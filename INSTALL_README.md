<p align="center">
  <img src="assets/powerglove-vision-logo.png" alt="PowerGlove Vision" width="680">
</p>

# PowerGlove Vision installation

This guide installs every part of PowerGlove Vision:

1. the camera and vision application on an Arduino UNO Q;
2. the virtual gamepad receiver on a Raspberry Pi/RetroPie console;
3. automatic per-game profile selection for Programs A-I, Bad Street Brawler,
   and Super Glove Ball;
4. the shared Wi-Fi connection and pairing token;
5. optional RetroArch controller mapping and startup configuration.

PowerGlove Vision does not require an original Power Glove or the Bad Street
Brawler cartridge menu. A bare hand works. A plain white or black glove is an
optional tracking aid and contains no electronics.

## What you need

- An Arduino UNO Q. The 4 GB model is recommended.
- A Raspberry Pi running RetroPie and RetroArch.
- A UVC-compatible USB camera. A Razer Kiyo should appear as a standard UVC
  camera.
- An externally powered USB-C hub or dock for the UNO Q and camera.
- A 5 V/3 A supply suitable for the UNO Q.
- A computer running Arduino App Lab.
- A trusted local Wi-Fi or Ethernet network shared by the UNO Q and RetroPie.
- Internet access during the UNO Q's first application start. Its isolated
  Python 3.12 vision environment is downloaded once and then retained in the
  app's persistent `data` directory.

Do not expose ports 55355, 55356, or 8088 to the public internet. Controller
traffic is intended for a trusted local network; it is authenticated but not
encrypted.

## Network layout

The normal data paths are:

```text
Razer Kiyo --USB--> UNO Q --UDP 55355/Wi-Fi--> RetroPie virtual gamepad
                         <--UDP 55356/Wi-Fi-- RetroPie game profile hook

Browser --TCP 8088/Wi-Fi--> UNO Q status and calibration page
```

The defaults assume:

- RetroPie hostname: `retropieconsole.local`
- controller-state port on RetroPie: UDP `55355`
- profile-control port on the UNO Q: UDP `55356`
- UNO Q status page: TCP `8088`

Using `.local` hostnames is preferable to fixed IP addresses. If mDNS is not
available on the network, reserve addresses in the router and use those
addresses in the two configuration files instead.

## Part 1: Prepare the UNO Q

### 1. Install and connect Arduino App Lab

1. Install the current Arduino App Lab release from Arduino.
2. Connect the UNO Q to the computer with a USB data cable.
3. In App Lab, select the UNO Q and complete its initial setup.
4. Give the board a recognizable name.
5. Configure the board to join the same network as the RetroPie console.
6. Apply any board-system or App Lab updates offered before importing
   PowerGlove Vision.

Initial provisioning should be done over USB. Once configured, the UNO Q can
normally be selected and managed over Wi-Fi from App Lab.

### 2. Connect the camera

Connect the powered hub or dock to the UNO Q, then connect the Razer Kiyo to
the hub. An externally powered hub is strongly recommended because a camera
can draw substantially more power than a small passive adapter should supply.

PowerGlove Vision uses automatic camera discovery. It ignores the UNO Q's
internal video-codec devices and waits for a USB camera identifier. The camera
may therefore be connected before or after the app starts.

### 3. Import the App Lab package

Use the release package:

```text
output/app-lab/PowerGlove-Vision-Uno-Q.zip
```

In Arduino App Lab:

1. Choose the option to import an Arduino App from a ZIP file.
2. Select `PowerGlove-Vision-Uno-Q.zip`.
3. Open the imported **PowerGlove Vision** app.
4. Click **Run**.
5. Allow several minutes for the first run. The board installs a private
   Python 3.12 runtime, MediaPipe 0.10.18, and headless OpenCV.
6. Enable **Run at startup** after the first successful initialization.

The package contains both sides of the UNO Q application:

- the Linux vision and networking process;
- the STM32 sketch that drives the 8x13 blue LED matrix.

The first protected Arduino boot display is not replaced. When PowerGlove
Vision takes over, the matrix shows its own loading animation and status.

### 4. Understand the matrix states

- Animated hand: application or hand model is loading.
- `PG`: ready before a specific profile is selected.
- `A` through `I`: cartridge-free Power Glove Program A-I selected.
- `BS`: Bad Street Brawler profile selected.
- `GB`: Super Glove Ball profile selected.
- Pulsing profile: a calibrated hand is actively being tracked.
- Blinking X: no usable camera is connected or the vision worker needs
  attention.

It is normal to see the blinking X if the app is installed without the Kiyo.
The App Lab supervisor remains running and starts the tracker after a camera is
plugged in.

### 5. Locate the UNO Q configuration and pairing token

On first start, the app creates persistent settings at:

```text
data/device.json
```

Its shape is:

```json
{
  "receiver": "retropieconsole.local",
  "token": "a-random-token-created-on-first-start",
  "profile": "bad_street_brawler",
  "glove_color": "none",
  "camera": "auto"
}
```

From a phone or computer on the same network, open:

```text
http://UNO-Q-HOSTNAME.local:8088/setup
```

Enter the RetroPie console hostname, controller port, startup profile, camera,
and optional glove colour, then choose **Save & restart tracker**. Use **Test
console name** to confirm that the name resolves on the local network. The setup
page stays available when the camera is disconnected.

The page never displays the private token. For the initial RetroPie pairing,
use App Lab's file view to open the app's `data/device.json`. If needed, open an
App Lab shell and locate it with:

```sh
find /home/arduino/ArduinoApps -path '*/data/device.json' -print
```

Copy the value of `token` somewhere private; it must be installed on RetroPie
in Part 2. Do not commit `data/device.json`, paste its token into an issue, or
include it in a shared application export.

You can edit this JSON file directly as a recovery option. Supported
`glove_color` values are `none`, `white`, and `black`. Leave `camera` as `auto`
unless troubleshooting a system with several USB cameras. Browser changes
restart the tracker automatically; manual JSON changes require an app restart.

If you select **Generate a new private pairing token** in the browser, copy the
new value from `data/device.json` into `/etc/powerglove/token` on RetroPie and
restart `powerglove-receiver.service` before playing.

## Part 2: Install the RetroPie receiver

The examples below keep the repository in `/opt/powerglove-src` and put its
Python virtual environment in `/opt/powerglove`. This matches the paths used by
the supplied launch-hook scripts.

### 1. Install system requirements

Open a terminal on RetroPie, locally or over SSH:

```sh
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-dev build-essential
sudo modprobe uinput
```

Confirm that the virtual-input device exists:

```sh
ls -l /dev/uinput
```

To load it automatically after reboot:

```sh
printf '%s\n' uinput | sudo tee /etc/modules-load.d/powerglove.conf
```

### 2. Install the repository and Python package

For a public GitHub repository, replace `YOUR-USER` below:

```sh
sudo git clone https://github.com/YOUR-USER/PowerGlove.git /opt/powerglove-src
sudo python3 -m venv /opt/powerglove
sudo /opt/powerglove/bin/python -m pip install --upgrade pip
sudo /opt/powerglove/bin/python -m pip install -e '/opt/powerglove-src[receiver]'
```

If the repository is private or was copied to the Pi another way, substitute
its local path for `/opt/powerglove-src` in the last command.

### 3. Install the pairing token and configuration

Create the protected configuration directory:

```sh
sudo install -d -m 0755 /etc/powerglove
sudo install -m 0644 /opt/powerglove-src/config/games.json /etc/powerglove/games.json
sudo install -m 0644 /opt/powerglove-src/config/launcher.example.json /etc/powerglove/launcher.json
sudo install -m 0600 /dev/null /etc/powerglove/token
sudo nano /etc/powerglove/token
```

Paste only the UNO Q token value into the final file, save it, and exit. There
must be no quotation marks. A trailing newline is harmless.

Edit the launcher settings:

```sh
sudo nano /etc/powerglove/launcher.json
```

Set `uno_q` to the board's `.local` hostname or reserved IP address. For
example:

```json
{
  "uno_q": "arduiain.local",
  "port": 55356,
  "token_file": "/etc/powerglove/token",
  "registry": "/etc/powerglove/games.json",
  "timeout": 0.4
}
```

Do not change `port` unless the UNO Q profile port is changed at the same time.

### 4. Test packets before creating a gamepad

Stop any already-running receiver, then start the diagnostic receiver:

```sh
sudo /opt/powerglove/bin/powerglove-receiver \
  --listen 0.0.0.0 \
  --token "$(sudo cat /etc/powerglove/token)" \
  --dry-run
```

With the Kiyo connected and PowerGlove Vision running, show one hand to the
camera. The console should print controller state. Press `Ctrl+C` when done.

If nothing arrives, verify that both machines are on the same network and that
UDP port 55355 is not blocked.

### 5. Run the receiver at boot

Create `/etc/systemd/system/powerglove-receiver.service`:

```ini
[Unit]
Description=PowerGlove Vision virtual gamepad receiver
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=root
ExecStart=/bin/sh -c 'exec /opt/powerglove/bin/powerglove-receiver --listen 0.0.0.0 --token "$(cat /etc/powerglove/token)"'
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Then enable it:

```sh
sudo chmod 0644 /etc/systemd/system/powerglove-receiver.service
sudo systemctl daemon-reload
sudo systemctl enable --now powerglove-receiver.service
sudo systemctl status powerglove-receiver.service
```

The service runs as root because creating `/dev/uinput` devices normally
requires elevated privileges on RetroPie. An advanced installation may instead
use a dedicated user and a narrowly scoped udev rule.

Confirm that Linux can see the controller:

```sh
grep -A8 -B2 'PowerGlove Vision' /proc/bus/input/devices
```

## Part 3: Configure RetroArch

The receiver creates a Linux gamepad named `PowerGlove Vision`.

1. Start the UNO Q app and connect the camera.
2. Confirm that `powerglove-receiver.service` is active.
3. Open RetroArch's **Settings > Input > RetroPad Binds > Port 1 Controls**.
4. Select `PowerGlove Vision` as the device.
5. Bind D-pad Up/Down/Left/Right, A, B, Start, and Select.
6. Save the controller profile or current RetroArch configuration.

The extra `BTN_TR2` input carries the Bad Street Brawler glove-zap event. A
standard NES core cannot necessarily use that native glove-only action; it is
retained for the planned native Nestopia integration.

If an arcade cabinet already combines several controllers, add PowerGlove
Vision to the existing input merger instead of replacing the cabinet's primary
gamepad configuration.

### Install the games

Copy legally obtained NES images to RetroPie's NES ROM directory, normally:

```text
~/RetroPie/roms/nes/
```

The supplied registry recognizes `.nes`, `.zip`, and `.7z` filenames for Bad
Street Brawler and Super Glove Ball. Emulator support for archive types varies;
an uncompressed `.nes` file is the simplest troubleshooting format.

ROM images are never uploaded to the UNO Q and should not be included in the
GitHub repository. Programs A-I are implemented as PowerGlove Vision profiles,
so Bad Street Brawler does not need to be launched merely to configure another
game.

## Part 4: Enable automatic game profiles

RetroPie calls `runcommand-onstart.sh` when a game starts and
`runcommand-onend.sh` when it exits. PowerGlove Vision uses those hooks to
select a profile and show its acknowledgement on the UNO Q matrix.

### 1. Preserve existing hooks

Do not overwrite existing cabinet scripts. They may control RGB lighting,
trackballs, controller ordering, bezels, or other hardware.

Make the supplied helper scripts executable:

```sh
sudo chmod 0755 /opt/powerglove-src/retropie/runcommand-onstart-powerglove.sh
sudo chmod 0755 /opt/powerglove-src/retropie/runcommand-onend-powerglove.sh
```

Append this line to the cabinet's existing
`/opt/retropie/configs/all/runcommand-onstart.sh`:

```sh
/opt/powerglove-src/retropie/runcommand-onstart-powerglove.sh "$1" "$2" "$3" "$4"
```

Append this line to
`/opt/retropie/configs/all/runcommand-onend.sh`:

```sh
/opt/powerglove-src/retropie/runcommand-onend-powerglove.sh
```

Create either hook file if it does not exist, start it with `#!/bin/sh`, and
make it executable:

```sh
sudo chmod 0755 /opt/retropie/configs/all/runcommand-onstart.sh
sudo chmod 0755 /opt/retropie/configs/all/runcommand-onend.sh
```

### 2. Review the game registry

Profiles are selected using the exact, case-insensitive ROM filename in:

```text
/etc/powerglove/games.json
```

The supplied registry includes:

| Game | Profile |
| --- | --- |
| Bad Street Brawler | `bad_street_brawler` |
| Super Glove Ball | `super_glove_ball` |
| Joust | `program_b` |
| Gyruss | `program_c` |
| Defender II | `program_e` |
| Sesame Street 1-2-3 | `program_f` |
| Gun.Smoke | `program_g` |
| Knight Rider | `program_i` |

Programs A, D, and H are available for additional games. Valid values are
`program_a` through `program_i`, `bad_street_brawler`, and
`super_glove_ball`.

Add the exact ROM basename when a collection uses a different region, revision,
archive type, or naming convention. Unknown games explicitly turn gesture
control off rather than inheriting the previous game's profile.

### 3. Test profile switching manually

From RetroPie:

```sh
sudo /opt/powerglove/bin/powerglove-profile \
  --uno-q arduiain.local \
  --token-file /etc/powerglove/token \
  --profile program_b
```

The command should report an acknowledgement and the matrix should display
`B`. Replace the UNO Q hostname as necessary.

Test gesture-off mode:

```sh
sudo /opt/powerglove/bin/powerglove-profile \
  --uno-q arduiain.local \
  --token-file /etc/powerglove/token \
  --profile off
```

## Part 5: Calibrate and play

Once the camera and tracker are active, open this page from another device on
the same network:

```text
http://UNO-Q-HOSTNAME.local:8088/debug
```

The dashboard displays the camera overlay, game, active profile, tracking
confidence, controller buttons, axes, finger curl, recent gesture events, and
profile source. The root URL redirects here.

1. Stand where the player will normally stand.
2. Keep one hand fully visible with some space around it.
3. Press **Center hand**.
4. Hold the hand still in a comfortable neutral pose during calibration.
5. Move slowly at first and confirm the on-screen landmarks and matrix state.

For a white glove, use a darker background. For a black glove, use a lighter
background. Strong front lighting and a simple background are more important
than glove color.

The setup and dashboard service starts before the camera worker, so both pages
remain available while no usable camera is connected. The dashboard reports
the missing camera and the matrix blinks X until one is attached.

## Firewall rules

Most RetroPie installations do not enable a host firewall. If one is enabled,
allow the following only from the trusted local subnet:

- UDP 55355 inbound to RetroPie;
- UDP 55356 inbound to the UNO Q;
- TCP 8088 inbound to the UNO Q for the status page.

The UNO Q must also be allowed to download packages during its first run.

## Updating

### RetroPie

```sh
cd /opt/powerglove-src
sudo git pull --ff-only
sudo /opt/powerglove/bin/python -m pip install -e '/opt/powerglove-src[receiver]'
sudo install -m 0644 config/games.json /etc/powerglove/games.json
sudo systemctl restart powerglove-receiver.service
```

Back up local changes to `/etc/powerglove/games.json` before replacing it.

### UNO Q

1. Back up the imported app's `data/device.json`.
2. Stop PowerGlove Vision in App Lab.
3. Import the newer `PowerGlove-Vision-Uno-Q.zip` release.
4. Restore the receiver hostname, token, glove hint, and other local settings
   if the new import uses a new app folder.
5. Run the app once and enable **Run at startup** for the new copy.
6. Remove the older app only after the new copy has been verified.

Never publish the backed-up `device.json` or `/etc/powerglove/token`.

## Troubleshooting

### The UNO Q shows a blinking X

- Confirm that the camera is connected through a powered hub.
- Try a different USB cable or hub port.
- Stop and restart PowerGlove Vision in App Lab.
- In an App Lab shell, inspect USB video devices with
  `v4l2-ctl --list-devices` if that utility is installed.
- The app should remain marked running while it waits for a camera.

### First start takes several minutes

This is expected. The app downloads a compatible Python 3.12 runtime and its
ARM64 vision libraries into persistent app data. Later starts reuse them.
Check the App Lab console for download progress and make sure the UNO Q has
internet access and adequate free storage.

### The controller does not appear on RetroPie

```sh
sudo systemctl status powerglove-receiver.service
sudo journalctl -u powerglove-receiver.service -n 100 --no-pager
ls -l /dev/uinput
```

Confirm that the receiver uses `--listen 0.0.0.0`, that the `uinput` module is
loaded, and that the token exactly matches the UNO Q token.

### The controller appears but never moves

- Confirm that the status page shows a detected and calibrated hand.
- Re-run the receiver in `--dry-run` mode.
- Confirm UDP 55355 connectivity from the UNO Q to RetroPie.
- Confirm that `receiver` in `data/device.json` names the correct console.
- Check that a physical controller merger is not filtering the new virtual
  device.

### Profiles do not change when games launch

- Run the manual profile test above.
- Verify UDP 55356 connectivity to the UNO Q.
- Check `uno_q` and `token_file` in `/etc/powerglove/launcher.json`.
- Confirm that the existing RetroPie hooks actually call the supplied helper
  scripts and forward all four start arguments.
- Match the exact ROM basename in `/etc/powerglove/games.json`.

Profile communication failures intentionally do not prevent a game from
launching.

### `.local` names do not resolve

Use router-reserved IP addresses in `data/device.json` and
`/etc/powerglove/launcher.json`, or install/enable mDNS support on the console.
Both devices must be on network segments that permit mDNS and the required
UDP traffic.

## Uninstalling

On RetroPie:

```sh
sudo systemctl disable --now powerglove-receiver.service
sudo rm /etc/systemd/system/powerglove-receiver.service
sudo systemctl daemon-reload
```

Remove the PowerGlove lines from the two RetroPie runcommand hooks. After
backing up any desired custom profiles, the following directories may be
removed manually:

```text
/opt/powerglove
/opt/powerglove-src
/etc/powerglove
```

On the UNO Q, stop PowerGlove Vision, disable **Run at startup**, and remove
the imported app through Arduino App Lab. Its persistent `data` directory
contains the local token and cached Python worker, so export anything needed
before deleting the app.
