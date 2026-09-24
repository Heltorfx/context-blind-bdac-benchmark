# VEIL exhibition

## One-click start

Double-click `Start-Exhibit.cmd`. The launcher only starts `run_server.sh` in
WSL and keeps the server attached to that window. It does not inspect or
configure Windows networking. Open the display or administrator QR page in a
browser, then press `Ctrl+C` in the server window after the event.

The default public URL is `http://192.168.137.1:8766`, which matches the usual
Windows Mobile Hotspot address. To use another address, pass it explicitly:

```powershell
.\Start-Exhibit.ps1 -PublicUrl http://YOUR_ADDRESS:8766
```

The existing Windows-to-WSL port forwarding, if needed for phone access, must
already be configured separately. The launcher does not modify the firewall,
port forwarding, hosts file, or hotspot settings.

From WSL, the two control scripts are:

```sh
bash BDAC/exhibit/reset_server.sh
bash BDAC/exhibit/stop_server.sh
```

`reset_server.sh` clears every wallet, presentation ticket, decision, event and
counter while keeping the initialized cryptographic engine and administrator
link. It refuses to reset while a cryptographic operation is running.
`stop_server.sh` terminates only the VEIL server recorded by `run_server.sh`.

## Manual start

Run inside WSL from `Implementation` with the Sage environment activated:

```sh
pip install qrcode
python -m BDAC.exhibit.server --port 8766 --public-url http://YOUR_WINDOWS_HOTSPOT_IP:8766
```

Wallet: `/`. Public display: `/screen`. Administrator QR page: `/admin-qr`.
All assets are served locally. No Internet is needed once dependencies are installed.

Windows must forward incoming hotspot connections to the WSL server if WSL
uses NAT networking. Configure a port proxy from the Windows hotspot address
to the WSL address on port 8766, and allow that port in the Windows firewall
for the demonstration network. This requires administrator rights. Test from
a real phone before the event; localhost success alone does not test this path.

With Mobile Hotspot enabled, find its IPv4 address in Windows network settings
and run in administrator PowerShell:

```powershell
.\Connect-Hotspot.ps1 -HotspotAddress 192.168.137.1
```

The address above is an example. The script checks that it belongs to this PC,
forwards only port 8766 on that address, and restricts the firewall rule to the
local subnet. Restart the Python server with the printed `--public-url` value.
After the event, remove the route and rule (substitute the actual address):

```powershell
netsh interface portproxy delete v4tov4 listenaddress=192.168.137.1 listenport=8766
Remove-NetFirewallRule -DisplayName 'BDAC Exhibition 192.168.137.1 8766'
```

Each browser receives an opaque HttpOnly session cookie. Credentials, attributes
and software SE keys stay in server memory and disappear on restart. Clearing
the cookie loses access to that wallet. This is a hosted research demonstration,
not a phone hardware wallet. HTTP is intended for a controlled local network.

The implementation runs genuine enrollment, CAPSS issuance and Aurora v2 ZK
presentation. Sixteen random field attributes are enrolled before issuance;
the verifier requests positions 0–3. No real-world attribute certification or
single-redemption policy is claimed. Presentations may be repeated.

All crypto jobs execute serially because the proof backend shares workspace
files. Public events contain no session identifiers or attribute values, but
the demonstration host can observe its hosted wallets and activity timing.
The display shows actual coarse protocol events, not simulated substeps.
# Administrator Review

The wallet shows 16 fictional profile attributes (name, age, birthplace, sex,
height, etc.) and previews the four requested values before consent. These ASCII
values are left-padded with zero bytes to the field element width and are the
actual signed attributes, not display-only aliases. The progress indicator shows
the current operation and elapsed time, without an estimated percentage.
A generated presentation produces a QR on the credential card,
valid for ten minutes. Scan it using the administrator phone's native camera.

First open the private administrator URL printed at server startup on that phone.
Keep this link private: it grants desk approval access. The browser remembers this
access on the same origin. The visitor QR alone does not grant administrator access.
The administrator sees only the four disclosed values, the cryptographic result,
and Accept/Decline controls. The visitor sees the decision on their own screen.

Currently the existing protocol call generates AND cryptographically verifies the
Aurora proof before creating the QR receipt. Scanning retrieves this verified
receipt; it does not rerun the verifier. Desk acceptance is a separate decision.
Each receipt can be decided once, but the credential can generate new presentations.
Restarting resets wallets, receipts, and the administrator link.

This remains a trusted-local-network demonstration over HTTP, not a production
authentication service. Administrators must keep their link and browser private.
