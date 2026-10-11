<div align="center">
  <img src="oremote.png" width="64" height="64" alt="oremote logo" align="center"> 
    <h1> Oremote </h1>
    <p><strong>Control your computer's trackpad, keyboard, applications, and shell commands from your mobile browser</strong></p>
</div>

---

> **Note:** Early release (v0.1.0). Cross-platform support for Linux & Windows.

---

## Features

- **Trackpad**: Real-time cursor movement over WebRTC DataChannel with WebSocket fallback. Tap to click, two-finger tap for right-click, two-finger drag to scroll.
- **Keyboard & Media**: Keystroke injection, navigation keys, volume control, and playback toggles.
- **App Launcher**: Configurable app shortcuts and terminal command buttons via `config.json` with OS-specific profiles.
- **Interface Selection**: Automatically detects and prioritizes active Wi-Fi and Ethernet adapters on both Windows and Linux.
- **Token Security**: Dynamic 32-byte session token with IP rate-limiting protection.

---

## Requirements

- Python 3.10+
- **Linux**: `xdotool` (`sudo apt install xdotool python3-venv`)
- **Windows**: Built-in Windows User32 API (no extra tools required)
- Active graphical desktop session

---

## Quick Start

### Linux

1. **Clone & Setup**:
   ```bash
   git clone https://github.com/potatobun321/Oremote.git
   cd Oremote

   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run Server**:
   ```bash
   python3 my_remote.py
   ```

### Windows

1. **Clone & Setup** (PowerShell or Command Prompt):
   ```powershell
   git clone https://github.com/potatobun321/Oremote.git
   cd Oremote

   python -m venv venv
   .\venv\Scripts\Activate.ps1       # Or `venv\Scripts\activate.bat` in CMD
   pip install -r requirements.txt
   ```

   > **Note for PowerShell execution policy**: If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` in PowerShell.

2. **Run Server**:
   ```powershell
   python my_remote.py
   ```

### Connect from Phone

- **Same Wi-Fi**: Open the printed IP URL (e.g. `http://192.168.1.x:5001`).
- **Cellular / Different Network**: Open `http://<tailscale-ip>:5001` (see [Tailscale Setup](./TAILSCALE_SETUP.md)).

---

## Configuration

Customize launcher buttons by editing `config.json` in the project root. `config.json` supports separate sections for `"windows"` and `"linux"`:

```json
{
  "windows": {
    "apps": [
      { "label": "CODE", "type": "launch", "value": "code", "class": "btn-wide" },
      { "label": "TERM", "type": "launch", "value": "powershell" },
      { "label": "FILES", "type": "launch", "value": "explorer" }
    ],
    "terminal": [
      { "label": "SYSINFO", "type": "cmd", "value": "systeminfo" },
      { "label": "IPCONFIG", "type": "cmd", "value": "ipconfig" }
    ]
  },
  "linux": {
    "apps": [
      { "label": "CODE", "type": "launch", "value": "code" },
      { "label": "TERM", "type": "launch", "value": "gnome-terminal" }
    ],
    "terminal": [
      { "label": "HTOP", "type": "cmd", "value": "htop" }
    ]
  }
}
```

---

## Troubleshooting & Firewall

- **Windows Defender Firewall**: When running on Windows for the first time, Windows Defender Firewall may prompt you to allow Python network access. Ensure **Private networks** is checked. If connections time out, verify port `5001` is allowed through Windows Firewall.
- **Linux Firewall**: Ensure `ufw` or `firewalld` permits incoming traffic on port `5001` (`sudo ufw allow 5001/tcp`).
- **Client/AP Isolation**: Public Wi-Fi networks (cafes, hotels, universities) often block device-to-device connections. Use [Tailscale](./TAILSCALE_SETUP.md) for direct connectivity in these environments.

---

## Remote Access (Tailscale)

If your router enables AP/Client isolation or you are on cellular data (4G/5G), use [Tailscale](https://tailscale.com) to connect securely without port-forwarding. See [`TAILSCALE_SETUP.md`](./TAILSCALE_SETUP.md) for full instructions.

---

## About

Created and maintained by [@potatobun321](https://github.com/potatobun321). Designed for minimal OLED mobile screens, low-latency WebRTC trackpad control, and customizable system shortcuts over LAN or Tailscale.

---

## License

[MIT](./LICENSE)
