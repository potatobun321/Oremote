# Changelog

Fixes and hardening made to `my_remote.py` / README.

## Fixed

- **Windows startup crash on `fcntl` import.** `fcntl` is a POSIX-only module that caused `ModuleNotFoundError: No module named 'fcntl'` on Windows. Replaced with conditional import and a cross-platform fallback for interface and IP detection.
- **Windows trackpad & mouse control.** Both WebRTC and WebSocket mouse handlers previously invoked `xdotool` directly, causing `FileNotFoundError` on Windows. Replaced with native Win32 User32 API calls (`ctypes.windll.user32.mouse_event`), supporting sub-millisecond cursor movement, left/middle/right click, and mouse wheel scrolling with zero external dependencies.
- **Windows keystroke latency & exceptions.** Removed the slow PowerShell `SendKeys` subprocess execution (~1s delay per key) and replaced with native `keybd_event` and `KEYEVENTF_UNICODE`. Properly mapped navigation keys (`space`, `Return`, `BackSpace`, arrows), media controls (`VOL+`, `VOL-`, `MUTE`, `PLAY`), window management (`Alt+F4`), and system lock (`LockWorkStation`).
- **Drag-to-move silently failed ~50% of the time over the WebRTC data
  channel.** The server generated each session ID as an *unsigned*
  32-bit integer (`struct.unpack('<I', ...)`) but compared incoming
  mouse-move packets using a *signed* unpack (`'<ihh'`). Those two
  interpretations of the same bytes only agree when the top bit of the
  top byte is 0 — a coin flip on every new session. When they
  disagreed, the server silently dropped every drag packet while
  clicks and other actions (a separate HTTP path) kept working,
  making the bug look intermittent/network-related when it was purely
  a random-number coin flip. Fixed by unpacking as unsigned (`'<Ihh'`)
  to match how the ID was generated.

## Added

- **Full Windows cross-platform support.** Native zero-dependency Windows implementation running alongside the existing Linux `xdotool` pipeline.
- **OS-specific configuration in `config.json`.** Added support for `"windows"` and `"linux"` sections with sensible defaults for each operating system (e.g. File Explorer, PowerShell, Task Manager on Windows).
- **Interface filtering for local IP detection.** `get_all_ips()` skips virtual/tunnel adapters (`docker*`, `veth*`, `tun`, `wg`, `tailscale`, VM bridges, etc.) and sorts real Wi-Fi/Ethernet adapters first, working on both Linux and Windows.
- **Brute-force throttle on the auth token.** After 10 failed attempts from the same IP within 30 seconds, that IP is locked out for the rest of the window.
- **Startup diagnostics** for cross-network connectivity: the server prints likely causes (Windows Firewall "Public" profile, Linux `ufw`/`firewalld`, router/hotspot AP isolation).
- **Tailscale documentation** (`TAILSCALE_SETUP.md`) for using this across networks that don't share a LAN, or that block device-to-device traffic outright.
