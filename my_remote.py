"""
OLED Remote — control your computer's keyboard, mouse, apps and shell
from your phone over the local network.

Open http://<this-machine-ip>:5001 on your phone while it's on the same
Wi-Fi / LAN as this machine.
"""
from flask import Flask, request, render_template_string
from flask_socketio import SocketIO, emit
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
import subprocess
import platform
import socket
import os
import secrets
import re
import asyncio
import struct
import fcntl
import hmac
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
# cors_allowed_origins=[] rejects EVERY origin, including the page's own —
# that can silently break the Socket.IO handshake on some browsers/networks.
# "*" is fine here because every state-changing action still requires the
# per-run AUTH_TOKEN below.
socketio = SocketIO(app, cors_allowed_origins="*")

AUTH_TOKEN = secrets.token_urlsafe(32)
system = platform.system()


def token_matches(candidate):
    """Constant-time token comparison to avoid timing attacks."""
    if not isinstance(candidate, str):
        return False
    return hmac.compare_digest(candidate, AUTH_TOKEN)


# ---------- BRUTE-FORCE THROTTLE ----------
# The token is the only thing standing between "anyone on this network"
# and arbitrary shell execution, so cheaply slow down guessing attempts
# from a single source instead of letting /run be hit at full speed.
import time
_failed_attempts = {}
_LOCKOUT_THRESHOLD = 10
_LOCKOUT_SECONDS = 30


def _client_throttled(ip):
    entry = _failed_attempts.get(ip)
    if not entry:
        return False
    count, first_seen = entry
    if time.time() - first_seen > _LOCKOUT_SECONDS:
        _failed_attempts.pop(ip, None)
        return False
    return count >= _LOCKOUT_THRESHOLD


def _record_failed_attempt(ip):
    count, first_seen = _failed_attempts.get(ip, (0, time.time()))
    _failed_attempts[ip] = (count + 1, first_seen)


# ---------- WEBRTC ASYNCIO LOOP ----------
_webrtc_loop = asyncio.new_event_loop()
_webrtc_thread = threading.Thread(target=_webrtc_loop.run_forever, daemon=True)
_webrtc_thread.start()


def _run_webrtc(coro):
    return asyncio.run_coroutine_threadsafe(coro, _webrtc_loop).result(timeout=10)


_webrtc_sessions = {}


def _parse_browser_ice(candidate_str, sdp_mid, sdp_m_line_index):
    parts = candidate_str.split()
    if len(parts) < 8 or not parts[0].startswith("candidate:"):
        return None
    return RTCIceCandidate(
        component=int(parts[1]),
        foundation=parts[0].split(":", 1)[1],
        ip=parts[4],
        port=int(parts[5]),
        priority=int(parts[3]),
        protocol=parts[2],
        type=parts[7],
        sdpMid=sdp_mid,
        sdpMLineIndex=sdp_m_line_index,
    )


async def _close_session(session):
    pc = session.get('pc')
    if pc:
        try:
            await pc.close()
        except Exception:
            pass


# ---------- GET LOCAL IP ----------
# Interfaces that are virtual/tunnel/container adapters rather than the
# real Wi-Fi/Ethernet link to your router. If one of these sorts before
# your real adapter (common once Docker, a VPN, or a virtual machine has
# been installed), the URL printed at startup points at a dead interface
# — which looks like "it broke on the new network" but is really "it was
# printing the wrong IP the whole time, home just happened to sort first".
IGNORED_IFACE_PREFIXES = (
    'docker', 'veth', 'br-', 'virbr', 'vmnet', 'vboxnet',
    'tun', 'tap', 'wg', 'zt', 'tailscale', 'utun', 'anbox', 'podman',
)


def get_all_ips():
    ips = []
    try:
        with open('/proc/net/dev') as f:
            lines = f.readlines()[2:]
            for line in lines:
                iface = line.split(':')[0].strip()
                if iface == 'lo' or iface.startswith(IGNORED_IFACE_PREFIXES):
                    continue
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    ip = socket.inet_ntoa(fcntl.ioctl(
                        s.fileno(),
                        0x8915,  # SIOCGIFADDR
                        struct.pack('256s', iface.encode('utf-8')[:15])
                    )[20:24])
                    ips.append((iface, ip))
                    s.close()
                except Exception:
                    pass
    except Exception:
        pass
    # Prefer real Wi-Fi/Ethernet adapter names first (wlan, wl*, eth, en*)
    # so the FIRST printed URL is the one that's actually reachable, even
    # on a machine with several adapters.
    def _priority(item):
        iface = item[0]
        if iface.startswith(('wl', 'wifi')):
            return 0
        if iface.startswith(('eth', 'en')):
            return 1
        return 2
    ips.sort(key=_priority)
    return ips


def get_local_ip():
    all_ips = get_all_ips()
    if all_ips:
        return all_ips[0][1]
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


# ---------- INPUT VALIDATION ----------
VALID_ACTIONS = {"key", "type", "launch", "cmd", "click"}
SAFE_KEY_RE = re.compile(r'^[a-zA-Z0-9_+]+$')
BLOCKED_TYPE_CHARS = re.compile(r'[;|&`$(){}!\n\r]')


def validate_input(action_type, value):
    if not isinstance(value, str) or not value or '\x00' in value:
        return False
    if action_type not in VALID_ACTIONS:
        return False
    if action_type == "key" and not SAFE_KEY_RE.match(value):
        return False
    if action_type == "type" and system == "Windows" and BLOCKED_TYPE_CHARS.search(value):
        return False
    if action_type == "click" and not value.isdigit():
        return False
    return True


# ---------- ACTION EXECUTOR ----------
def execute_action(action_type, value):
    if not validate_input(action_type, value):
        return "INVALID"
    if system == "Windows":
        if action_type == "key":
            subprocess.run(["powershell", "-Command",
                f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{{{value}}}')"])
        elif action_type == "type":
            subprocess.run(["powershell", "-Command",
                f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{value}')"])
        elif action_type == "launch":
            subprocess.Popen(["start", value], shell=True)
        elif action_type == "cmd":
            subprocess.Popen(["start", "cmd", "/k", value], shell=True)
    else:  # Linux
        if action_type == "key":
            subprocess.run(["xdotool", "key", value])
        elif action_type == "type":
            subprocess.run(["xdotool", "type", "--delay", "50", value])
        elif action_type == "launch":
            subprocess.Popen(["sh", "-c", value], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action_type == "cmd":
            subprocess.Popen([
                "x-terminal-emulator", "-e", "bash", "-c",
                f"{value} ; exec bash"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action_type == "click":
            subprocess.run(["xdotool", "click", value])
    return "OK"


# ---------- WEBSOCKET: MOUSE MOVE (FALLBACK) ----------
@socketio.on('move')
def handle_move(data):
    if not isinstance(data, dict) or not token_matches(data.get('token')):
        return
    try:
        dx = int(data.get('dx', 0))
        dy = int(data.get('dy', 0))
    except (TypeError, ValueError):
        return
    subprocess.run(["xdotool", "mousemove_relative", "--", str(dx), str(dy)])


# ---------- WEBRTC SIGNALING ----------
@socketio.on('webrtc-offer')
def handle_webrtc_offer(data):
    sid = request.sid

    async def _setup():
        # A client may re-offer (e.g. after a page reload) while its old
        # session is still registered — close the stale connection first
        # instead of leaking it.
        old_session = _webrtc_sessions.pop(sid, None)
        if old_session:
            await _close_session(old_session)

        pc = RTCPeerConnection()
        session_id = os.urandom(4)
        session_id_int = struct.unpack('<I', session_id)[0]

        _webrtc_sessions[sid] = {
            'pc': pc, 'channel': None, 'session_id': session_id_int
        }

        @pc.on("datachannel")
        def on_datachannel(channel):
            if sid in _webrtc_sessions:
                _webrtc_sessions[sid]['channel'] = channel

                @channel.on("message")
                def on_message(message):
                    if isinstance(message, bytes) and len(message) == 8:
                        # NOTE: must unpack as unsigned ('I') to match how
                        # session_id_int was stored above ('<I'). Unpacking
                        # as signed ('i') here made this comparison fail
                        # for ~50% of randomly generated session IDs (any
                        # time the top bit of the top byte was set),
                        # silently dropping every drag/mouse-move packet
                        # for that session while leaving clicks (a
                        # separate HTTP path) unaffected.
                        s, dx, dy = struct.unpack('<Ihh', message)
                        if s == session_id_int:
                            subprocess.run(["xdotool", "mousemove_relative",
                                            "--", str(dx), str(dy)])

        @pc.on("icecandidate")
        def on_ice_candidate(candidate):
            if candidate and sid in _webrtc_sessions:
                socketio.emit('webrtc-ice-server', {
                    'candidate': candidate.candidate,
                    'sdpMid': candidate.sdpMid,
                    'sdpMLineIndex': candidate.sdpMLineIndex,
                }, room=sid)

        await pc.setRemoteDescription(RTCSessionDescription(
            sdp=data['sdp'], type=data['type']
        ))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return {
            'sdp': pc.localDescription.sdp,
            'type': pc.localDescription.type,
            'session_id': list(session_id)
        }

    try:
        result = _run_webrtc(_setup())
        if result:
            emit('webrtc-answer', result)
    except Exception as e:
        print(f"WebRTC offer error: {e}")


@socketio.on('webrtc-ice')
def handle_webrtc_ice(data):
    session = _webrtc_sessions.get(request.sid)
    if session:
        async def _add():
            candidate = _parse_browser_ice(
                data['candidate']['candidate'],
                data['candidate'].get('sdpMid'),
                data['candidate'].get('sdpMLineIndex'),
            )
            if candidate:
                await session['pc'].addIceCandidate(candidate)
        try:
            _run_webrtc(_add())
        except Exception as e:
            print(f"WebRTC ICE error: {e}")


@socketio.on('disconnect')
def handle_disconnect():
    session = _webrtc_sessions.pop(request.sid, None)
    if session:
        try:
            _run_webrtc(_close_session(session))
        except Exception:
            pass


# ---------- HTML UI ----------
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>OLED Remote</title>
    <link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
        html, body {
            background: #000;
            color: #fff;
            font-family: 'Press Start 2P', monospace;
            margin: 0;
            padding: 0;
            user-select: none;
            -webkit-user-select: none;
            overscroll-behavior: none;
            height: 100%;
        }
        body {
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }
        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 12px;
            border-bottom: 1px solid #222;
            flex-shrink: 0;
        }
        .topbar .title { font-size: 11px; letter-spacing: 1px; color: #ccc; }
        #status-badge {
            font-size: 8px;
            padding: 5px 9px;
            border: 1px solid #555;
            color: #555;
            border-radius: 3px;
        }
        #status-badge.ws { color: #ff0; border-color: #ff0; }
        #status-badge.udp { color: #0f0; border-color: #0f0; }
        #status-badge.off { color: #f44; border-color: #f44; }

        .page { flex: 1; display: none; padding: 14px; padding-bottom: 90px; overflow-y: auto; }
        .page.active { display: block; }

        .section-title {
            font-size: 11px;
            letter-spacing: 2px;
            color: #888;
            text-transform: uppercase;
            padding-bottom: 4px;
            border-bottom: 1px solid #333;
            margin: 18px 0 10px 0;
        }
        .section-title:first-child { margin-top: 0; }

        .grid { display: grid; gap: 8px; }
        .btn {
            background: #111;
            border: 2px solid #fff;
            color: #fff;
            font-family: 'Press Start 2P', monospace;
            font-size: 10px;
            padding: 12px 6px;
            text-align: center;
            cursor: pointer;
            min-height: 52px;
            line-height: 1.4;
            word-break: break-word;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 4px;
        }
        .btn:active { background: #fff; color: #000; }
        .btn-wide { grid-column: span 2; }
        .btn-tall { min-height: 66px; }
        .btn-full { grid-column: 1 / -1; }
        .grid-4 { grid-template-columns: repeat(4, 1fr); }
        .grid-3 { grid-template-columns: repeat(3, 1fr); }
        .grid-2 { grid-template-columns: repeat(2, 1fr); }
        .media { border-color: #0af; }
        .danger { border-color: #f44; }

        .input-area { display: flex; gap: 8px; width: 100%; }
        .input-area input {
            flex: 1;
            background: #111;
            border: 2px solid #fff;
            border-radius: 4px;
            color: #fff;
            padding: 12px;
            font-family: 'Press Start 2P', monospace;
            font-size: 10px;
            outline: none;
            min-height: 52px;
            min-width: 0;
        }
        .input-area input:focus { background: #222; }
        .input-area .btn { flex-shrink: 0; min-width: 76px; min-height: 52px; }

        /* ---- Touchpad ---- */
        #touchpad {
            width: 100%;
            height: 46vh;
            min-height: 260px;
            background: repeating-linear-gradient(0deg, #0a0a0a, #0a0a0a 23px, #111 24px),
                        repeating-linear-gradient(90deg, #0a0a0a, #0a0a0a 23px, #111 24px);
            border: 2px solid #444;
            border-radius: 8px;
            touch-action: none;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #444;
            font-size: 9px;
            letter-spacing: 1px;
            text-align: center;
            padding: 12px;
        }
        #touchpad.active { border-color: #0af; }
        .pad-hint { line-height: 1.8; }

        .settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 14px; }
        .setting-group { display: flex; flex-direction: column; gap: 6px; }
        .setting-label { font-size: 9px; color: #888; }
        .setting-value { color: #fff; }
        input[type="range"] {
            -webkit-appearance: none; appearance: none;
            width: 100%; height: 4px; background: #333; outline: none; border-radius: 2px;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none; appearance: none;
            width: 20px; height: 20px; background: #fff; border-radius: 50%; cursor: pointer;
        }
        input[type="range"]::-moz-range-thumb {
            width: 20px; height: 20px; background: #fff; border: none; border-radius: 50%; cursor: pointer;
        }

        /* ---- Tab bar ---- */
        .tabbar {
            position: fixed;
            bottom: 0; left: 0; right: 0;
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            background: #0a0a0a;
            border-top: 1px solid #222;
            padding-bottom: env(safe-area-inset-bottom, 0px);
        }
        .tab {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            gap: 4px; padding: 10px 2px; color: #666; font-size: 8px; cursor: pointer;
        }
        .tab .icon { font-size: 18px; }
        .tab.active { color: #0af; }

        /* ---- Toast ---- */
        #toast {
            position: fixed;
            top: 52px; left: 50%; transform: translateX(-50%) translateY(-10px);
            background: #1a1a1a; border: 1px solid #f44; color: #f44;
            font-size: 9px; padding: 10px 14px; border-radius: 4px;
            opacity: 0; transition: opacity 0.2s, transform 0.2s;
            z-index: 1000; max-width: 90%; text-align: center; pointer-events: none;
        }
        #toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
    </style>
</head>
<body>

<div class="topbar">
    <div class="title">OLED REMOTE</div>
    <div id="status-badge" class="off">OFFLINE</div>
</div>
<div id="toast"></div>

<!-- ===== TRACKPAD PAGE ===== -->
<div class="page active" id="page-pad">
    <div class="section-title">🖱 Trackpad</div>
    <div id="touchpad">
        <div class="pad-hint">
            DRAG TO MOVE<br>
            TAP = LEFT CLICK<br>
            TWO-FINGER TAP = RIGHT CLICK<br>
            TWO-FINGER DRAG = SCROLL
        </div>
    </div>
    <div class="grid grid-2" style="margin-top:10px;">
        <div class="btn" onclick="send('click','1')">LEFT CLICK</div>
        <div class="btn danger" onclick="send('click','3')">RIGHT CLICK</div>
    </div>
    <div class="settings-grid">
        <div class="setting-group">
            <div class="setting-label">SENSITIVITY <span class="setting-value" id="speedVal">1.0</span>x</div>
            <input type="range" id="speedSlider" min="3" max="30" value="10">
        </div>
        <div class="setting-group">
            <div class="setting-label">SCROLL SPEED <span class="setting-value" id="rateVal">50</span>ms</div>
            <input type="range" id="rateSlider" min="10" max="150" value="50">
        </div>
    </div>
</div>

<!-- ===== KEYS PAGE ===== -->
<div class="page" id="page-keys">
    <div class="section-title">⌨ Keystroke Injection</div>
    <div class="input-area">
        <input id="customText" type="text" placeholder="TYPE HERE..." autocomplete="off"
               onkeydown="if(event.key==='Enter') sendType()">
        <div class="btn" onclick="sendType()">SEND</div>
    </div>

    <div class="section-title">⌨ Keyboard</div>
    <div class="grid grid-4">
        <div class="btn" onclick="send('key','space')">SPACE</div>
        <div class="btn" onclick="send('key','Return')">ENTER</div>
        <div class="btn" onclick="send('key','BackSpace')">⌫</div>
        <div class="btn" onclick="send('key','Escape')">ESC</div>
        <div class="btn" onclick="send('key','Left')">◄</div>
        <div class="btn" onclick="send('key','Right')">►</div>
        <div class="btn" onclick="send('key','Up')">▲</div>
        <div class="btn" onclick="send('key','Down')">▼</div>
        <div class="btn" onclick="send('key','Super_L')">WIN</div>
        <div class="btn" onclick="send('key','Alt_L')">ALT</div>
        <div class="btn" onclick="send('key','Tab')">TAB</div>
        <div class="btn" onclick="send('key','Alt_L+Tab')">ALT+TAB</div>
    </div>

    <div class="section-title">🎵 Playback</div>
    <div class="grid grid-4">
        <div class="btn media" onclick="send('key','XF86AudioRaiseVolume')">VOL+</div>
        <div class="btn media" onclick="send('key','XF86AudioLowerVolume')">VOL-</div>
        <div class="btn danger" onclick="send('key','XF86AudioMute')">MUTE</div>
        <div class="btn media" onclick="send('key','XF86AudioPlay')">PLAY</div>
    </div>
</div>

<!-- ===== APPS PAGE ===== -->
<div class="page" id="page-apps">
    <div class="section-title">📟 Custom Launch</div>
    <div class="input-area">
        <input id="customCmd" type="text" placeholder="COMMAND OR PATH..." autocomplete="off"
               onkeydown="if(event.key==='Enter') sendCmd()">
        <div class="btn danger" onclick="sendCmd()">RUN</div>
    </div>

    <div class="section-title">📂 Applications</div>
    <div class="grid grid-3">
        <div class="btn btn-wide" onclick="send('launch','flatpak run app.zen_browser.zen')">ZEN</div>
        <div class="btn" onclick="send('launch','code')">CODE</div>
        <div class="btn" onclick="send('launch','gnome-terminal')">TERM</div>
        <div class="btn" onclick="send('launch','nautilus')">FILES</div>
        <div class="btn" onclick="send('launch','vlc')">VLC</div>
        <div class="btn" onclick="send('launch','blender')">BLENDER</div>
    </div>

    <div class="section-title">💻 Terminal</div>
    <div class="grid grid-2">
        <div class="btn btn-wide btn-tall" onclick="send('cmd','ranger')">📁 RANGER</div>
        <div class="btn btn-wide btn-tall" onclick="send('cmd','neofetch')">🖥 NEOFETCH</div>
        <div class="btn btn-full" onclick="send('cmd','sudo apt update && sudo apt upgrade -y')">⬆ UPDATE</div>
        <div class="btn" onclick="send('cmd','htop')">📊 HTOP</div>
        <div class="btn" onclick="send('cmd','gnome-system-monitor')">📈 SYSTEM</div>
        <div class="btn" onclick="send('cmd','clear')">🧹 CLEAR</div>
    </div>
</div>

<!-- ===== SYSTEM PAGE ===== -->
<div class="page" id="page-system">
    <div class="section-title">🛠 System</div>
    <div class="grid grid-2">
        <div class="btn danger" onclick="send('launch','xdotool getactivewindow windowclose')">FORCE QUIT WIN</div>
        <div class="btn danger" onclick="send('key','Super_L+l')">LOCK SCREEN</div>
    </div>
    <div class="section-title">🔐 Session</div>
    <div style="font-size:9px; color:#888; line-height:1.8; word-break:break-all;">
        Auth token is embedded in this page and required for every action.
        Keep this URL private — anyone with it and LAN access can control this machine.
    </div>
</div>

<div class="tabbar">
    <div class="tab active" data-page="page-pad" onclick="showPage('page-pad', this)">
        <div class="icon">🖱</div>TRACKPAD
    </div>
    <div class="tab" data-page="page-keys" onclick="showPage('page-keys', this)">
        <div class="icon">⌨</div>KEYS
    </div>
    <div class="tab" data-page="page-apps" onclick="showPage('page-apps', this)">
        <div class="icon">📂</div>APPS
    </div>
    <div class="tab" data-page="page-system" onclick="showPage('page-system', this)">
        <div class="icon">🛠</div>SYSTEM
    </div>
</div>

<script>
const AUTH_TOKEN = "{{ auth_token }}";
const socket = io();

// ---------- TAB NAVIGATION ----------
function showPage(id, tabEl) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    tabEl.classList.add('active');
}

// ---------- TOAST ----------
let toastTimer = null;
function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2200);
}

// ---------- CONNECTION STATUS ----------
function setStatus(mode) {
    const badge = document.getElementById('status-badge');
    badge.classList.remove('ws', 'udp', 'off');
    if (mode === 'udp') { badge.textContent = 'UDP'; badge.classList.add('udp'); }
    else if (mode === 'ws') { badge.textContent = 'WS'; badge.classList.add('ws'); }
    else { badge.textContent = 'OFFLINE'; badge.classList.add('off'); }
}

// ---------- WEBRTC DATACHANNEL ----------
let pc = null;
let dc = null;
let useUDP = false;
let sessionId = null;

async function setupWebRTC() {
    try {
        pc = new RTCPeerConnection({ iceServers: [] });
        dc = pc.createDataChannel('mouse', { ordered: false, maxRetransmits: 0 });

        dc.onopen = () => { useUDP = true; setStatus('udp'); };
        dc.onclose = () => {
            useUDP = false;
            setStatus(socket.connected ? 'ws' : 'off');
            setTimeout(() => {
                if (!pc || pc.connectionState !== 'connected') setupWebRTC();
            }, 3000);
        };
        dc.onerror = () => { useUDP = false; setStatus(socket.connected ? 'ws' : 'off'); };

        pc.onicecandidate = (event) => {
            if (event.candidate) socket.emit('webrtc-ice', { candidate: event.candidate });
        };
        pc.onconnectionstatechange = () => {
            if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
                useUDP = false;
                setStatus(socket.connected ? 'ws' : 'off');
                setTimeout(() => setupWebRTC(), 3000);
            }
        };

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        socket.emit('webrtc-offer', { sdp: pc.localDescription.sdp, type: pc.localDescription.type });
    } catch (e) {
        console.log('WebRTC setup failed, using WebSocket:', e);
        useUDP = false;
        setStatus(socket.connected ? 'ws' : 'off');
    }
}

socket.on('webrtc-answer', async (data) => {
    try {
        await pc.setRemoteDescription(new RTCSessionDescription({ sdp: data.sdp, type: data.type }));
        const b = data.session_id;
        sessionId = b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24);
    } catch (e) {
        console.log('WebRTC answer error:', e);
    }
});

socket.on('webrtc-ice-server', async (data) => {
    if (pc) {
        try {
            await pc.addIceCandidate(new RTCIceCandidate({
                candidate: data.candidate, sdpMid: data.sdpMid, sdpMLineIndex: data.sdpMLineIndex
            }));
        } catch (e) {
            console.log('Failed to add server ICE candidate:', e);
        }
    }
});

socket.on('connect', () => { setStatus('ws'); setupWebRTC(); });
socket.on('disconnect', () => { useUDP = false; setStatus('off'); showToast('Disconnected from server'); });

// ---------- SETTINGS ----------
let sensitivity = 1.0;
let scrollRate = 50;

document.getElementById('speedSlider').addEventListener('input', function() {
    sensitivity = parseInt(this.value) / 10;
    document.getElementById('speedVal').textContent = sensitivity.toFixed(1);
});
document.getElementById('rateSlider').addEventListener('input', function() {
    scrollRate = parseInt(this.value);
    document.getElementById('rateVal').textContent = scrollRate;
});

// ---------- MOUSE MOVE (UNIFIED TRANSPORT) ----------
function sendMouseMove(dx, dy) {
    if (dx === 0 && dy === 0) return;
    if (dc && dc.readyState === 'open' && sessionId !== null) {
        const buf = new ArrayBuffer(8);
        const view = new DataView(buf);
        view.setInt32(0, sessionId, true);
        view.setInt16(4, dx, true);
        view.setInt16(6, dy, true);
        dc.send(buf);
    } else {
        socket.emit('move', { dx: dx, dy: dy, token: AUTH_TOKEN });
    }
}

// ---------- TOUCHPAD (drag = move, tap = click, two-finger = right-click/scroll) ----------
const pad = document.getElementById('touchpad');
let padActive = false;
let lastX = 0, lastY = 0, startTime = 0, moved = false, touchCount = 1;
let scrollIntervalId = null;
const TAP_MAX_MS = 300;
const TAP_MAX_MOVE = 6;

function padStart(x, y, count) {
    padActive = true;
    lastX = x; lastY = y;
    startTime = Date.now();
    moved = false;
    touchCount = count;
    pad.classList.add('active');
}

function padMove(x, y) {
    if (!padActive) return;
    const dx = x - lastX;
    const dy = y - lastY;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
    lastX = x; lastY = y;

    if (touchCount >= 2) {
        if (Math.abs(dy) > 4) send('click', dy > 0 ? '5' : '4'); // two-finger drag = scroll
    } else {
        sendMouseMove(Math.round(dx * sensitivity), Math.round(dy * sensitivity));
    }
}

function padEnd() {
    if (!padActive) return;
    const duration = Date.now() - startTime;
    if (!moved && duration < TAP_MAX_MS) {
        send('click', touchCount >= 2 ? '3' : '1');
    }
    padActive = false;
    pad.classList.remove('active');
}

pad.addEventListener('touchstart', (e) => {
    e.preventDefault();
    const t = e.touches[0];
    padStart(t.clientX, t.clientY, e.touches.length);
}, { passive: false });
pad.addEventListener('touchmove', (e) => {
    e.preventDefault();
    const t = e.touches[0];
    padMove(t.clientX, t.clientY);
}, { passive: false });
pad.addEventListener('touchend', (e) => {
    e.preventDefault();
    padEnd();
}, { passive: false });

// Mouse fallback so the trackpad is also testable from a desktop browser.
pad.addEventListener('mousedown', (e) => padStart(e.clientX, e.clientY, 1));
window.addEventListener('mousemove', (e) => { if (padActive) padMove(e.clientX, e.clientY); });
window.addEventListener('mouseup', () => padEnd());

// ---------- SEND FUNCTIONS ----------
function send(action, value) {
    fetch('/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Auth-Token': AUTH_TOKEN },
        body: JSON.stringify({ action: action, value: value })
    })
    .then((res) => {
        if (navigator.vibrate) navigator.vibrate(10);
        if (res.status === 401) showToast('Unauthorized — reload the page');
        else if (!res.ok) showToast('Action failed');
    })
    .catch(() => showToast('Cannot reach server'));
}

function sendType() {
    const input = document.getElementById('customText');
    if (input.value.trim() !== '') {
        send('type', input.value);
        input.value = '';
        input.focus();
    }
}

function sendCmd() {
    const input = document.getElementById('customCmd');
    if (input.value.trim() !== '') {
        send('cmd', input.value);
        input.value = '';
        input.focus();
    }
}
</script>
</body>
</html>
"""

# ---------- ROUTES ----------
@app.route('/')
def home():
    return render_template_string(HTML_PAGE, auth_token=AUTH_TOKEN)


@app.route('/run', methods=['POST'])
def run():
    client_ip = request.remote_addr
    if _client_throttled(client_ip):
        return "Too many failed attempts, try again shortly", 429
    if not token_matches(request.headers.get('X-Auth-Token')):
        _record_failed_attempt(client_ip)
        return "Unauthorized", 401
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    value = data.get('value')
    if action and value:
        result = execute_action(action, value)
        if result == "INVALID":
            return "Invalid action/value", 400
        return "OK"
    return "Missing params", 400


# ---------- START SERVER ----------
if __name__ == '__main__':
    port = 5001
    all_ips = get_all_ips()
    primary_ip = all_ips[0][1] if all_ips else get_local_ip()
    print("OLED Remote")
    print("Open on your phone:")
    for iface, ip in all_ips:
        print(f"  http://{ip}:{port}  ({iface})")
    if not all_ips:
        print(f"  http://{primary_ip}:{port}")
    print(f"Auth token: {AUTH_TOKEN}")
    print()
    print("If the phone can't reach this on a network other than home:")
    print("  - Confirm the phone and this PC are actually on the same")
    print("    Wi-Fi network (not one on 5GHz guest + one on 2.4GHz main,")
    print("    which some routers split into separate subnets).")
    print("  - Windows: this PC's firewall profile for that network may be")
    print("    'Public', which blocks inbound connections by default. Set")
    print("    it to 'Private' or add a firewall rule for port 5001/TCP.")
    print("  - Linux: check ufw/firewalld isn't blocking port 5001.")
    print("  - Many cafe/office/hotel Wi-Fi and phone hotspots enable")
    print("    'client/AP isolation', which blocks device-to-device")
    print("    traffic on purpose even though both are 'on the network'.")
    print("    There's no code fix for this - it has to be disabled on")
    print("    the router/hotspot itself, or avoided with a private")
    print("    overlay network like Tailscale or ZeroTier (see README).")
    print("Press Ctrl+C to stop")
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
