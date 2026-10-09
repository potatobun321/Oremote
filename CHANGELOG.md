# Changelog

Fixes and hardening made to the original `my_remote.py` / README.

## Fixed

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

- **Interface filtering for local IP detection.** `get_all_ips()` now
  skips virtual/tunnel adapters (`docker*`, `veth*`, `tun`, `wg`,
  `tailscale`, VM bridges, etc.) and sorts real Wi-Fi/Ethernet adapters
  first, so the URL printed at startup is reliably the one your phone
  can actually reach — instead of occasionally pointing at a dead
  virtual interface that happened to list first.
- **Brute-force throttle on the auth token.** After 10 failed attempts
  from the same IP within 30 seconds, that IP is locked out for the
  rest of the window. The token is the only thing gating shell
  execution, so this reduces the blast radius of naive guessing.
- **Startup diagnostics** for cross-network connectivity: the server
  now prints likely causes (Windows Firewall "Public" profile, Linux
  `ufw`/`firewalld`, router/hotspot AP isolation) if the phone can't
  reach it on a network other than home.
- **Tailscale documentation** (`TAILSCALE_SETUP.md`) for using this
  across networks that don't share a LAN, or that block
  device-to-device traffic outright.
