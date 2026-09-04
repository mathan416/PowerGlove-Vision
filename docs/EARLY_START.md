# Early sketch startup (UNO Q)

The UNO Q installer includes this host helper and enables it for every boot.
The manual procedure below is for repair or an older installation. It leaves the Arduino sketch, hourglass frames, and
normal App Lab services unchanged.

The installed Arduino platform 1.0.0 loader clears the matrix after the system
boot animation and waits for App Lab to release the sketch. App Lab 0.13.0
builds with **Wait for App**. The helper uses the same release word as Arduino's
installed uploader, but without the uploader's reset, halt, or flash operations.
The existing sketch then supplies its own hourglass while Python starts.

## Scope and safeguards

`scripts/uno-q-early-start.py` runs on the UNO Q as the Arduino user. Without
`--release`, it only checks. It verifies the board identity, the selected startup
app, the cached Wait for App image header, and four 64-byte samples of installed
sketch memory against that cached image. This is a compatibility check, **not a
complete firmware integrity check**. It refuses mismatches, unexpected release
values, an unavailable router, or an unavailable debug interface. An already
released sketch is left alone. Debug listeners and reset pins are not enabled.

The helper uses the board's `/opt/openocd` tool and SWD pins, and writes only the
startup release word `0xCAFFEEEE` at `0x40036400`. These are specific to the
inspected UNO Q installation. Review them again after platform or board updates.
Do not run this helper concurrently with uploads or other debugger tools.

The user service waits at most 30 seconds for the router service to be active;
that is not a guarantee that its internal initialization has finished. The loader
still waits for Linux's hardware readiness signal before starting the sketch.
There is no ordering dependency between this user service and App Lab. If the
helper loses that race, the debug connection can fail or find an already released
sketch; normal App Lab startup remains responsible. App Lab may subsequently
reset the sketch during its normal upload, so a brief second startup animation
is possible. Confirm this visually before adopting a permanent helper.

## Installation

The helper requires an existing lingering Arduino user manager (`loginctl
show-user arduino -p Linger`). Copy the helper to
`~/.local/lib/powerglove/uno-q-early-start.py` and the supplied service from
`uno-q/powerglove-early-start.service` to `~/.config/systemd/user/`.
Then, as the Arduino user:

```sh
mkdir -p ~/.local/state
systemctl --user daemon-reload
systemctl --user enable powerglove-early-start.service
```

The enabled user service runs on every boot. No armed marker is needed. It makes
one bounded attempt; failure leaves normal App Lab startup in control. Existing
one-boot installations should disable `powerglove-early-start-trial.service` and
remove its armed marker before enabling this service.

Inspect the result after boot:

```sh
journalctl --user -b -u powerglove-early-start.service --no-pager
```

Remove the helper:

```sh
systemctl --user disable powerglove-early-start.service
rm -f ~/.local/state/powerglove-early-start-armed
rm -f ~/.config/systemd/user/powerglove-early-start.service
rm -f ~/.local/lib/powerglove/uno-q-early-start.py
systemctl --user daemon-reload
```

## Validation

On September 4, 2026, the controlled board test paused the idle Python container,
reset the microcontroller into its normal loader wait, observed `WAITING`,
released it, and observed `ALREADY_RELEASED` on a subsequent check. The router
recorded the sketch starting, and the Python container was restored with its
worker running. No sketch source or firmware was changed. Reading the complete
image exceeded the experiment's 20-second timeout, so the bounded sample check
replaced that approach. The debug connection also refused access while App Lab
was using it during startup.

The user confirmed the one-boot trial worked successfully on September 4, 2026.
For future board or platform changes, repeat the physical cold-boot check: watch the Arduino logo and heart,
measure the blank interval, confirm the existing hourglass appears earlier, and
confirm the usual glove animation and controls still work. Check for a second
reset when App Lab uploads. A successful manual release alone does not establish
cold-boot timing or readiness for release.
