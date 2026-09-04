<p align="center">
  <img src="assets/powerglove-vision-logo.png" alt="PowerGlove Vision" width="760">
</p>

# PowerGlove Vision

PowerGlove Vision lets you play RetroPie games by moving your hand in front of
a camera connected to an Arduino UNO Q. Use your bare hand or a plain glove;
there are no glove electronics to build. The UNO Q tracks your movements and
sends controller input to a Raspberry Pi, where RetroArch sees a virtual
gamepad named **PowerGlove Vision**.

The project includes eleven profiles: nine reusable Programs A–I and dedicated
controls for Bad Street Brawler and Super Glove Ball. RetroPie can select a
profile automatically when you launch a registered game. Glove Academy mode lets you
practise without sending input to the cabinet.

The cabinet currently uses `lr-fceumm` as its default NES emulator.
`lr-nestopia` has not been tested with PowerGlove Vision. Native Power Glove
support remains planned work. The software preserves
analogue and finger measurements for that future integration, but the current
gamepad path does not provide every original glove feature.

## Choose a guide

### User manuals

| You want to… | Read… |
| --- | --- |
| Install both devices and play your first game | [Installation Guide](docs/INSTALL_README.md) |
| Find a command or connection reminder | [Quick Reference](docs/cheatsheet.md) |
| Learn a game's gestures and try a short challenge | [Game and gesture guide](docs/GAMEPLAY_GUIDE.md) |
| Choose or experiment with Programs A–I | [Programs A–I manual](docs/bad-street-brawler-programs.md) |
| Recognize matrix animations and letters | [Matrix display guide](docs/MATRIX_GUIDE.md) |

### Technical documentation

| You want to… | Read… |
| --- | --- |
| Understand components and data flows | [Architecture](docs/ARCHITECTURE.md) |
| Change settings or look up command flags | [Configuration Reference](docs/CONFIGURATION_REFERENCE.md) |
| Understand network and pairing boundaries | [Security policy](docs/SECURITY.md) |
| Change the project or its documentation | [Contributing guide](docs/CONTRIBUTING.md) |
| Check dependency provenance or release history | [Third-party components](docs/THIRD_PARTY_COMPONENTS.md) and [Changelog](docs/CHANGELOG.md) |

## Quick start

Prepare your UNO Q with Arduino App Lab and use an existing RetroPie installation.
Connect both to the same trusted network and attach the camera through a powered
USB hub. Keep a physical controller available for RetroArch setup.

The commands in the Installation Guide select the latest published stable release.
Use the same release on both devices. Download `install-uno-q.sh` and
`install-retropie.sh` from that published
[release](https://github.com/mathan416/PowerGlove-Vision/releases). Run the first
on the UNO Q and the second on RetroPie as your normal login user. Each verifies
its package and requests sudo access when needed. The UNO installer includes
the Arduino sketch, early-start helper, and shutdown helper; no separate App Lab
import or helper installation is needed.

Follow the [Installation Guide](docs/INSTALL_README.md) for copyable commands,
pairing, calibration, and your first game. Both scripts also support `--check`
and repeatable updates while preserving personal settings. Installer assets
must be published before the release download commands become available.

## Controls

Calibration records the resting hand position that the app treats as the
centre of movement. Move away from that position to give a direction and
return to it to release that direction. Recalibrate after moving the camera or
changing your playing position. Some profiles replace ordinary hand movement
with wrist steering or other controls, as shown below.

Across the profiles, hold a **V sign** for about 0.7 seconds to send Start and
a **thumbs-up with the other fingers closed** to send Select. These poses
suppress A/B attacks; some profiles can still generate directional or auxiliary
input, so keep your hand near its resting position while using them.

### Programs A–I

These reusable mappings produce ordinary NES controls. You do not need to
launch Bad Street Brawler first. The table describes controller output; its
effect depends on the game. A pulsed button repeatedly presses and releases.

| Program | Movement | Actions and special gestures |
| --- | --- | --- |
| A — Pinball | Ordinary movement is disabled. | Index curl sends A; thumb curl sends Up; wrist roll sends B. Pulling back toggles combined flippers. |
| B — Joust | Move your hand left or right. | Index or middle curl pulses A; thumb curl holds B. |
| C — Gyruss | Roll your wrist left or right. | A straight index finger holds A; pulling back sends B. Use the game's Attack Control B mode. |
| D — Challenge | All four hand-movement directions are reversed. | Thumb curl sends A; index curl sends B. |
| E — Defender II | Move your hand in four directions. | Thumb curl sends A; wrist roll sends B; ring-finger curl rapidly alternates left and right. |
| F — Sesame Street | Ordinary directional output is disabled. | Moving an open hand away from centre sends A; closing all fingers sends B. |
| G — Gun Smoke | Move your hand in four directions; wrist roll adds left or right. | Index curl sends A; pushing forward sends B. Combine them for A+B. Thumb and ring-finger curl together suppress D-pad and A/B output. |
| H — General | Move your hand in four directions. | Index curl pulses A; thumb curl pulses B. |
| I — Knight Rider | Roll your wrist to steer; lower your hand to brake. | Index curl sends Up for acceleration; pushing sends Up+A for turbo; thumb curl sends B. |

Programs A, D, and H have no default ROM assignment. Choose one on Dashboard
to try it, then register the exact game filename if you want automatic
selection. The [Programs manual](docs/bad-street-brawler-programs.md) includes
illustrations; the [Game and gesture guide](docs/GAMEPLAY_GUIDE.md) adds objectives and tips.

### Bad Street Brawler

| Gesture | Controller output |
| --- | --- |
| Move your hand left, right, up, or down | Corresponding D-pad direction |
| Curl your thumb | Pulsed B |
| Curl your middle finger | A+B |
| Roll your wrist left or right | A plus that direction |
| Push toward the camera | Glove Zap: short simultaneous Left + Right pulse |

Push toward the camera for Glove Zap, then return to your starting distance
before trying again. Bad Street Brawler needs its game-specific emulator setting;
see the [configuration reference](docs/CONFIGURATION_REFERENCE.md#bad-street-brawler-glove-zap).

### Super Glove Ball

| Gesture | Controller output |
| --- | --- |
| Move your hand left, right, up, or down | Corresponding D-pad direction |
| Curl your index finger | A |
| Curl your thumb | B |

The protocol also carries hand position, estimated depth, wrist roll, and
finger measurements for future native-glove support.

## Use the web interface

| Page | What it does |
| --- | --- |
| Dashboard, `/dashboard` | Shows the camera and generated inputs; selects the current profile and starts or stops delivery. |
| Glove Academy, `/learn` | Provides twelve practice lessons and guided gesture tuning, with game input paused. |
| Help, `/help` | Opens the local manuals and PDFs; **This cabinet** shows current connection details. |
| Setup, `/setup` | Saves connection, camera, and startup settings; the Games section edits RetroPie mappings with backup and restore. Pairing requires HTTPS on port 8443. |

With **Gestures off** selected, the camera stays closed. Choose an active profile
or open Glove Academy to begin. Wait for the camera view before practicing or
playing; starting immediately after a reboot can take longer.

**Stop controller** pauses delivery while leaving active tracking available.
**Gestures off** closes the camera. **Shutdown** requests a Linux halt, but
the tested UNO Q restarts afterward. A disappearing website is not proof that
it is safe to remove power. See the installation guide before using Shutdown.

![Dashboard showing the selected profile and controller readings](docs/images/debug-dashboard.png)

The screenshots below show the current interface. Camera imagery is blurred for privacy.

![Glove Academy in Tune mode, with thresholds below the blurred camera](docs/images/tune-page.png)

In **Glove Academy**, switch on **Tune gestures** to adjust sensitivity. The UNO Q shows
a scanning **T** during tuning and a matching scanning **L** during ordinary practice. Both modes pause game input.

Tuning uses three recordings of three seconds each: open hand, gesture, open hand.
Optional **Set up my hand** uses open hand, gentle fist with the thumb outside,
open hand to measure all five fingers. Preview before saving. Saved Activation
and Release thresholds apply in gameplay across profiles. **Glove Zap** and
**Pull Back** have separate practice lessons and tuning controls; movement tuning
ends by returning to the starting position and camera distance.

![Games editor in the lower part of Setup](docs/images/games-section.png)

Scroll down **Setup** to **Games** to map exact ROM filenames to profiles.
Saving affects the next game launch, not the game already running.

## Maintain or extend the project

Use the [Installation Guide's maintenance section](docs/INSTALL_README.md#updates-and-checks)
for updates, and the [Configuration Reference](docs/CONFIGURATION_REFERENCE.md)
for settings and all command options. The [Contributing guide](docs/CONTRIBUTING.md)
covers tests, documentation, package verification, and releases. Printable
editions are stored in [output/pdf/](output/pdf/).

PowerGlove Vision is an independent project licensed under the [MIT License](LICENSE).
Nintendo, NES, Power Glove, and the named games belong to their respective
owners. Third-party software and models retain their own terms, documented in
[Third-party components](docs/THIRD_PARTY_COMPONENTS.md).
