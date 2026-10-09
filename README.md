# <img src="oremote.png" width="32" height="32" alt="oremote logo" align="center"> oremote

Control your computer's trackpad, keyboard, applications, and shell commands from your mobile browser.

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
- **Linux**: `xdotool` (`sudo apt install xdotool`)
- **Windows**: PowerShell (built-in)
- Active graphical desktop session

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python3 my_remote.py
```

Open the printed IP URL on your mobile browser while connected to the same network (e.g., `http://192.168.1.x:5001`).

---

## Configuration

Customize your launcher buttons by editing `config.json` in the project root:

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

## Remote Access

If your router enables AP/Client isolation or you are on a public network, use [Tailscale](https://tailscale.com) to route traffic securely. See [`TAILSCALE_SETUP.md`](./TAILSCALE_SETUP.md) for details.

---

## License

[MIT](./LICENSE)
