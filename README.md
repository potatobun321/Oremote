<p align="center">
  <img src="oremote.png" alt="OLED Remote Logo" width="350" />
</p>

# 📱 OLED Remote (`Oremote`)

> **Turn any mobile browser into an ultra-low-latency, OLED-optimized touch remote for your computer — over LAN or anywhere via Tailscale.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Transport: WebRTC + Socket.IO](https://img.shields.io/badge/transport-WebRTC%20%7C%20Socket.IO-green.svg)](#architecture--transport)
[![Network: Tailscale Ready](https://img.shields.io/badge/network-Tailscale%20Ready-purple.svg)](TAILSCALE_SETUP.md)

---

## 📌 Overview

**OLED Remote (`Oremote`)** is a zero-install (client-side) web application that gives you full trackpad, keyboard, media, application, and shell control over your host PC directly from your phone's browser.

Designed specifically for OLED mobile displays with a sleek, pitch-black retro interface (`Press Start 2P`), `Oremote` pairs high-performance **WebRTC DataChannels** (UDP transport) with a robust **Socket.IO** fallback to deliver mouse dragging and clicks with virtually zero lag.

---

## ⚡ Key Features

- 🖱 **WebRTC Trackpad**: Real-time cursor control using raw WebRTC Data Channels (UDP-like speed). Supports 1-finger tap (left click), 2-finger tap (right click), and 2-finger drag (vertical scrolling).
- ⌨ **Keystroke Injection & Controls**: Direct text injection input box, arrow navigation, media keys (volume, play/pause, mute), system hotkeys (Win, Alt, Tab, Alt+Tab, Esc, Enter).
- 🚀 **App Launcher & Shell Command Execution**: One-tap app triggers (`Zen Browser`, `VS Code`, `Nautilus`, `VLC`, `Blender`) and quick terminal shortcuts (`ranger`, `htop`, `neofetch`, system update).
- 🛠 **System Control**: Quick desktop shortcuts, force-close active windows (`xdotool getactivewindow windowclose`), lock screen.
- 🌐 **Smart Adapter Detection**: Automatically filters out dead container/virtual interfaces (`docker0`, `veth`, `tun`, `wg`, `tailscale`) and prioritizes active physical Wi-Fi/Ethernet IPs for seamless setup.
- 🔒 **Hardened Security**: Every action requires a per-run 32-byte cryptographic token validated via constant-time comparison (`hmac.compare_digest`), backed by dynamic IP brute-force lockout throttling.

---

## 🔒 Security Advisory

> [!WARNING]
> **Oremote executes shell commands and system hotkeys on the host machine.**
> 
> - **Trusted Networks Only**: Intended strictly for your private local network (LAN) or a private encrypted overlay network like [Tailscale](https://tailscale.com).
> - **Do NOT Port-Forward**: Never expose port `5001` directly to the public internet without additional authentication / reverse proxy TLS.
> - **Token Protection**: Keep your startup URL and authentication token private. Anyone with access to the link and token on your network can issue commands to your machine.

---

## 📋 Requirements

### Host Machine
- **Python**: 3.10 or higher
- **Linux (X11)**: `xdotool` (`sudo apt install xdotool`)
- **Windows**: PowerShell (built-in)
- **Active Desktop Session**: Must be running inside a graphical environment (mouse/keyboard events require an active desktop session).

### Mobile / Client
- Any modern mobile browser (iOS Safari, Android Chrome, Firefox, Brave, Zen, etc.) with WebRTC and WebSocket support.

---

## 🚀 Quick Start

### 1. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/potatobun321/Oremote.git
cd Oremote

# Create virtual environment
python3 -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

*(Note: On Debian/Ubuntu/Mint, if `venv` creation fails, run `sudo apt install python3-venv` first).*

### 2. Run the Server

```bash
python3 my_remote.py
```

Upon launching, the terminal will display reachable local network URLs along with a generated authentication token:

```text
OLED Remote
Open on your phone:
  http://192.168.1.50:5001  (wlan0)

Auth token: aB3_x9Z...
```

Open the printed URL on your phone while connected to the same Wi-Fi network.

---

## 🌐 Remote & Cross-Network Access (Tailscale)

When on public Wi-Fi (cafes, hotels, university networks) or cellular data, routers often block direct device-to-device communication using **AP/Client Isolation**.

To use `Oremote` from **any location** securely:
1. Use **[Tailscale](https://tailscale.com)** (free for personal use).
2. Read the full step-by-step guide in [`TAILSCALE_SETUP.md`](./TAILSCALE_SETUP.md).
3. Connect your phone via Tailscale IP or MagicDNS URL (e.g. `http://100.x.y.z:5001`).

---

## 🏗 Architecture & Design

```mermaid
graph TD
    subgraph Phone [Mobile Browser Client]
        UI[OLED Web Interface]
        RTC_C[WebRTC DataChannel]
        WS_C[Socket.IO Client]
        HTTP_C[Fetch API HTTP POST]
    end

    subgraph Host [Host PC Server - my_remote.py]
        SRV[Flask + SocketIO + aiortc]
        AUTH[Token Auth & Rate Limiter]
        EXEC[Action Executor]
    end

    subgraph OS [Operating System Layer]
        XD[Linux: xdotool]
        PS[Windows: PowerShell / SendKeys]
    end

    UI -->|Mouse Movement (UDP-like Low Latency)| RTC_C
    RTC_C <-->|Binary Packet '<Ihh'| SRV
    UI -->|Fallback Mouse Movement| WS_C
    WS_C <-->|JSON Events| SRV
    UI -->|Clicks / Keys / Apps / Shell| HTTP_C
    HTTP_C -->|Headers: X-Auth-Token| AUTH
    AUTH -->|Valid Request| EXEC
    EXEC -->|X11 Input| XD
    EXEC -->|Win32 Input| PS
```

---

## 💡 What It Does Right (Highlights & Strengths)

- **Unmatched Trackpad Latency**: Employs raw WebRTC Data Channels using un-ordered UDP datagrams (`maxRetransmits: 0`). Cursor movement arrives instantaneously without head-of-line blocking TCP delays.
- **Fixed Endianness Bug**: Binary mouse-movement packets use explicitly matched unsigned bit packing (`<Ihh`) across client and server, guaranteeing rock-solid drag stability.
- **Smart Network Adapter Ordering**: Eliminates interface confusion by filtering out Docker, WireGuard, TUN/TAP, and virtual bridge interfaces, guaranteeing the primary Wi-Fi/Ethernet URL is displayed first.
- **Robust Security Architecture**:
  - Per-session cryptographically random 32-byte authorization token.
  - Constant-time comparison (`hmac.compare_digest`) protects against timing attacks.
  - Automatic IP brute-force lockout (throttles IPs exceeding 10 invalid attempts within 30 seconds).
- **Single-File Server Engine**: Clean, zero-build-step deployment where Python serves an embedded OLED dark-theme frontend with native haptic vibration (`navigator.vibrate`).

---

## 🔮 Roadmap & Areas for Improvement

While `Oremote` is fully functional and stable, the following enhancements are planned:

- [ ] **Native Wayland Support (Linux)**: Add `ydotool` / `wtype` / `uinput` backend options to support Wayland sessions alongside traditional X11 (`xdotool`).
- [ ] **macOS Compatibility**: Implement `osascript` / `Quartz` backend for macOS desktop control.
- [ ] **Cross-Platform Input Engine**: Refactor OS subprocess calls to unified libraries (e.g. `pynput` / `pyautogui`).
- [ ] **Configurable Application Grid**: Allow users to customize app launcher icons, names, and command strings via a `config.json` file.
- [ ] **Built-in HTTPS / Local TLS**: Enable self-signed TLS certificates out of the box to avoid mixed-content browser warnings on HTTPS networks.
- [ ] **Enhanced Touchpad Gestures**: Pinch-to-zoom, multi-finger window swiping, and custom hotkey bindings.

---

## 📄 License

Distributed under the MIT License. See [`LICENSE`](./LICENSE) for details.
