# Matrix display guide

The blue LED matrix on the UNO Q is PowerGlove Vision's status display. It tells
you which mode is active and helps distinguish startup, practice, tracking, and
pairing. It does not show a game's score or confirm that a game accepted a button.

This guide describes the current Arduino sketch. Photos of the physical display
will be added later; the descriptions below are usable without them.

## Recognize the display

| What you see | What it means | What to do |
| --- | --- | --- |
| Board boot logo or system animation | The UNO Q's system software is starting, before PowerGlove Vision controls the display. | Wait for the app's hourglass or normal display. |
| Pulsing hourglass | The sketch has started and is waiting for the app, or the app is loading vision resources. | Allow startup to finish. If it persists, check Dashboard. |
| Glove animation with moving cuff, curling fingers, and a spark | Gestures are off; the app is in its idle mode. | Open Glove Academy to practice, or choose a game profile on Dashboard. |
| A large scanning **L** | Glove Academy lessons are active. L stands for lessons. | Practice the moves shown in your browser; controller output is paused. |
| A large scanning **T** | Gesture tuning is active, including hand setup. | Follow the recording, preview, and save instructions in Glove Academy. Controller output is paused. |
| A steady **A-I**, **BS**, or **GB** | A game profile is selected, but a calibrated hand is not currently being reported as tracked. | Show your hand and check tracking/calibration on Dashboard. |
| **A-I**, **BS**, or **GB** gently changing brightness | The app reports a detected, calibrated hand for that profile. | Check Dashboard's controller status before playing. This pulse alone does not mean controls are enabled. |
| **ID**, characters, **PN**, and digits repeating | Secure pairing is showing the device identity and temporary PIN. | Follow the Connection page; read each group in order. |
| A flashing **X** | The app has requested an error display. | Read Dashboard's error message before deciding whether to reconnect the camera or restart. |
| A blank matrix | The display has been turned off, the app is stopping, or the board has not yet reached the sketch's display stage. It may also have lost power. | Use the browser and board power indicators to distinguish these cases. Blank does not prove shutdown is complete. |

## Startup: logo, hourglass, then your mode

A typical startup with **Gestures off** selected is:

1. The board shows its system boot display.
2. When the Arduino sketch starts, it draws an hourglass immediately.
3. The hourglass keeps moving while the sketch connects to Linux and waits for app status.
4. Once the app reports idle mode, the glove animation begins.

With an active startup profile, the later display can instead be its profile
letters. Opening Glove Academy selects **L**; enabling tuning selects **T**.
These mode displays can appear while their camera resources are still starting.
Use the browser's startup message for that detail.

The hourglass has five frames, changing about every 220 milliseconds. It is a
repeating activity indicator, not a percentage, countdown, or promise that startup
will complete. Background library preloading can continue after the app becomes
idle and shows the glove. An hourglass is not required to stay visible throughout
that background work.

The system controls the interval before the sketch starts. PowerGlove Vision
cannot show its hourglass during that earlier interval. Cold-boot transitions
still need confirmation on the physical board. If the hourglass never gives way
to a mode display, open Dashboard and check whether the app is reachable and what
startup or error message it reports. See [startup diagnostics](CONFIGURATION_REFERENCE.md#vision-startup-and-timing).

## The idle glove show

The idle animation is a small repeating attraction sequence, not a reading of
your actual hand. It contains these beats:

1. An energy streak crosses the matrix.
2. A cuff slides into position.
3. The glove rises into view.
4. Its fingers curl, clench, and reopen.
5. A spark travels along the glove with a short trailing glow.
6. The outline brightens, settles, and pauses before the sequence repeats.

A flashing spark here does **not** mean you performed Glove Zap. This animation
means gestures are off. It is different from selecting a game profile and merely
pressing **Stop controller**: that keeps the camera/profile active and can leave
profile letters visible.

## Glove Academy: L and T

Both letters use the same effect: a dim letter, a brighter row scanning through
it, and a short glow behind that row. The scan advances about every 160
milliseconds. It is an activity animation, not a lesson-completion meter or a
recording timer.

**L** identifies ordinary lessons, even though the navigation section is now
called **Glove Academy**. **T** identifies tuning, including **Set up my hand**,
individual adjustments, and previewing thresholds. The browser shows which of
the three recordings you are on and whether a suggestion is ready to save.

Both modes pause controller output. After practice, use Dashboard to check the
selected profile and controller state; after tuning, explicitly start controller
delivery when ready to play. A pairing display can temporarily cover either
letter. Tracking details and pose failures remain in the browser rather than
being spelled out on the matrix.

## Game profile letters

| Letters | Selected profile |
| --- | --- |
| **A** through **I** | The corresponding reusable Program A-I profile |
| **BS** | Bad Street Brawler |
| **GB** | Super Glove Ball |

For example, **GB** is what you should expect with Super Glove Ball selected.
It stays steady when the app is not reporting both hand detection and completed
calibration. It alternates between bright and dim about every 360 milliseconds
when both are reported. The characters remain the same: the animation does not
identify individual finger curls, movements, or button presses.

The important distinction is **tracking versus delivery**. A pulsing **GB** can
appear while controller output is stopped. Confirm **Start controller** has been
used and Dashboard shows output enabled, then confirm the action in the game.
The matrix does not acknowledge RetroPie receipt or the game's response.

A generic **PG** ready symbol or a small pulsing tracking symbol can appear when
no recognized profile identifier is available. These are fallback displays;
normal named game profiles use their letters. They do not represent extra games
or new gesture commands. If you expected **GB** or **BS**, check the selected
profile on Dashboard.

## Pairing: ID and PN

During secure pairing, the small display presents the information in pieces:

1. **ID** announces the device certificate identity.
2. Seven hexadecimal characters follow in groups of two, with the last character shown alone.
3. **PN** announces the temporary six-digit PIN.
4. Three pairs of digits follow, preserving leading zeroes.
5. The sequence repeats so you can read it again.

Each step lasts about 650 milliseconds; the nine-step loop takes roughly six
seconds. Read left to right across each pair, then concatenate the groups. Do not
mistake **PN** for a game program or use the certificate identity as the PIN.

Use the Connection page's certificate-comparison and PIN instructions. The
pairing sequence temporarily takes priority over ordinary mode updates for the
pairing display window (normally two minutes), then normal status can resume.
A shutdown/off request can clear it sooner. Readability of this sequence does not
prove pairing succeeded; check the Connection page's result.

For public photographs, use a clearly marked demonstration sequence or obscure
live pairing digits. Never publish an active PIN or connection credentials. See
[secure pairing](INSTALL_README.md) for the full procedure.

## Errors, pauses, and a blank display

The error **X** alternates with a blank frame about every 420 milliseconds. That
intentional dark half of its blink is different from a continuously blank
matrix. The X does not encode a specific fault: Dashboard provides the message.
Some modes prioritize their own letter or idle animation, so the absence of an X
is not proof that no camera or startup error exists.

A blank display alone does not prove the board is safe to unplug. Use the normal
Shutdown procedure and its completion guidance. If the board should be running,
check its power, wait for boot to finish, and try Dashboard. If the web app works
but the display stays blank, record what appeared immediately before it went
blank and whether restarting the app changes it.

## Photo examples to add later

The guide is complete as a text reference. These are useful future examples;
there are no missing-image links to fill before using it.

| Example | What to capture | Suggested caption |
| --- | --- | --- |
| System boot | The board's logo before the app display | System startup, before PowerGlove Vision takes over |
| Startup hourglass | A short clip, or two successive frames | PowerGlove Vision is starting |
| Idle glove | Open glove, clenched glove, and spark frames | Gestures off: the idle glove animation |
| Academy lessons | L with its brighter scanning row | Glove Academy lessons; controller output paused |
| Tuning | T with its brighter scanning row | Personal tuning; follow the browser's recording steps |
| Super Glove Ball | Steady GB and a clip of pulsing GB | GB identifies the profile; the pulse indicates tracking |
| Programs and Brawler | One program letter and BS | Selected program or game profile |
| Pairing | ID and PN labels with synthetic or obscured values | Pairing information arrives in successive groups |
| Error | X plus the associated non-sensitive Dashboard message | Check Dashboard for the cause |

Short clips show scanning and pulsing more clearly than a single photo. Keep the
matrix upright, reduce exposure enough to separate adjacent LEDs, and include a
little of the case for orientation. Record the selected mode and whether
controller output was enabled. Describe photos as examples from the tested
board, since camera exposure can change the apparent brightness and shape.
