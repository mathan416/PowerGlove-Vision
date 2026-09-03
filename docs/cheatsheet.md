<p align="center">
  <img src="../assets/powerglove-vision-logo.png" alt="PowerGlove Vision" width="680">
</p>

# PowerGlove Vision — Current Setup Cheat Sheet

This page describes the currently deployed development setup. It intentionally
does not contain the private pairing token.

## UNO Q

| Item | Current value |
| --- | --- |
| Board name | `ArduIain` |
| Network hostname | `arduiain.local` |
| Current IPv4 address | `10.0.2.105` |
| Board | Arduino UNO Q |
| App Lab app | PowerGlove Vision |
| Camera | Razer Kiyo, configured as `auto` |
| Configured receiver | `10.0.2.57` (`retropieconsole.local` when mDNS is available) |
| Startup profile | Super Glove Ball |

Prefer the `.local` hostname in bookmarks and configuration. The numeric IP is
assigned by the network and may change.

## Browser URLs

| Purpose | URL |
| --- | --- |
| Live debug dashboard | <http://arduiain.local:8088/debug> |
| Offline gesture lessons | <http://arduiain.local:8088/learn> |
| Friendly connection setup | <http://arduiain.local:8088/setup> |
| Secure pairing setup | <https://arduiain.local:8443/setup> |
| Root (redirects to dashboard) | <http://arduiain.local:8088/> |
| Machine-readable status | <http://arduiain.local:8088/status> |
| Camera stream | <http://arduiain.local:8088/stream> |
| GitHub repository | <https://github.com/mathan416/PowerGlove-Vision> |

If `.local` discovery is unavailable, replace `arduiain.local` with the current
UNO Q IP address, currently `10.0.2.105`.

## Network ports

| Port | Protocol | Direction | Use |
| --- | --- | --- | --- |
| `8088` | TCP | Browser → UNO Q | Setup, dashboard, status and camera stream |
| `8443` | TCP/TLS | Browser → UNO Q | Secure RetroPie pairing |
| `55355` | UDP | UNO Q → RetroPie | Controller-state packets |
| `55356` | UDP | RetroPie → UNO Q | Authenticated profile selection and acknowledgement |
| `55357` | TCP/TLS | UNO Q → RetroPie | Temporary one-time pairing helper |

Keep these ports limited to the trusted local network. Do not expose them to
the public internet.

## RetroPie defaults

| Item | Value |
| --- | --- |
| Console hostname | `retropieconsole.local` |
| Virtual controller | `PowerGlove Vision` |
| Pairing-token file | `/etc/powerglove/token` |
| Game registry | `/etc/powerglove/games.json` |
| Launcher settings | `/etc/powerglove/launcher.json` |
| Receiver service | `powerglove-receiver.service` |
| Delayed-start timer | `powerglove-receiver.timer` (45 seconds after boot) |
| UNO Q shutdown watcher | `powerglove-system-shutdown.path` (`enabled`, `active`) |
| Shutdown readiness marker | `data/.shutdown-enabled` |

The token in `/etc/powerglove/token` must exactly match the token stored in the
UNO Q app's `data/device.json`. Never paste that value into GitHub, screenshots,
logs or this cheat sheet.

The shutdown watcher, readiness marker, Dashboard and Setup buttons, and API
rejection safeguards were verified on September 3, 2026. **Stop controller**
leaves the UNO Q running; **Shutdown system** powers Linux off and requires
power to be restored or cycled before restart.

## Local development files

| Purpose | Path |
| --- | --- |
| Git working copy | `/Users/mathan/Developer/PowerGlove` |
| Installation guide | `/Users/mathan/Developer/PowerGlove/docs/INSTALL_README.md` |
| Gameplay guide | `/Users/mathan/Developer/PowerGlove/docs/GAMEPLAY_GUIDE.md` |
| Programs A–I reference | `/Users/mathan/Developer/PowerGlove/docs/bad-street-brawler-programs.md` |
| UNO Q App Lab installation ZIP | `/Users/mathan/Developer/PowerGlove/output/app-lab/PowerGlove-Vision-Uno-Q.zip` |
| Gesture profiles | `/Users/mathan/Developer/PowerGlove/config/profiles.json` |
| Automatic game mapping | `/Users/mathan/Developer/PowerGlove/config/games.json` |

## Deploy over Wi-Fi

The Mac is authorized to maintain the UNO Q using its SSH key. From the local
repository, deploy application updates and restart PowerGlove Vision with:

```sh
cd /Users/mathan/Developer/PowerGlove
scripts/deploy-uno-q-wifi.sh
```

One-time installation of the Dashboard and Setup shutdown control:

```sh
cd /Users/mathan/Developer/PowerGlove
scripts/install-uno-q-shutdown-helper.sh arduino@arduiain.local
```

The helper asks for the UNO Q password through the terminal. **Shutdown
system** gracefully powers off Linux; restore or cycle power to start the UNO Q
again.

This preserves the private `data/device.json`. No password is stored in the
repository. USB is only needed as a recovery option or for a passwordless blue
matrix firmware upload; App Lab can also perform a wireless firmware update by
asking for the board password privately.

Verify key access before deploying:

```sh
ssh -o BatchMode=yes arduino@arduiain.local hostname
```

## Pair the current RetroPie

Recommended one-time-code method:

1. On RetroPie, run `sudo /opt/powerglove/bin/powerglove-pair`.
2. Open <https://arduiain.local:8443/setup> on the trusted local network.
3. Enter `retropieconsole.local` and the 20-character code.
4. Prepare pairing and compare the matrix `ID` with the browser certificate's
   SHA-256 fingerprint prefix.
5. Enter the matrix `PN` digits and complete pairing.
6. Confirm `powerglove-receiver.service` is active.

Username/password pairing is available on the same secure page. Choose
**Prepare password pairing** before entering the password, perform the same
matrix certificate check, and then complete the one-time SSH operation. The
password is not stored.

## Quick health checks

Open the status endpoint in a browser or run:

```sh
curl -sS http://arduiain.local:8088/status
```

Healthy tracking should report:

```json
{
  "camera_available": true,
  "worker_running": true,
  "detected": true,
  "calibrated": true
}
```

Useful RetroPie checks:

```sh
sudo systemctl status powerglove-receiver.service
sudo systemctl status powerglove-receiver.timer
sudo journalctl -u powerglove-receiver.service -n 100 --no-pager
grep -A8 -B2 'PowerGlove Vision' /proc/bus/input/devices
```

Run the local software tests:

```sh
cd /Users/mathan/Developer/PowerGlove
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Camera troubleshooting

The Razer Kiyo must be connected to the UNO Q through an externally powered
USB-C hub. Connect to App Lab over Wi-Fi while the UNO Q is acting as the USB
host. A camera connected to the Mac is not visible inside the UNO Q app.

If the UNO Q lists only `qcom-venus-encoder` and `qcom-venus-decoder`, the Kiyo
is not visible to Linux. Check the powered hub, reconnect the Kiyo, wait several
seconds, and watch the dashboard. The supervisor retries automatically; do not
cycle through camera indexes when no UVC device exists.

## Website images

- `docs/images/debug-dashboard.png`
- `docs/images/learn-page.png`
- `docs/images/setup-page.png`

## Profiles

The Dashboard can change the active profile for the current session, and Setup
can choose the profile used at startup:

- Bad Street Brawler
- Super Glove Ball
- Power Glove Programs A–I
- Gestures off

RetroPie launch hooks select the registered profile for each recognized ROM.
Launching an unregistered game safely selects **Gestures off**. Automatic profile
selection currently applies only to NES and Famicom games; launching another
system also turns gestures off.

### Useful off-script starting points

| Program | Good first experiment | Controls and tradeoff |
| --- | --- | --- |
| A | Pinball and games built around short bursts | Finger actions suit flippers, wrist movement can suit tilt, and pullback toggles a control. It does not provide an ordinary D-pad. |
| D | Challenge runs and games where reversed movement is fun | Every direction is reversed; thumb and index actions provide A and B. |
| H | General NES and Famicom experiments | Hand movement provides a conventional D-pad and thumb/index actions pulse A and B. Pulses are a poor fit for actions that must be held continuously. |

### Quick off-script test

1. Launch an unregistered NES or Famicom game. Confirm that PowerGlove Vision
   reports **Gestures off**.
2. Open the UNO Q **Dashboard** and choose Program A, D, H, or another profile.
3. Wait for vision to start and ask for centering.
4. Center your hand, select **Start controller**, and test movement and actions.
5. Stop the controller before changing profiles or games.

This temporary choice is ideal for discovery. It does not change the automatic
game registry or the startup profile saved in Setup. While **Gestures off** is
selected, the camera and MediaPipe tracker are closed and the UNO Q matrix runs
its animated glove attract sequence.

### Keep a working combination

Add the ROM's exact basename, including `.nes`, `.zip`, or `.7z`, to the `games`
object in `/etc/powerglove/games.json`. Preserve all existing entries. For
example:

```json
{
  "games": {
    "YOUR EXACT GAME FILENAME.nes": "program_h"
  }
}
```

Check the edited file before testing:

```sh
sudo python3 -m json.tool /etc/powerglove/games.json >/dev/null
```

Restart the game so its launch hook selects the newly registered profile. See
`docs/GAMEPLAY_GUIDE.md` for the illustrated play and experimentation guide and
`docs/bad-street-brawler-programs.md` for complete Program A–I controls.

For Super Glove Ball, hand position controls the D-pad, index curl is A, thumb
curl is B, a V sign held for about 0.7 seconds is Start, and a thumbs-up with
the other fingers closed is Select.

## Startup behaviour

In Arduino App Lab, the current PowerGlove Vision project must show the
`DEFAULT` badge. The app then starts automatically after the UNO Q boots. The
dashboard becomes available before the camera worker is ready, which makes it
the best first place to diagnose startup or camera problems.

On RetroPie, direct boot enablement of `powerglove-receiver.service` is
disabled. `powerglove-receiver.timer` starts it after 45 seconds so
EmulationStation initializes before the virtual controller appears. This
helps prevent frontend pauses and conflicts with other USB devices, including
the BitPixel display, when the receiver starts too early.

App Lab should contain one active `powerglove-vision` installation. Keep that
copy set as the default/autostart app so the dashboard returns after every UNO
Q reboot. The Wi-Fi deployment script reapplies this designation.
