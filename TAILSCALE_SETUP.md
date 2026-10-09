# Setting up Tailscale for OLED Remote

This lets you use OLED Remote from your phone even when it's not on
the same physical network as your PC — different Wi-Fi, mobile data,
a hotel network, wherever. Tailscale creates a private mesh network
("tailnet") between your own devices; each one gets a stable private
IP that the others can reach directly.

It's free for this use case: the Personal plan supports up to 6 users
and unlimited devices per user, at no cost.

## 1. Create a Tailscale account

Go to [tailscale.com](https://tailscale.com) and sign up (Google,
Microsoft, GitHub, or email). No card required for the free plan.

## 2. Install on your PC (Linux Mint / Ubuntu-based)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

The second command prints a login URL — open it in a browser, sign in
with the account from step 1, and approve the device.

Verify it worked:
```bash
tailscale status
tailscale ip -4
```

## 3. Install on your phone (Android)

1. Install **Tailscale** from the Play Store.
2. Open it and sign in with the **same account** used on the PC.
3. Accept the VPN permission prompt (Tailscale runs as a VPN profile
   under the hood — this is expected and normal).
4. Toggle Tailscale **on**.

## 4. Confirm both devices see each other

On the PC:
```bash
tailscale status
```
Both the PC and phone should be listed as connected.

## 5. Connect to OLED Remote over Tailscale

Start the server as usual on the PC:
```bash
python3 my_remote.py
```
Ignore the LAN IP it prints. Instead, get the Tailscale IP:
```bash
tailscale ip -4
```
On the phone, open:
```
http://<tailscale-ip>:5001
```
This works regardless of what network the phone is on, as long as
both devices have any internet connection and Tailscale is turned on.

## 6. (Optional) Use a name instead of an IP

1. Go to the [Machines page](https://login.tailscale.com/admin/machines)
   of the admin console.
2. Rename your PC (e.g. `mint-pc`) via its `⋮` menu → edit machine
   name.
3. Go to the **DNS** tab and confirm **MagicDNS** is enabled (usually
   on by default).
4. Now you can use `http://mint-pc:5001` from your phone instead of
   the numeric IP.

## 7. (Recommended) Disable key expiry on the PC

By default, each device's Tailscale key expires every 180 days,
requiring you to re-authenticate. For the PC running the server, it's
worth disabling this so the remote doesn't silently stop working:

1. Go to the [Machines page](https://login.tailscale.com/admin/machines).
2. Find the PC, open its `⋮` menu, select **Disable Key Expiry**.

This is available on the free plan. If a key *does* expire, just run
`sudo tailscale up` on the PC again to re-authenticate.

## Troubleshooting

- **Phone doesn't show up in `tailscale status`** — make sure you
  logged into the *exact same* Tailscale account on both devices, not
  a newly created second account.
- **`mint-pc` name doesn't resolve** — confirm MagicDNS is on (step 6)
  and that you typed the name exactly as set in the admin console.
- **Connects but the page won't load** — check the local firewall on
  the PC (`sudo ufw allow 5001/tcp` on Linux) isn't blocking the port
  even over the Tailscale interface.
