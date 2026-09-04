<p align="center">
  <img src="../assets/powerglove-vision-logo.png" alt="PowerGlove Vision" width="680">
</p>

# Play with PowerGlove Vision

This guide provides eight game-specific play cards and explains how to use
the nine reusable programs. It shows you which gestures to make, what controls
they produce, and how to try them with other games in your library.

Find your game below, check its profile, and try the first-round exercise.
If the system is not installed yet, start with the [Installation Guide](INSTALL_README.md).

## Get ready to play

Select a profile on Dashboard, or open Learn for practice. If you see
**Starting camera and gesture tracking**, wait for the camera view to appear.
The app prepares its tracking software in the background after startup, keeping
the camera off until needed. If you begin straight after boot, you may wait for
that preparation to finish. The elapsed-time display covers the remaining
preparation, camera startup, and tracking initialization. **Calibrate** becomes
available when vision is active.

  1. Stand where the camera can see your whole hand with a little room on every side.
  2. Open your hand and face your palm toward the camera. On first use, or if your camera or playing position has changed, select **Calibrate**. Otherwise reuse your saved resting position, which the app treats as the centre of movement.
  3. Wait for tracking to settle, then select **Start controller**.
  4. Move your whole hand away from center for directions. Return to center to stop.
  5. Make one gesture at a time. Clean poses beat frantic motion.

<img src="images/gestures/v2/pixel-pal-web.png" alt="Pixel Pal, your arcade practice buddy" width="112">

### The two gestures that work everywhere

| Gesture | See it | Result |
| --- | --- | --- |
| Hold a V sign for about 0.7 seconds | <img src="images/gestures/v2/v-sign.png" alt="V sign with the index and middle fingers extended" width="104"> | Start or pause |
| Hold a thumbs-up with the other fingers closed for about 0.7 seconds | <img src="images/gestures/v2/thumbs-up.png" alt="Thumbs-up with the other fingers closed" width="104"> | Select |

The menu poses suppress A/B attacks while they form. Some profiles can still
produce directional or auxiliary output from wrist, depth, or finger gestures;
keep your hand near its calibrated resting position while using menu poses. If a game
needs Select and a direction at exactly the same time, use the physical
controller for that combination. Recalibrate if your resting hand position produces unwanted movement.

The small pictures in each game card are pose reminders. Paired arrows show the
available movement or wrist-roll directions; paired pictures show a combined
gesture.

**Comfort tip:** If the character moves while your hand is resting, recalibrate
in that position. Keep movements small enough to repeat comfortably.

<!-- PAGEBREAK -->

## Your gesture reference

Practice one movement at a time. Your selected profile decides what each
gesture does in the game; the play cards below show the mapping.

| Gesture | See it | Try it |
| --- | --- | --- |
| Move left | <img src="images/gestures/v2/move-left.png" alt="Move left" width="96"> | Slide your whole hand left. |
| Move right | <img src="images/gestures/v2/move-right.png" alt="Move right" width="96"> | Slide your whole hand right. |
| Move up | <img src="images/gestures/v2/move-up.png" alt="Move up" width="96"> | Raise your whole hand. |
| Move down | <img src="images/gestures/v2/move-down.png" alt="Move down" width="96"> | Lower your whole hand. |
| Curl index finger | <img src="images/gestures/v2/curl-index.png" alt="Curl index finger" width="96"> | Bend your index finger toward your palm. |
| Curl thumb | <img src="images/gestures/v2/curl-thumb.png" alt="Curl thumb" width="96"> | Fold your thumb across your palm. |
| V sign | <img src="images/gestures/v2/v-sign.png" alt="V sign" width="96"> | Hold for about 0.7 seconds to Start or pause. |
| Thumbs-up | <img src="images/gestures/v2/thumbs-up.png" alt="Thumbs-up" width="96"> | Close the other fingers; hold for about 0.7 seconds for Select. |
| Roll wrist left | <img src="images/gestures/v2/wrist-roll-left.png" alt="Roll wrist left" width="96"> | Tilt your hand left at the wrist. |
| Roll wrist right | <img src="images/gestures/v2/wrist-roll-right.png" alt="Roll wrist right" width="96"> | Tilt your hand right at the wrist. |
| Push toward camera | <img src="images/gestures/v2/push-toward-camera.png" alt="Push toward camera" width="96"> | Move your hand closer to the camera. |
| Pull away from camera | <img src="images/gestures/v2/pull-away-from-camera.png" alt="Pull away from camera" width="96"> | Move your hand farther from the camera. |

The glove is an illustration: PowerGlove Vision tracks your bare hand.

<!-- PAGEBREAK -->

## Bad Street Brawler

**Profile:** `bad_street_brawler` / matrix code `BS`

**Your mission:** Guide Duke Davis through each stage, discover that stage's
three fighting moves at the practice bag, and clear the street before time or
vitality runs out.

| Do this | See it | Duke does this |
| --- | --- | --- |
| Move hand left / right | <img src="images/gestures/actions/horizontal-movement.png" alt="Move the whole hand left or right" width="96"> | Walk left / right |
| Raise / lower hand | <img src="images/gestures/actions/vertical-movement.png" alt="Raise or lower the whole hand" width="96"> | Jump / crouch |
| Curl thumb | <img src="images/gestures/v2/curl-thumb.png" alt="Curl the thumb" width="72"> | Pulsed B move |
| Curl middle finger | <img src="images/gestures/actions/finger-curl.png" alt="Finger-curl motion" width="72"> | A+B force move |
| Roll wrist left / right | <img src="images/gestures/actions/wrist-roll.png" alt="Roll the wrist left or right" width="96"> | A plus that direction |
| Push toward camera | <img src="images/gestures/v2/push-toward-camera.png" alt="Push the hand toward the camera" width="72"> | Glove Zap auxiliary event |

**Play smart:** The available force moves change with each stage. Test the
thumb curl, middle-finger curl, and wrist rolls on the punching bag before
leaving practice. The Glove
Zap signal is preserved, but the current standard-gamepad integration cannot
unlock the cartridge's native glove-only zap yet.

**First round:**

  1. At the practice bag, try a thumb curl, a middle-finger curl, and a wrist roll separately.
  2. Notice which move each gesture produces in this stage.
  3. Enter the street and use one familiar move before adding combinations.

<!-- PAGEBREAK -->

## Super Glove Ball

**Profile:** `super_glove_ball` / matrix code `GB`

**Your mission:** Control the Robo-Glove, keep the energy ball in play, break a
complete wall of tiles, and follow the revealed arrows through the maze.

| Do this | See it | Controller result |
| --- | --- | --- |
| Move whole hand | <img src="images/gestures/actions/whole-hand-movement.png" alt="Move the whole hand in four directions" width="96"> | Steer the Robo-Glove with the D-pad fallback |
| Curl index finger | <img src="images/gestures/v2/curl-index.png" alt="Curl the index finger" width="72"> | A: move the glove into the room |
| Curl thumb | <img src="images/gestures/v2/curl-thumb.png" alt="Curl the thumb" width="72"> | B: punch, grab, or launch a new ball |
| Hold V sign | <img src="images/gestures/v2/v-sign.png" alt="Hold a V sign" width="72"> | Start / pause |
| Hold thumbs-up | <img src="images/gestures/v2/thumbs-up.png" alt="Hold a thumbs-up" width="72"> | Select: doorway or Robo-Bullet action |

**Play smart:** Pick one wall and finish it. When its arrow appears, use Select
to take the exit. The current profile also preserves analogue hand position,
depth, wrist roll, and individual finger values for future native glove support.

**First round:**

  1. Move the glove across the room with small hand movements.
  2. Try the index and thumb actions separately so you can recognize their effects.
  3. Keep the ball in play, then aim to clear one wall.

<!-- PAGEBREAK -->

## Joust

**Profile:** `program_b` / matrix code `B`

**Your mission:** Ride the ostrich, strike enemy riders from above, collect
their eggs before they hatch, and stay clear of the lava.

| Do this | See it | Result |
| --- | --- | --- |
| Move hand left / right | <img src="images/gestures/actions/horizontal-movement.png" alt="Move the whole hand left or right" width="96"> | Steer left / right |
| Curl index or middle finger | <img src="images/gestures/actions/finger-curl.png" alt="Finger-curl motion" width="72"> | Pulsed A: steady flap |
| Curl thumb | <img src="images/gestures/v2/curl-thumb.png" alt="Curl the thumb" width="72"> | B: faster flap |
| Hold V sign | <img src="images/gestures/v2/v-sign.png" alt="Hold a V sign" width="72"> | Start / pause |
| Hold thumbs-up | <img src="images/gestures/v2/thumbs-up.png" alt="Hold a thumbs-up" width="72"> | Select game mode |

**Play smart:** Height wins jousts. Use the faster thumb flap to climb, then the
pulsed finger flap to hold position. Sweep up eggs quickly; every ignored egg is
an enemy preparing a return engagement.

**First round:**

  1. Curl your index finger to practise a steady flap.
  2. Move left and right while keeping your height.
  3. Approach one rider from above, then collect the egg.

<!-- PAGEBREAK -->

## Gyruss

**Profile:** `program_c` / matrix code `C`

**Your mission:** Circle the tunnel, destroy incoming formations, survive the
warp zones, and fight from planet to planet toward the Sun.

| Do this | See it | Result |
| --- | --- | --- |
| Roll wrist left / right | <img src="images/gestures/actions/wrist-roll.png" alt="Roll the wrist left or right" width="96"> | Orbit counter-clockwise / clockwise |
| Keep index finger straight | <img src="images/gestures/actions/keep-index-straight.png" alt="Keep the index finger straight" width="72"> | Continuous A fire |
| Pull hand away from camera | <img src="images/gestures/v2/pull-away-from-camera.png" alt="Pull the hand away from the camera" width="72"> | B bomb |
| Hold V sign | <img src="images/gestures/v2/v-sign.png" alt="Hold a V sign" width="72"> | Start / pause |
| Hold thumbs-up | <img src="images/gestures/v2/thumbs-up.png" alt="Hold a thumbs-up" width="72"> | Select control mode |

**Before launching:** Choose **Attack Control B** at the title screen. This
profile expects left/right rotation rather than eight-direction movement.

**First round:**

  1. Select Attack Control B at the title screen.
  2. Keep your index straight and practise small wrist rolls in both directions.
  3. Clear one formation before trying the pull-back bomb.

<!-- PAGEBREAK -->

## Defender II

**Profile:** `program_e` / matrix code `E`

**Your mission:** Patrol the planet, destroy alien raiders, and rescue the
humanoids before abductors carry them away and turn them into mutants.

| Do this | See it | Result |
| --- | --- | --- |
| Move whole hand | <img src="images/gestures/actions/whole-hand-movement.png" alt="Move the whole hand in four directions" width="96"> | Fly up, down, left, or right |
| Curl thumb | <img src="images/gestures/v2/curl-thumb.png" alt="Curl the thumb" width="72"> | A: fire |
| Roll wrist either way | <img src="images/gestures/actions/wrist-roll.png" alt="Roll the wrist in either direction" width="96"> | B: smart bomb |
| Curl ring finger | <img src="images/gestures/actions/finger-curl.png" alt="Finger-curl motion" width="72"> | Rapid left/right evasive thrash |
| Hold V sign | <img src="images/gestures/v2/v-sign.png" alt="Hold a V sign" width="72"> | Start / pause |

**Play smart:** Watch the scanner as much as the ship. Intercept abductors early;
if one lifts a humanoid, shoot the alien and catch the falling person. Wrist
rolls trigger the smart-bomb action, so make them deliberate.

**First round:**

  1. Fly a short circuit with your wrist level.
  2. Curl your thumb to fire while moving.
  3. Track one abductor on the scanner; save deliberate wrist rolls for smart bombs.

<!-- PAGEBREAK -->

## Sesame Street 1-2-3

The same game may appear in your library as **Sesame Street 123**. The registry
includes both filename spellings, with `.nes`, `.zip`, and `.7z` extensions.

**Profile:** `program_f` / matrix code `F`

**Your mission:** Play the counting activities by giving the game a simple,
physical Yes or No answer.

| Do this | See it | Result |
| --- | --- | --- |
| Move an open hand in any direction | <img src="images/gestures/actions/whole-hand-movement.png" alt="Move an open hand in any direction" width="96"> | A: Yes |
| Close every finger into a fist | <img src="images/gestures/actions/close-all-fingers.png" alt="Close all fingers" width="72"> | B: No |
| Hold V sign | <img src="images/gestures/v2/v-sign.png" alt="Hold a V sign" width="72"> | Start / pause |
| Hold thumbs-up | <img src="images/gestures/v2/thumbs-up.png" alt="Hold a thumbs-up" width="72"> | Select |

**Play smart:** Directional output is intentionally disabled in this profile.
Make the open-hand answer broad and obvious; make the fist complete. Return to a
relaxed open hand between questions so one answer does not run into the next.

**First round:**

  1. Count the objects before making a gesture.
  2. Move an open hand from the resting position for Yes, or close all fingers for No.
  3. Return to a relaxed hand at the centre before the next question.

<!-- PAGEBREAK -->

## Gun Smoke

**Profile:** `program_g` / matrix code `G`

**Your mission:** Walk the scrolling frontier, defeat the bandits, find or buy
each wanted poster, and collect the bounty by beating the stage boss.

| Do this | See it | Result |
| --- | --- | --- |
| Move whole hand | <img src="images/gestures/actions/whole-hand-movement.png" alt="Move the whole hand in four directions" width="96"> | Walk in that direction |
| Curl index finger | <img src="images/gestures/v2/curl-index.png" alt="Curl the index finger" width="72"> | A: shoot diagonally right |
| Push toward camera | <img src="images/gestures/v2/push-toward-camera.png" alt="Push the hand toward the camera" width="72"> | B: shoot diagonally left |
| Curl index while pushing | <img src="images/gestures/actions/index-push-combination.png" alt="Combine a finger curl with a push toward the camera" width="96"> | A+B: shoot straight ahead |
| Curl thumb and ring finger | <img src="images/gestures/actions/thumb-finger-combination.png" alt="Combine a thumb curl with another finger curl" width="96"> | Suppress D-pad and A/B output |

**Play smart:** A stage keeps looping until you obtain its wanted poster. Keep
your palm level while walking; wrist roll can add a left/right movement command.
Use index-plus-push when you need the straight-ahead shot.

**First round:**

  1. Try an index curl for the right shot and a forward push for the left shot.
  2. Combine them to fire straight ahead.
  3. Walk while firing, then look for the wanted poster.

<!-- PAGEBREAK -->

## Knight Rider

**Profile:** `program_i` / matrix code `I`

**Your mission:** Drive KITT from city to city, avoid roadside hazards, destroy
the criminals ahead, and reach each destination before the timer expires.

| Do this | See it | Result |
| --- | --- | --- |
| Roll wrist left / right | <img src="images/gestures/actions/wrist-roll.png" alt="Roll the wrist left or right" width="96"> | Steer left / right |
| Curl index finger | <img src="images/gestures/v2/curl-index.png" alt="Curl the index finger" width="72"> | Accelerate |
| Lower hand | <img src="images/gestures/v2/move-down.png" alt="Lower the whole hand" width="72"> | Brake |
| Push toward camera | <img src="images/gestures/v2/push-toward-camera.png" alt="Push the hand toward the camera" width="72"> | Accelerate plus turbo boost |
| Curl thumb | <img src="images/gestures/v2/curl-thumb.png" alt="Curl the thumb" width="72"> | Fire weapons |

**Play smart:** Keep the wrist near center on straight roads; large steering
rolls are for real turns. Keep your index finger curled for normal speed and reserve the
forward push for a clean burst when the road opens.

**First round:**

  1. Curl your index finger to accelerate and make small wrist rolls to steer.
  2. Lower your hand to practise braking.
  3. Use a forward push for turbo only when the road ahead is clear.

<!-- PAGEBREAK -->

## Take PowerGlove Vision off-script

You can use the included profiles with games beyond the eight listed in this
guide. Programs A–I send ordinary NES controller inputs, so try matching their
gestures to games with similar controls. Programs A, D, and H have no default
ROM assignment and are useful starting points for these experiments.

### Start with A, D, and H

| Program | See it | Try it with | Know before playing |
| --- | --- | --- | --- |
| **A - Pinball** | <img src="images/gestures/actions/wrist-roll.png" alt="Rotate the wrist for the pinball tilt action" width="96"> | Pinball and games driven by two independent actions | Index curl is A, thumb curl is Up, wrist tilt is B, and pulling back toggles combined flippers. Ordinary directional movement is disabled. |
| **D - Mirror world** | <img src="images/gestures/actions/whole-hand-movement.png" alt="Move the whole hand in four directions" width="96"> | A game you already know well, a party challenge, or an inverted-direction accessibility experiment | Every direction is reversed. Thumb and index provide A and B. Expect your muscle memory to complain loudly. |
| **H - General play** | <img src="images/gestures/actions/finger-curl.png" alt="Curl a finger for a general-purpose action button" width="72"> | Two-button platform, maze, puzzle, and action games | Hand movement supplies the D-pad. Index and thumb pulse A and B, so games that require a long held button may be a poor fit. |

Try Program H first for general play, or Program A for pinball controls.
Program D turns a familiar game into a new coordination challenge without
changing the ROM or emulator.

### Try a combination

  1. Launch the NES or Famicom game normally. An unregistered game safely turns gesture output off instead of inheriting the previous game's controls.
  2. Open the UNO Q **Dashboard** and choose **A: Pinball**, **D: Challenge**, **H: General**, or another Program A-I profile from **Active profile**.
  3. Use **Calibrate** if your resting hand position produces unwanted movement or your physical setup has changed. Hold still while calibration completes, then select **Start controller** and return to the game.
  4. Test movement, both action gestures, Start, and Select before committing to a long session. Stop the controller immediately if a gesture remains active.

The selection is temporary. Starting or ending a game sends a new command
that changes the profile or turns gestures off.

### Keep a discovery

Add the game's exact ROM basename, including `.nes`, `.zip`, or `.7z`, to the
`games` object in `/etc/powerglove/games.json` on RetroPie. Keep the existing
entries and assign the profile that worked:

```json
{
  "games": {
    "YOUR EXACT GAME FILENAME.nes": "program_h"
  }
}
```

Restart the game after saving. The launch hook will then select that profile
automatically and the UNO Q matrix will show its letter. Automatic selection is
currently limited to NES and Famicom; other systems deliberately turn gesture
control off until their mappings and launch behaviour are validated.

Do not stop at A, D, and H. Try B when rhythmic button pulses suit the action,
C when wrist rotation can replace horizontal movement, F for simple Yes/No
choices, or I when steering and throttle are the heart of the game. Match the
profile to the game's mechanics, not to the title printed on the cartridge.

> **GLOVE LAB RULE**  A strange pairing that is controllable, repeatable, and
> fun is a successful experiment. Record the exact ROM filename and profile so
> somebody else can reproduce it.

For every Program A–I gesture, see the illustrated
[Programs A–I manual](bad-street-brawler-programs.md). For registry validation
and manual profile commands, see the
[Configuration Reference](CONFIGURATION_REFERENCE.md).

## Sources, artwork, and fair play

The profile descriptions are checked against the project's implemented gesture
engine and tests. Game objectives and original control intent were summarized
from the following historical instruction sources:

  - [Mattel Power Glove instructions and Programs A-I](https://home.hiwaay.net/~lkseitz/cvg/power_glove.shtml)
  - [Bad Street Brawler NES instruction transcription](https://www.world-of-nintendo.com/manuals/nes/bad_street_brawler.shtml)
  - [Super Glove Ball NES instruction manual](https://www.digitpress.com/library/manuals/nes/Super%20Glove%20Ball.pdf)
  - [Joust NES instruction transcription](https://www.world-of-nintendo.com/manuals/nes/joust.shtml)
  - [Gyruss NES instruction transcription](https://www.world-of-nintendo.com/manuals/nes/gyruss.shtml)
  - [Defender II NES instruction transcription](https://www.world-of-nintendo.com/manuals/nes/defender_2.shtml)
  - [Gun Smoke NES gameplay reference](https://strategywiki.org/wiki/Gun.Smoke_%28NES%29/Gameplay)
  - [Knight Rider NES instruction manual](https://www.retrogames.cz/manualy/NES/Knight_Rider_-_NES_-_Manual.pdf)

The gesture drawings are original PowerGlove Vision project illustrations made
for this guide. They deliberately avoid game screenshots, box art, characters,
and publisher logos.

PowerGlove Vision is an independent MIT-licensed hobbyist project by Iain
Bennett. Nintendo, NES, Power Glove, and all game titles and marks belong to
their respective owners. No ROM images or original game artwork are distributed.


### Reading the camera overlay

The camera overlay labels the detected hand as **Right** or **Left**. The
number beside the label indicates how confident the tracker is in that
identification. To see the controls produced by your gestures, check the
D-pad, button, and axis readings on Dashboard.

Learn uses the same saved resting-position reference as gameplay. It helps
you practise gestures but does not train or save a personal recognition model.

## Make the controls fit your hand

If a gesture needs too much movement or fires accidentally, open **Learn** and
switch on **Tune gestures**. Record your relaxed hand, then three repetitions of
the gesture and its release. Preview the suggested thresholds before choosing
**Save for all profiles**. Your games keep their button assignments; the selected
gesture becomes easier or harder to activate everywhere it is used.

![Tune mode with a blurred camera view and editable thresholds](images/tune-page.png)

The threshold table is below the camera; recording instructions are beside it.
The matrix shows **T** during tuning, and controller delivery stays paused.
Camera imagery in this screenshot is blurred for privacy.

For a different automatic profile, open **Setup → Games**, edit the exact ROM filename's
mapping, validate, and save. Restart the game to use the new mapping. The
[configuration reference](CONFIGURATION_REFERENCE.md) explains both workflows.

![Games mappings in the lower section of Setup](images/games-section.png)
