<p align="center">
  <img src="../assets/powerglove-vision-logo.png" alt="PowerGlove Vision" width="620">
</p>

# Bad Street Brawler's Power Glove Programs

Bad Street Brawler does more than map its own controls. Its cartridge contains
nine additional programs, labelled A through I, which it can transmit to the
Power Glove. The player loads a program, turns off the NES, changes cartridges
within roughly 30 seconds, and then uses the retained mapping in another game.

These are configuration programs for the glove's resident gesture interpreter,
not replacement firmware. Each program combines tests for hand position,
depth, wrist angle, and finger flex, then emits ordinary NES controller inputs.
Consequently, the target game does not need to know that a glove is present.

## Program catalogue

| Program | Intended use | Gesture behaviour |
| --- | --- | --- |
| A | Pinball | Index operates the right flipper/A; thumb operates the left flipper/Up; six-o'clock wrist position tilts/B; pulling back toggles a combined-flipper mode. |
| B | Joust | Left/right hand movement steers; thumb turns the rider; index or middle finger flaps, using pulsed input. |
| C | Gyruss | Wrist angles rotate clockwise/counter-clockwise; keeping the index straight fires continuously; pulling the hand back fires a bomb. |
| D | Deliberately reversed controls | Left becomes Right, right becomes Left, up becomes Down, and down becomes Up; thumb and index supply A/B. |
| E | Defender II and similar shooters | Hand position moves the ship; thumb fires; six-o'clock wrist position triggers the smart bomb; ring-finger flex produces rapid left/right movement. |
| F | Sesame Street 1-2-3 | A closed/grabbing hand means No; moving an open hand means Yes. |
| G | Gun.Smoke | X/Y/Z-style hand movement walks; index fires; wrist angles select firing direction; thumb-plus-ring flex suppresses action for menus. |
| H | Training/general play | Conventional directional movement with pulsed thumb/index buttons, plus an audible indication when the hand is centred. |
| I | Knight Rider and driving games | Pushing forward enables turbo; index is throttle; lowering the hand brakes; thumb fires; wrist angles steer. |

The descriptions above follow the original Power Glove manual. PowerGlove
Vision implements practical camera-based equivalents that emit ordinary NES
controls. Their thresholds can be tuned without changing an emulator or ROM.

## Implication for PowerGlove Vision

The UNO Q contains Programs A-I itself. RetroPie's launch hook identifies the
actual ROM basename and requests the configured program over an authenticated
control channel. This intentionally removes the original requirement to run
Bad Street Brawler and swap cartridges within thirty seconds.

An eventual native Power Glove controller in Libretro Nestopia would still be
valuable for glove-aware software such as Super Glove Ball and Bad Street
Brawler's glove-only zap. It is no longer a prerequisite for using Programs
A-I with conventional NES games.

## Using a program

Select a program from the UNO Q Setup page for manual use, or map a game's
exact ROM filename in `/etc/powerglove/games.json` so RetroPie's launch hook
selects it automatically. The UNO Q matrix acknowledges the active program with
`A` through `I`. Opening `/learn` is safe for practice because it stops
controller transmission; use `/debug` to inspect the generated NES controls.

See the repository's `INSTALL_README.md` for Wi-Fi setup, secure RetroPie
pairing and launch-hook installation.
