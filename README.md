<p align="center">
  <img src="assets/powerglove-vision-logo.png" alt="PowerGlove Vision" width="760">
</p>

# PowerGlove Vision

**Current project version: 0.4.0; public candidate: v0.4.0-rc.1.** This candidate promotes the tested
MediaPipe efficiency work: newest-frame capture, four inference threads,
30-fps-first camera negotiation, off-thread lightweight preview rendering, and
Latest-coordinate native movement with guarded reacquisition. Optional,
capability-checked camera latency and exposure choices are available without changing
the compatible defaults. Update the
Controller and RetroPie together using the [installation guide](docs/INSTALL_README.md).

PowerGlove Vision lets you play RetroPie games by moving your hand in front of
a camera connected to the **PowerGlove Vision Controller**, built on an Arduino
UNO Q. Use your bare hand or a plain glove; there are no glove electronics to
build. The PowerGlove Vision Controller tracks your movements and
sends controller input to a Raspberry Pi, where RetroArch sees a virtual
gamepad named **PowerGlove Vision**.

The project includes eleven profiles: nine reusable Programs A–I and dedicated
controls for Bad Street Brawler and Super Glove Ball. RetroPie can select a
profile automatically when you launch a registered game. Glove Academy teaches
hand movements and gestures through sixteen guided lessons, with camera feedback,
saved progress for each player, and a **Glove Master** award for completing them all.
Learning mode lets you practise without sending input to the cabinet. Its optional Pixel Pal-guided
personalization wizard adjusts recognition to a player's hand without retraining
the model, changing game mappings, or exposing raw thresholds during normal use.
The local Play page adds a camera-controlled Rock Paper Scissors match against
Pixel Pal without requiring RetroPie.

The Dashboard's **Start controller** choice is retained across Controller application
and system restarts as an armed preference. Armed does not mean that controls are
always being sent: a registered RetroPie launch maintains a short renewable game
session only while RetroArch is running. Controller delivery resumes after a Controller
restart when that session is still live, then returns to neutral when the game ends,
the session becomes stale, or an unregistered game is launched. **Stop controller**
remains sticky until the player explicitly starts it again. Manual Dashboard profile
selection remains available for testing outside the registered-game flow.

The cabinet supports two Super Glove Ball paths. `lr-fceumm` is the complete,
standard-joystick fallback and remains the safe default. The separately named
`lr-nestopia-powerglove` core supplies native absolute X/Y and Z coordinates plus
open-hand, closed-hand/fist, and index-point states. Exact-ROM traces and
deterministic headless tests confirm their packet bytes alongside detection,
Start, four-direction activation/release, small continuous movement, and safe
neutralization. Live cabinet play now confirms every implemented Super Glove
Ball action: native Start, open-hand release/throw, closed-hand grab/catch,
index-point Robo-Bullet fire, and fist-plus-forward Power Punch. Corrected Y
orientation and full-field X/Y movement are also playable. Movement still has
noticeable latency to refine. Native wrist rotation and the remaining unused
packet button fields stay neutral until exact-ROM testing gives them a purpose;
they are not missing from the game actions confirmed in the completed session.

Choose **Setup → Matrix attract mode** to keep the idle animation On, Dim it,
or turn it Off except for faint connection pixels. This does not change game
displays, T, L, or gesture recognition. The setting saves without a tracker restart. Off mode has separate app, console-service, authenticated-console, and Networking pixels; the fourth reports a physical Wi-Fi or Ethernet link, including USB dock Ethernet. Setup distinguishes unavailable telemetry from disconnection. Updating the host sampler enables Ethernet detection without a new matrix firmware format.

Setup starts with four labelled status markers matching the Off-mode pixels: Controller app, console service, authenticated response, and Networking. Green means confirmed, red means disconnected or not confirmed, and grey means unknown. Tracking, controller output, and the saved console appear alongside them. Both pairing methods require the approval PIN displayed on the Controller matrix.

Setup places **Players** below Controller status, followed by **Matrix attract
mode**, **Connection and startup**, guided pairing, Games, and the optional
statistics preference. Select **Save settings**
before pairing; the three steps use the saved console address: choose a method,
confirm the Controller certificate and matrix PIN, then enter the RetroPie code
or SSH credentials. Both methods remain available. After selecting **Pair with RetroPie**,
a visible **Pairing in progress** panel leads to **Pairing complete** or an actionable error. Expiry and submitted failures
require fresh confirmation. Controller Start/Stop and shutdown are on Dashboard.
**Check console address** tests name resolution; use a running game to verify delivery.

When a submitted pairing attempt finishes, the matrix releases the approval PIN and resumes its normal display. When idle, the glove animation follows your On, Dim, or Off attract setting; active game and status displays still take priority.

The [Changelog](docs/CHANGELOG.md) retains the completed Setup review and release
evidence instead of maintaining a second history. Player calibration, complete
backups, background hostname refresh, independent Networking indication, signed
controller sessions, and web-module cleanup are implemented. Controller transport
requires matching version-2 software on both computers; follow the
[coordinated upgrade instructions](docs/CONFIGURATION_REFERENCE.md#signed-controller-transport-and-upgrades).

Manage players and backups in **Setup → Players**. Select the active player on Dashboard or in Glove Academy; that selection applies to both practice and gameplay. Dashboard combines the game name and session status in one Game card.

On Dashboard, **Center hand** saves the resting reference for the selected player. If that player needs centering, guidance appears beside the controls before you can start controller output.

## Choose a guide

### User manuals

| You want to… | Read… |
| --- | --- |
| Install both devices and play your first game | [Installation Guide](docs/INSTALL_README.md) |
| Choose a camera, frame rate, or exposure setting | [Camera Guide](docs/CAMERA_GUIDE.md) |
| Find a command or connection reminder | [Quick Reference](docs/cheatsheet.md) |
| Learn a game's gestures and try a short challenge | [Game and gesture guide](docs/GAMEPLAY_GUIDE.md) |
| Choose or experiment with Programs A–I | [Programs A–I manual](docs/bad-street-brawler-programs.md) |
| Join Pixel Pal's suspiciously well-fingered scavenger hunt | [Game and gesture guide](docs/GAMEPLAY_GUIDE.md) and [Programs A–I manual](docs/bad-street-brawler-programs.md) |
| Recognize matrix animations and letters | [Matrix display guide](docs/MATRIX_GUIDE.md) |

### Technical documentation

| You want to… | Read… |
| --- | --- |
| Get the complete project at a glance | [Project overview PDF](output/pdf/PowerGlove-Vision-Overview.pdf) |
| Understand components and data flows | [Architecture](docs/ARCHITECTURE.md) |
| Understand joystick versus native glove input | [Native emulation explained](docs/NATIVE_EMULATION_EXPLAINED.md) |
| Review Super Glove Ball packet and gameplay evidence | [Native compatibility record](docs/super-glove-ball-native.md) |
| Change settings or look up command flags | [Configuration Reference](docs/CONFIGURATION_REFERENCE.md) |
| Review measured native and FCEUmm direction response | [Direction-response benchmark](docs/direction-response-benchmark.md) |
| Review movement-filter evidence and experiments | [Motion smoothing analysis](docs/motion-smoothing-analysis.md) |
| Measure native X/Y or isolate it from Super Glove Ball behavior | [Native movement validation](docs/direction-response-benchmark.md#direct-output-dot-test) |
| Understand network and pairing boundaries | [Security policy](docs/SECURITY.md) |
| Change the project or its documentation | [Contributing guide](docs/CONTRIBUTING.md) |
| Check dependency provenance or release history | [Third-party notices](THIRD_PARTY_NOTICES.md) and [Changelog](docs/CHANGELOG.md) |

### Pixel Pal's Extra-Digit Hunt

Pixel Pal has discovered that a few illustrated gloves left the art department
with a generous interpretation of hand anatomy. Naturally, this is now a game.

Count every illustrated hand showing five fingers plus a thumb. Count each
appearance, even when the same artwork returns. Pixel Pal has tucked the answers
at the back of the two illustrated guides and behind a reveal in built-in Help,
so there are no spoilers here.

An automated documentation check keeps the answers synchronized with the art.
The art itself remains untouched in the interests of arcade archaeology - and
because it is far too funny to fix.

The web footer shows exact software and running matrix firmware identities.
Glove Academy supports twelve player presets, saved lesson progress, and portable
version-2 hand-setup backups containing name, personal and effective sensitivity, software identity, and per-player calibration. Selecting a player immediately loads their sensitivity, progress, and saved center, with output paused. Use **Center hand** for new players or after changing the physical setup. Version-1 portable backups are no longer accepted. Navigation
and controls adapt to phone and tablet widths.

## Quick start

Prepare the PowerGlove Vision Controller with Arduino App Lab and use an existing RetroPie installation.
Connect both to the same trusted network and attach the camera through a powered
USB hub. Keep a physical controller available for RetroArch setup.

The commands in the Installation Guide select the latest published stable release.
Use the same release on both devices. Download `install-uno-q.sh` and
`install-retropie.sh` from that published
[release](https://github.com/mathan416/PowerGlove-Vision/releases). Run the first
on the Controller and the second on RetroPie as your normal login user. Each verifies
its package and requests sudo access when needed. The UNO installer includes
the Arduino sketch, early-start helper, shutdown helper, and guarded USB-camera
recovery helper; no separate App Lab import or helper installation is needed.

Follow the [Installation Guide](docs/INSTALL_README.md) for copyable commands,
pairing, calibration, and your first game. Both scripts also support `--check`
and repeatable updates while preserving personal settings. The release-owned
`config/profiles.json` baseline is backed up and replaced, while calibration and
personal tuning under `data/` remain in place. Installer assets
must be published before the release download commands become available.

When gestures are off, the matrix plays a lightning-and-glove animation with
curling fingers, a travelling spark, and a soft grayscale glow. See the
[Matrix display guide](docs/MATRIX_GUIDE.md); the revised loop requires updated
matrix firmware.

The tested shared baseline includes responsive `0.28` activation and `0.14`
release thresholds, calibrated native X/Y reach with an 8% edge margin, and
**Latest coordinate** as the native movement default. It sends each newest
valid, reach-clamped palm position directly during continuous tracking. After a
brief MediaPipe dropout, one contradictory or unusually distant reacquisition
may be held for the next fresh result; strongly aligned forward movement remains
immediate. This guard does not predict, smooth, or overshoot. Latest coordinate
is the only live native X/Y behavior. The selected camera frame's capture time
and MediaPipe Hands remain authoritative for palm landmarks, finger curls, and
gestures. The earlier bounded and optical-flow experiments are archived in the
source tree for research and are no longer live movement options. These are
suitable starting values for
every installation. A neutral calibration is different: it records
the palm center, apparent hand size, wrist angle, and resting jitter for one
camera and playing position, so the installer never substitutes another
person’s recorded coordinates for yours.

Install the same release on the Controller and RetroPie. Automatic game-session resume
depends on the current Controller worker and current RetroPie launch hook being present
together; mixed old/new installations continue to fail safe but cannot provide the
renewable session behavior.

When a registered Super Glove Ball ROM is present, the RetroPie installer offers
to build the optional native core locally from pinned GPLv2 Nestopia source. If
you decline, nothing changes and FCEUmm remains available. If you accept, both
cores appear in RetroPie's per-ROM launch menu; FCEUmm stays selected until you
choose the native entry. The project does not distribute ROMs or a compiled
Nestopia core in its ordinary installation archive.

## Controls

Calibration records the resting hand position that the app treats as the
centre of movement. Move away from that position to give a direction and
return to it to release that direction. Recalibrate after moving the camera or
changing your playing position. Direction activation and release are shared by
all FCEUmm profiles and automatically rise above measured resting-hand jitter;
you do not normally calibrate each direction. Some profiles replace ordinary hand movement
with wrist steering or other controls, as shown below.

Calibration accepts 24 geometrically valid hand observations. MediaPipe Hands'
reported score identifies handedness certainty, not landmark or position
confidence, so it is shown diagnostically but is not used as a false quality
gate. The whole hand must still be detected with usable palm geometry.
Holding the same neutral pose at the same distance should reproduce a very
similar reference, but ordinary tracking variation means the saved numbers will
not be identical. A completed calibration is saved atomically and reused across
games and restarts; an incomplete attempt does not replace the previous file.

Across the profiles, hold a **V sign** steadily for half a second to send Start and
a **thumbs-up with the other fingers closed** to send Select. These poses
suppress A/B attacks; some profiles can still generate directional or auxiliary
input, so keep your hand near its resting position while using them. Start sends
only one press and must see a clearly non-V pose for 0.30 seconds before it can
trigger again.

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
| G — Gun Smoke | Move your hand in four directions; wrist roll adds left or right. | Index curl sends A; pushing forward sends B. Combine them for A+B. Menu guard suppresses all ordinary controller output. |
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
before trying again. A push or pull must cross its threshold on two consecutive
fresh observations and travel at least 0.10 palm-scale units in the intended
direction within 250 ms. This rejects a one-frame scale jump and a stationary
hand that merely begins near or far from the camera. Bad Street Brawler needs its game-specific emulator setting;
see the [configuration reference](docs/CONFIGURATION_REFERENCE.md#bad-street-brawler-glove-zap).

### Super Glove Ball

| Gesture | Controller output |
| --- | --- |
| Move your hand left, right, up, or down | Corresponding D-pad direction |
| Curl your index finger | A |
| Curl your thumb | B |

The same responsive mapping remains the explicit FCEUmm fallback. Headless tests
using the same exact ROM show that both paths visibly activate and release every
direction by frame 3. Their semantics differ: FCEUmm supplies held digital
directions, while the native core supplies an absolute target position. The
native path has passed exact-ROM detection, Start, continuous X/Y, absolute Z,
open/fist/index packet, and safe-neutralization tests. Live full-game play
confirms grab/throw, index fire, and fist-plus-forward Power Punch. Native
movement uses per-player reach calibration and the selected MediaPipe response
mode. A brief missed observation holds only the last X/Y coordinate for up to
120 ms, while actions release immediately. On recovery, Latest accepts the new
measurement immediately unless it contradicts established motion or is an
unusually distant non-forward jump; only that questionable result waits for one
fresh confirmation. A longer loss neutralizes the native sample. Wrist rotation
and remaining unused native packet fields stay neutral. See the
[native compatibility record](docs/super-glove-ball-native.md).

The eight-ROM [input audit](docs/power-glove-rom-input-audit.md) confirms that the
other listed games consume standard NES controller bits. They continue to use
FCEUmm and the same global recognition settings.

For movement-latency investigation, the [baseline procedure](docs/direction-response-benchmark.md#collect-a-live-status-baseline)
collects fresh timing observations without changing camera settings or controls.
It keeps Controller software timing separate from network, emulator, and display delay.
The optional [PowerGlove Vision Controller dot test](docs/direction-response-benchmark.md#direct-output-dot-test) reuses the cabinet's installed
`lr-powerglove-dot` core to display the same receiver X/Y publication without
game movement logic, with read-only input-range and validity measurements.

The [native latency session tools](docs/direction-response-benchmark.md#native-latency-and-stationary-jitter-session)
guide stationary/movement windows, optionally correlate software traces, and
extract annotated evidence from an original hand-and-screen recording. They are
disabled during normal play. A privacy-safe preflight records the exact two-device
test state without changing it; smoke mode checks framing before the full session,
and the reversible trace helper restores production services before exporting its
bounded evidence. Historical trace tools can compare recognized,
optical-flow, selected, and filtered coordinates without recording video; the
current live path reports the newest valid MediaPipe coordinate directly.
Physical hand-to-screen latency still requires synchronized recording.

The production Controller runs the proven CPU MediaPipe Hands path at 640×480,
with four explicitly selected inference threads, a `0.35` tracking-confidence
threshold, and a `2.25` next-frame hand search area. The larger search area
recovered five of nine previously missed fast-sweep frames in repeatable replay
without a material latency or false-activation cost. Camera rate defaults to
Automatic, which tries the measured 30 fps
path before safely accepting the driver's supported rate. An isolated Adreno GPU probe
successfully created a delegate but the first MediaPipe Tasks graph was much
slower than production, so no GPU wheel or runtime change ships in this
candidate. A lean, output-paused GPU palm/landmark experiment remains research.

## Use the web interface

Setup includes **Joystick dead zone**, saved separately for each player. Small
requires less hand movement to press a direction; Large gives more room around
center. **Use standard size** selects the existing 0.28 activation / 0.14 release
pair; select **Save dead zone** to apply. The slider sets all four directions
together, without changing center or native Super Glove Ball reach. Live direction
indicators work while tracking is active. Separate directional thresholds remain
under Glove Academy → Tune gestures → Advanced thresholds and diagnostics.

The Controller website uses the logo’s hand-and-target emblem for browser tabs
and saved home-screen shortcuts.

| Page | What it does |
| --- | --- |
| Dashboard, `/dashboard` | Shows the camera and generated inputs; selects the current profile and starts or stops delivery. |
| Play, `/play` | Runs a camera-controlled Rock Paper Scissors match against Pixel Pal, with cabinet input paused. |
| Glove Academy, `/learn` | Provides sixteen mapping-independent practice lessons and guided gesture tuning, with game input paused. Player presets retain individual sensitivity, progress, and the Glove Master award across restarts. Select the same active player used for gameplay; manage players and hand-setting backups in Setup. |
| Help, `/help` | Opens the local manuals and PDFs; **This console** shows current connection details. |
| Setup, `/setup` | Saves connection, camera, and startup settings; its camera dropdown lists Automatic and discovered usable cameras. The Games section edits RetroPie mappings with backup and restore. Pairing requires HTTPS on port 8443. |

With **Gestures off** selected, the camera stays closed. Choose an active profile,
open Play, or open Glove Academy to begin. Wait for the camera view before
practicing or playing; starting immediately after a reboot can take longer.

The live camera is diagnostic rather than part of controller output. **Show
statistics** is off by default and can be enabled on Dashboard or Setup; the
browser remembers the choice. When it is off, the Dashboard does not render or
retain the optional controller, axes, finger, performance, or event panels, and
the worker skips their derived housekeeping. When enabled, changed controls are
published immediately while routine detail and percentile summaries refresh at
about 10 Hz through a latest-only status worker.
Camera
capture continuously keeps only the newest frame, and browser JPEG encoding
runs on a separate latest-preview worker that may drop stale preview jobs.
Gameplay preview annotation and encoding use a 320×240 copy while Academy and
tuning keep the full preview. The preview remains capped at 5 fps. Closing Dashboard or Glove Academy while playing
a RetroPie game still avoids optional drawing and encoding work; tracking and
controller delivery continue.

Strong light behind the player can leave the hand dark even when the room looks
bright. Prefer light from the camera side or move bright windows out of the
background. The project does not force hardware backlight compensation: on the
tested Razer Kiyo Pro it made the measured backlit scene darker.

Setup also offers opt-in camera controls. **Low latency — Direct V4L2**
reads the newest Linux MJPEG driver buffer and automatically falls back to
OpenCV if the camera or negotiated format is incompatible. **Razer Kiyo Pro —
tested low latency** keeps automatic exposure, requests a fixed frame rate using
advertised standard UVC controls, and also requests the Kiyo's volatile HDR-off
mode. **Manual exposure and gain** is available only with Direct V4L2. The
Controller first checks the camera's advertised controls and reports the values
actually applied. Unsupported settings fall back visibly to automatic exposure.
Automatic remains the portable installation default; this project's Kiyo Pro
tested slightly more reliably at exposure `78` and gain `96`, without a measured
latency difference. Manual controls are restored to automatic when the camera is
closed, while the saved preference is reused the next time vision starts.

The direct reader passed a live compatibility check on this project's Kiyo Pro
and exposed valid driver sequence numbers and monotonic timestamps. It remains
an option rather than a universal default because other camera drivers may not
provide the same Linux MJPEG interface. A matched lean MediaPipe output test did
not produce a meaningful end-to-end improvement, so the complete proven graph
remains selected.

The Controller host helper supports one UVC camera. Installation works with or without
the camera connected. On the first healthy sighting it records the camera and its
actual parent USB hub in a root-owned allowlist, disables autosuspend for both,
and automatically updates that association if the camera is later moved to a
different hub. If the camera remains missing for 15 seconds while vision is
requested, PowerGlove Vision makes one guarded recovery attempt for that outage
by resetting only the last successfully observed hub. This can briefly interrupt
USB Ethernet; Wi-Fi remains available. If a camera has never been seen—or does
not return after that attempt—reconnect or power-cycle it and check the hub and
cable rather than repeatedly resetting it.

**Stop controller** pauses delivery while leaving active tracking available.
**Gestures off** closes the camera. **Shutdown** requests a Linux halt, but
the tested Arduino UNO Q hardware restarts afterward. A disappearing website is not proof that
it is safe to remove power. See the installation guide before using Shutdown.

![Dashboard showing the selected profile and controller readings](docs/images/debug-dashboard.png)

The screenshots below show the current interface with isolated sample data. Camera imagery is
replaced with a labelled placeholder for privacy.

![Glove Academy with Pixel Pal guiding the personalization choices](docs/images/tune-page.png)

**Learn and practise:** open **Glove Academy** and choose your player to work
through sixteen lessons, from showing and centering your hand to movement and
gesture control. Follow the illustrated instructions and camera feedback, practise
one movement at a time, and return later to your saved progress. Complete every
lesson to earn **Glove Master**. Lessons teach the gestures independently of the
selected game mapping; use the [Gameplay Guide](docs/GAMEPLAY_GUIDE.md) to see
what those gestures do in each game. The Controller displays a scanning **L**
during learning mode, with cabinet input paused.

Choose each player in turn and select **Back up hand setup** to download a
separate file named for that player, such as
`iain-powerglove-hand-setup.json`. Your browser saves it on the computer, phone,
or tablet you are using, usually in **Downloads** or the folder you choose. To restore, select
the player you want to update, choose **Restore hand setup**, and pick that
player's saved file from your device. Review it before confirming; restore
updates the selected player, rather than adding a new one.

**Personalize recognition:** switch on **Tune gestures** when recognition needs
adjustment for your hand. This optional mode displays a scanning **T** and also
pauses cabinet input.

Pixel Pal first asks what feels wrong, then presents one instruction at a time.
Recording starts only after the whole hand has been tracked clearly and steadily;
the user presses **I'm ready** and sees a countdown. The wizard previews a
conservative adjustment, requires two successful uses and releases plus three
neutral seconds, and enables Save only after that check passes. Saved recognition
settings apply across profiles. Numerical thresholds, selective reset, manual
preview, and the private diagnostic capture live under **Advanced**. Diagnostic
video remains on the Controller, is deleted after analysis or cancellation, and its
downloadable aggregate report contains no pictures or per-frame hand data.

The separate **Movement reach** section exposes the selected player's left,
right, up, and down spans. These are normalized distances from the saved center;
smaller values require less physical travel. Its summary shows the resulting
tracking-area dimensions and aspect ratio. **Save reach values** changes only
those four spans, while **Restore full camera field** returns all four to the
camera-boundary default without changing center or gesture thresholds.

![Games editor in the lower part of Setup](docs/images/games-section.png)

Scroll down **Setup** to **Games** to map exact ROM filenames to profiles.
Saving affects the next game launch, not the game already running.

New builders can start with [Build your own: parts, cost, and difficulty](docs/BUILD_YOUR_OWN.md).
For the game-input background, read [How native Power Glove emulation works](docs/NATIVE_EMULATION_EXPLAINED.md).
When something fails, use [Troubleshooting by symptom](docs/TROUBLESHOOTING.md).
All three are available in Controller Help and as printable PDFs. Help orders
user manuals from console details through game controls, programs, matrix
displays, building, installation, and troubleshooting. Technical documentation starts with the
project overview and architecture before configuration and detailed evidence.

## Maintain or extend the project

Use the [Installation Guide's maintenance section](docs/INSTALL_README.md#updates-and-checks)
for updates, and the [Configuration Reference](docs/CONFIGURATION_REFERENCE.md)
for settings and all command options. The [Contributing guide](docs/CONTRIBUTING.md)
covers tests, documentation, package verification, and releases. Printable
editions are stored in [output/pdf/](output/pdf/). The maintained Markdown set
is intentionally consolidated into 19 documents: operational details live with
their owning guide, and third-party licensing, provenance, asset origins, and
native-core modifications share one notice. Regenerate PDFs only after the
Markdown review is complete.

PowerGlove Vision is an independent project licensed under the [MIT License](LICENSE).
The modified Nestopia core is GPLv2 software and is documented separately from
the MIT application; see its [distribution and license record](THIRD_PARTY_NOTICES.md#modified-nestopia-libretro-core).
Nintendo, NES, Power Glove, and the named games belong to their respective
owners. Third-party software and models retain their own terms, documented in
[Third-party notices](THIRD_PARTY_NOTICES.md).
