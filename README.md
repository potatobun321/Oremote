<div align="center">
  <img src="oremote.png" width="32" height="32" alt="oremote logo" align="center"> 
    <h1> Oremote </h1>
    <p><strong>Control your computer's trackpad, keyboard, applications, and shell commands from your mobile browser</strong></p>
</div>


---

> **Note:** Early release (v0.1.0). Under active development.

---

## Features

- **Trackpad**: Real-time cursor movement over WebRTC DataChannel with WebSocket fallback. Tap to click, two-finger tap for right-click, two-finger drag to scroll.
- **Keyboard & Media**: Keystroke injection, navigation keys, volume control, and playback toggles.
- **App Launcher**: Configurable app shortcuts and terminal command buttons via `config.json`.
- **Interface Selection**: Automatically detects and prioritizes active Wi-Fi and Ethernet adapters.
- **Token Security**: Dynamic 32-byte session token with IP rate-limiting protection.

---

## Requirements

- Python 3.10+
- **Linux**: `xdotool` (`sudo apt install xdotool python3-venv`)
- **Windows**: PowerShell (built-in)
- Active graphical desktop session

---

## Quick Start

1. **Clone & Setup**:
   ```bash
   git clone https://github.com/potatobun321/Oremote.git
   cd Oremote

   python3 -m venv venv
   source venv/bin/activate       # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run Server**:
   ```bash
   python3 my_remote.py
   ```

3. **Connect from Phone**:
   - **Same Wi-Fi**: Open the printed IP URL (e.g. `http://192.168.1.x:5001`).
   - **Cellular / Different Network**: Open `http://<tailscale-ip>:5001` (see [Tailscale Setup](./TAILSCALE_SETUP.md)).

---

## Configuration

Customize launcher buttons by editing `config.json` in the project root:

```json
{
  "apps": [
    { "label": "CODE", "type": "launch", "value": "code" },
    { "label": "TERM", "type": "launch", "value": "gnome-terminal" }
  ],
  "terminal": [
    { "label": "HTOP", "type": "cmd", "value": "htop" }
  ]
}
```

---

## Remote Access (Tailscale)

If your router enables AP/Client isolation or you are on cellular data (4G/5G), use [Tailscale](https://tailscale.com) to connect securely without port-forwarding. See [`TAILSCALE_SETUP.md`](./TAILSCALE_SETUP.md) for full instructions.

---

## About

Created and maintained by [@potatobun321](https://github.com/potatobun321). Designed for minimal OLED mobile screens, low-latency WebRTC trackpad control, and customizable system shortcuts over LAN or Tailscale.

---

## License

[MIT](./LICENSE)
