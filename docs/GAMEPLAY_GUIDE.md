<p align="center">
  <img src="../assets/powerglove-vision-logo.png" alt="Power Glove Vision" width="680">
</p>

# Play with Power Glove Vision

**Eight ready-made play cards. Nine reusable programs. One gloriously
impractical way to rediscover a game library.**

## Before you throw your first virtual punch

1. Stand where the camera can see your whole hand with a little room on every side.
2. Open your hand, face your palm toward the camera, and select **Center hand**.
3. Wait for tracking to settle, then select **Start controller**.
4. Move your whole hand away from center for directions. Return to center to stop.
5. Make one gesture at a time. Clean poses beat frantic motion.

![Whole-hand movement controls](images/gestures/actions/whole-hand-movement.png)

### The two gestures that work everywhere

| Gesture | See it | Result |
| --- | --- | --- |
| Hold a V sign for about 0.7 seconds | <img src="images/gestures/actions/v-sign.png" alt="V sign with the index and middle fingers extended" width="104"> | Start or pause |
| Hold a thumbs-up with the other fingers closed for about 0.7 seconds | <img src="images/gestures/actions/thumbs-up.png" alt="Thumbs-up with the other fingers closed" width="104"> | Select |

The menu poses briefly suppress movement and attacks while they form. If a game
needs Select and a direction at exactly the same time, use the physical
controller for that combination. Re-center whenever neutral begins to drift.

The small pictures in each game card are pose reminders. Paired arrows show the
available movement or wrist-roll directions; paired pictures show a combined
gesture.

> **GLOVE LAW #1**  If the character moves while your hand is centered, stop and
> re-center. Do not teach your arm to compensate for a bad neutral position.

## Bad Street Brawler

**Profile:** `bad_street_brawler` / matrix code `BS`

**Your mission:** Guide Duke Davis through each stage, discover that stage's
three fighting moves at the practice bag, and clear the street before time or
vitality runs out.

| Do this | See it | Duke does this |
| --- | --- | --- |
| Move hand left / right | <img src="images/gestures/actions/horizontal-movement.png" alt="Move the whole hand left or right" width="96"> | Walk left / right |
| Raise / lower hand | <img src="images/gestures/actions/vertical-movement.png" alt="Raise or lower the whole hand" width="96"> | Jump / crouch |
| Curl thumb | <img src="images/gestures/actions/thumb-curl.png" alt="Curl the thumb" width="72"> | Pulsed B move |
| Curl middle finger | <img src="images/gestures/actions/finger-curl.png" alt="Finger-curl motion" width="72"> | A+B force move |
| Roll wrist left / right | <img src="images/gestures/actions/wrist-roll.png" alt="Roll the wrist left or right" width="96"> | A plus that direction |
| Push toward camera | <img src="images/gestures/actions/push-toward-camera.png" alt="Push the hand toward the camera" width="72"> | Glove Zap auxiliary event |

**Play smart:** The available force moves change by stage. Test thumb, middle
finger, and wrist rolls on the punching bag before leaving practice. The Glove
Zap signal is preserved, but the ordinary `lr-nestopia` controller path cannot
unlock the cartridge's native glove-only zap yet.

> **ONE-LINE PLAN**  Learn the three moves, protect your vitality, and do not
> pick a fight with every little old lady carrying a handbag.

<!-- PAGEBREAK -->

## Super Glove Ball

**Profile:** `super_glove_ball` / matrix code `GB`

**Your mission:** Control the Robo-Glove, keep the energy ball in play, break a
complete wall of tiles, and follow the revealed arrows through the maze.

| Do this | See it | Controller result |
| --- | --- | --- |
| Move whole hand | <img src="images/gestures/actions/whole-hand-movement.png" alt="Move the whole hand in four directions" width="96"> | Steer the Robo-Glove with the D-pad fallback |
| Curl index finger | <img src="images/gestures/actions/finger-curl.png" alt="Curl the index finger" width="72"> | A: move the glove into the room |
| Curl thumb | <img src="images/gestures/actions/thumb-curl.png" alt="Curl the thumb" width="72"> | B: punch, grab, or launch a new ball |
| Hold V sign | <img src="images/gestures/actions/v-sign.png" alt="Hold a V sign" width="72"> | Start / pause |
| Hold thumbs-up | <img src="images/gestures/actions/thumbs-up.png" alt="Hold a thumbs-up" width="72"> | Select: doorway or Robo-Bullet action |

**Play smart:** Pick one wall and finish it. When its arrow appears, use Select
to take the exit. The current profile also preserves analogue hand position,
depth, wrist roll, and individual finger values for future native glove support.

> **ONE-LINE PLAN**  Think Breakout inside a room-sized maze: meet the ball,
> aim the rebound, and make an exit.

<!-- PAGEBREAK -->

## Joust

**Profile:** `program_b` / matrix code `B`

**Your mission:** Ride the ostrich, strike enemy riders from above, collect
their eggs before they hatch, and stay clear of the lava.

| Do this | See it | Result |
| --- | --- | --- |
| Move hand left / right | <img src="images/gestures/actions/horizontal-movement.png" alt="Move the whole hand left or right" width="96"> | Steer left / right |
| Curl index or middle finger | <img src="images/gestures/actions/finger-curl.png" alt="Finger-curl motion" width="72"> | Pulsed A: steady flap |
| Curl thumb | <img src="images/gestures/actions/thumb-curl.png" alt="Curl the thumb" width="72"> | B: faster flap |
| Hold V sign | <img src="images/gestures/actions/v-sign.png" alt="Hold a V sign" width="72"> | Start / pause |
| Hold thumbs-up | <img src="images/gestures/actions/thumbs-up.png" alt="Hold a thumbs-up" width="72"> | Select game mode |

**Play smart:** Height wins jousts. Use the faster thumb flap to climb, then the
pulsed finger flap to hold position. Sweep up eggs quickly; every ignored egg is
an enemy preparing a return engagement.

> **ONE-LINE PLAN**  Get above them, touch lances, grab the egg, repeat.

<!-- PAGEBREAK -->

## Gyruss

**Profile:** `program_c` / matrix code `C`

**Your mission:** Circle the tunnel, destroy incoming formations, survive the
warp zones, and fight from planet to planet toward the Sun.

| Do this | See it | Result |
| --- | --- | --- |
| Roll wrist left / right | <img src="images/gestures/actions/wrist-roll.png" alt="Roll the wrist left or right" width="96"> | Orbit counter-clockwise / clockwise |
| Keep index finger straight | <img src="images/gestures/actions/keep-index-straight.png" alt="Keep the index finger straight" width="72"> | Continuous A fire |
| Pull hand away from camera | <img src="images/gestures/actions/pull-away-from-camera.png" alt="Pull the hand away from the camera" width="72"> | B bomb |
| Hold V sign | <img src="images/gestures/actions/v-sign.png" alt="Hold a V sign" width="72"> | Start / pause |
| Hold thumbs-up | <img src="images/gestures/actions/thumbs-up.png" alt="Hold a thumbs-up" width="72"> | Select control mode |

**Before launching:** Choose **Attack Control B** at the title screen. This
profile expects left/right rotation rather than eight-direction movement.

> **ONE-LINE PLAN**  Keep the index straight, rotate into open space, and save
> the pull-back bomb for the formation that owns the whole tunnel.

<!-- PAGEBREAK -->

## Defender II

**Profile:** `program_e` / matrix code `E`

**Your mission:** Patrol the planet, destroy alien raiders, and rescue the
humanoids before abductors carry them away and turn them into mutants.

| Do this | See it | Result |
| --- | --- | --- |
| Move whole hand | <img src="images/gestures/actions/whole-hand-movement.png" alt="Move the whole hand in four directions" width="96"> | Fly up, down, left, or right |
| Curl thumb | <img src="images/gestures/actions/thumb-curl.png" alt="Curl the thumb" width="72"> | A: fire |
| Roll wrist either way | <img src="images/gestures/actions/wrist-roll.png" alt="Roll the wrist in either direction" width="96"> | B: smart bomb |
| Curl ring finger | <img src="images/gestures/actions/finger-curl.png" alt="Finger-curl motion" width="72"> | Rapid left/right evasive thrash |
| Hold V sign | <img src="images/gestures/actions/v-sign.png" alt="Hold a V sign" width="72"> | Start / pause |

**Play smart:** Watch the scanner as much as the ship. Intercept abductors early;
if one lifts a humanoid, shoot the alien and catch the falling person. Wrist
rolls spend the action mapped to the smart bomb, so make them deliberate.

> **ONE-LINE PLAN**  Scan, intercept, fire, rescue - then turn around fast.

<!-- PAGEBREAK -->

## Sesame Street 1-2-3

**Profile:** `program_f` / matrix code `F`

**Your mission:** Play the counting activities by giving the game a simple,
physical Yes or No answer.

| Do this | See it | Result |
| --- | --- | --- |
| Move an open hand in any direction | <img src="images/gestures/actions/whole-hand-movement.png" alt="Move an open hand in any direction" width="96"> | A: Yes |
| Close every finger into a fist | <img src="images/gestures/actions/close-all-fingers.png" alt="Close all fingers" width="72"> | B: No |
| Hold V sign | <img src="images/gestures/actions/v-sign.png" alt="Hold a V sign" width="72"> | Start / pause |
| Hold thumbs-up | <img src="images/gestures/actions/thumbs-up.png" alt="Hold a thumbs-up" width="72"> | Select |

**Play smart:** Directional output is intentionally disabled in this profile.
Make the open-hand answer broad and obvious; make the fist complete. Return to a
relaxed open hand between questions so one answer does not run into the next.

> **ONE-LINE PLAN**  Count carefully, answer clearly, and let the dramatic fist
> handle every emphatic No.

<!-- PAGEBREAK -->

## Gun.Smoke

**Profile:** `program_g` / matrix code `G`

**Your mission:** Walk the scrolling frontier, defeat the bandits, find or buy
each wanted poster, and collect the bounty by beating the stage boss.

| Do this | See it | Result |
| --- | --- | --- |
| Move whole hand | <img src="images/gestures/actions/whole-hand-movement.png" alt="Move the whole hand in four directions" width="96"> | Walk in that direction |
| Curl index finger | <img src="images/gestures/actions/finger-curl.png" alt="Curl the index finger" width="72"> | A: shoot diagonally right |
| Push toward camera | <img src="images/gestures/actions/push-toward-camera.png" alt="Push the hand toward the camera" width="72"> | B: shoot diagonally left |
| Curl index while pushing | <img src="images/gestures/actions/index-push-combination.png" alt="Combine a finger curl with a push toward the camera" width="96"> | A+B: shoot straight ahead |
| Curl thumb and ring finger | <img src="images/gestures/actions/thumb-finger-combination.png" alt="Combine a thumb curl with another finger curl" width="96"> | Suppress all action for menus |

**Play smart:** A stage keeps looping until you obtain its wanted poster. Keep
your palm level while walking; wrist roll can add a left/right movement command.
Use index-plus-push when you need the straight-ahead shot.

> **ONE-LINE PLAN**  Find the poster, build an A+B rhythm, and keep moving.

<!-- PAGEBREAK -->

## Knight Rider

**Profile:** `program_i` / matrix code `I`

**Your mission:** Drive KITT from city to city, avoid roadside hazards, destroy
the criminals ahead, and reach each destination before the timer expires.

| Do this | See it | Result |
| --- | --- | --- |
| Roll wrist left / right | <img src="images/gestures/actions/wrist-roll.png" alt="Roll the wrist left or right" width="96"> | Steer left / right |
| Curl index finger | <img src="images/gestures/actions/finger-curl.png" alt="Curl the index finger" width="72"> | Accelerate |
| Lower hand | <img src="images/gestures/actions/move-down.png" alt="Lower the whole hand" width="72"> | Brake |
| Push toward camera | <img src="images/gestures/actions/push-toward-camera.png" alt="Push the hand toward the camera" width="72"> | Accelerate plus turbo boost |
| Curl thumb | <img src="images/gestures/actions/thumb-curl.png" alt="Curl the thumb" width="72"> | Fire weapons |

**Play smart:** Keep the wrist near center on straight roads; large steering
rolls are for real turns. Hold index curl for normal speed and reserve the
forward push for a clean burst when the road opens.

> **ONE-LINE PLAN**  Index down, eyes forward, small steering corrections -
> then push for turbo when KITT has room to run.

<!-- PAGEBREAK -->

## Take Power Glove Vision off-script

The included game profiles are starting points, not a velvet rope around eight
approved cartridges. Programs A-I emit ordinary NES controller inputs, so the
real game is finding unexpected combinations that feel good. Programs A, D,
and H deliberately ship without a default ROM assignment because they are the
project's invitation to experiment.

### Start with A, D, and H

| Program | See it | Try it with | Know before playing |
| --- | --- | --- | --- |
| **A - Pinball** | <img src="images/gestures/actions/wrist-roll.png" alt="Rotate the wrist for the pinball tilt action" width="96"> | Pinball and games driven by two independent actions | Index curl is A, thumb curl is Up, wrist tilt is B, and pulling back toggles combined flippers. Ordinary directional movement is disabled. |
| **D - Mirror world** | <img src="images/gestures/actions/whole-hand-movement.png" alt="Move the whole hand in four directions" width="96"> | A game you already know well, a party challenge, or an inverted-direction accessibility experiment | Every direction is reversed. Thumb and index provide A and B. Expect your muscle memory to complain loudly. |
| **H - General play** | <img src="images/gestures/actions/finger-curl.png" alt="Curl a finger for a general-purpose action button" width="72"> | Two-button platform, maze, puzzle, and action games | Hand movement supplies the D-pad. Index and thumb pulse A and B, so games that require a long held button may be a poor fit. |

Program H is the best first guess. Program A is wonderfully specialized.
Program D turns a familiar game into a new coordination challenge without
changing the ROM or emulator.

### Try a combination

1. Launch the NES or Famicom game normally. An unregistered game safely turns
   gesture output off instead of inheriting the previous game's controls.
2. Open UNO Q **Setup**, choose Program A, D, H, or another Program A-I profile,
   then select **Save & restart tracker**.
3. Return to the game, select **Center hand**, and then **Start controller**.
4. Test movement, both action gestures, Start, and Select before committing to a
   long session. Stop the controller immediately if a gesture remains active.

The temporary choice lasts only until another game lifecycle command changes
the profile or turns gestures off.

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

For every Program A-I gesture, see the illustrated
`bad-street-brawler-programs.md` field manual. For registry validation and
manual profile commands, see `CONFIGURATION_REFERENCE.md`.

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
- [Gun.Smoke NES gameplay reference](https://strategywiki.org/wiki/Gun.Smoke_%28NES%29/Gameplay)
- [Knight Rider NES instruction manual](https://www.retrogames.cz/manualy/NES/Knight_Rider_-_NES_-_Manual.pdf)

The gesture drawings are original Power Glove Vision project illustrations made
for this guide. They deliberately avoid game screenshots, box art, characters,
and publisher logos.

Power Glove Vision is an independent MIT-licensed hobbyist project by Iain
Bennett. Nintendo, NES, Power Glove, and all game titles and marks belong to
their respective owners. No ROM images or original game artwork are distributed.
