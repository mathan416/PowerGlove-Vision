# PowerGlove Vision security policy

Use PowerGlove Vision on a trusted home or workshop network. This policy
explains how to report a vulnerability and which protections the project
expects pairing, networking, and shutdown code to maintain.

## Supported code

Security fixes will be available on the current `main` branch and included in
the next tagged release. Older snapshots may lack pairing, network, dependency, or
shutdown protections and should be upgraded before troubleshooting them.

## Reporting a vulnerability

Please do not publish credentials, pairing codes, tokens, private device
configuration, or working exploit instructions in a public issue.

1. Open the repository's **Security** tab and look for private vulnerability reporting.
2. Submit a private report with the information below. Remove secrets from every attachment.
3. If private reporting is unavailable, open a minimal public issue asking for a private contact channel; include no exploit details or secrets.

Include these details in the private report:

- the affected commit or release;
- the PowerGlove Vision Controller, RetroPie, browser, and network environment involved;
- concise reproduction steps and the observed result;
- the security boundary that was crossed;
- logs or screenshots after removing tokens, passwords, pairing codes, local addresses, and unrelated personal information.

This project does not currently offer a bug bounty or a guaranteed response time.

You can report controller-mapping, camera-compatibility, and game-profile
problems in public issues after removing sensitive information from the logs.

## Security model

The **PowerGlove Vision Controller** is the Arduino UNO Q device that owns the
camera, recognition pipeline, local website, and controller sender.

PowerGlove Vision is designed for a trusted home or workshop network. The PowerGlove Vision Controller
performs hand tracking and sends virtual-controller state to RetroPie. RetroPie
sends per-game profile changes back to the PowerGlove Vision Controller. Neither device should be
treated as an Internet-facing service.

The main protected assets are:

- the shared controller token;
- the PowerGlove Vision Controller and RetroPie operating systems;
- the privileged `/dev/uinput` receiver;
- the physical pairing display and single-use PIN;
- the fixed-purpose PowerGlove Vision Controller shutdown and USB-camera recovery helpers;
- the integrity of the App Lab installation ZIP, MediaPipe wheel, bundled or downloaded model, and Arduino dependencies.

The project does not attempt to protect a device after an attacker obtains root
access, physical storage access, or control of the trusted local network and
both paired hosts.

## Pairing boundaries

The PowerGlove Vision Controller and RetroPie share one random token of at least 16 characters. The
active token belongs only in the PowerGlove Vision Controller's private `data/device.json` and
RetroPie's `/etc/powerglove/token`. It must not be committed, placed in a shell
argument, stored in `launcher.json`, or included in a screenshot or log.

The supervised vision worker reads its token using `--device-config`, keeping
the secret out of process arguments. Device settings are created and replaced
atomically with mode `0600`. Legacy `--token` remains a compatibility option for
manual commands; prefer `--token-file` or `--device-config` for the worker.
Browser mutation routes reject cross-site origins, and connection-setting writes
require JSON. These browser protections do not add local-user authentication or
change the trusted-network model.

The recommended setup path uses a short-lived one-time code to authenticate
the RetroPie pairing server over pinned TLS. Password pairing uses authenticated SSH. After the initial connection
establishes trust, subsequent connections verify the saved remote host key.
The password is not placed on the process command line.

Both browser pairing methods require you to open secure Setup, compare the
browser certificate identity with the identifier on the PowerGlove Vision Controller matrix, and
enter the single-use PIN shown on the matrix before the token is released. This is a local certificate-pinning ceremony, not
validation by a public certificate authority.

Pairing sessions limit how long a connection handshake can take and how long
the pairing service remains available. Reusing a PIN, removing
the physical display requirement, accepting pairing credentials over ordinary
HTTP, or extending the listener indefinitely weakens the intended boundary and
requires explicit security review.

## Network exposure

| Port | Protocol | Direction | Boundary |
| --- | --- | --- | --- |
| `55355` | UDP | PowerGlove Vision Controller to RetroPie | Authenticated virtual-controller packets |
| `55356` | UDP | RetroPie to PowerGlove Vision Controller | HMAC-authenticated profile commands and acknowledgements |
| `55357` | TCP/TLS | Pairing client to temporary server | Short-lived code-pairing exchange only |
| `8088` | HTTP | Browser to PowerGlove Vision Controller | Local dashboard, Play, public Help guides, diagnostics, and ordinary controls; no pairing credentials accepted |
| `8443` | HTTPS | Browser to PowerGlove Vision Controller | Protected setup and pairing operations |

Keep these ports on a trusted LAN. Do not configure router port forwarding,
public reverse proxies, cloud tunnels, or Internet firewall exceptions for
them. Guest Wi-Fi and untrusted shared networks are inappropriate unless the
devices are isolated by firewall rules or a dedicated VLAN.

The profile-control brick publishes UDP `55356` and forwards packets to the
worker on the private container network. It has no token or private data mount,
runs without elevated privileges, and bounds packet sizes, pending exchanges,
and reply lifetime. Authentication remains in the worker; the relay never
creates an acknowledgement. A signed acknowledgement confirms queue admission,
not completed camera startup or enabled gameplay delivery.

Controller and profile UDP traffic is authenticated but not encrypted. Anyone
with access to the local network can observe packet timing and size even when
they cannot create accepted input without the token. The dashboard can expose
camera imagery and operational status to clients that can reach it, so network
access to port `8088` is itself sensitive.

The Help library serves a fixed list of public Markdown guides and images from
the installed application. It must not expose `data/`, the machine-specific
cheat sheet, arbitrary filesystem paths, or pairing credentials. Markdown HTML
is not executed, unsafe link schemes are rejected, and image requests are
confined below `docs/images`.

The dynamic **This cabinet** page accepts only a validated hostname or IP from
the browser `Host` header and combines it with `public_config()`. It may show
local network addresses, ports, profile selection, camera selection, and
whether pairing is configured, but it must never return the token value,
passwords, private files, or arbitrary Host-header content.

## Shutdown and camera-recovery permissions

The web process does not receive general `sudo` permission. A root-owned
systemd path unit watches one fixed file in the application data directory. A
matching oneshot service deletes that file and requests a non-blocking Linux
halt.

The dashboard route requires an explicit confirmation header and only creates
the fixed request when the host installer has placed the private
`.shutdown-enabled` marker. These checks reduce accidents and prevent command
substitution; they do not make the dashboard safe for public network exposure.
Anyone able to use the reachable dashboard may still cause a denial of service
by shutting down the PowerGlove Vision Controller.

A root-owned tmpfiles rule recreates only that fixed readiness marker during
boot. It grants no command execution and does not change the container's
privileges.

Camera recovery follows the same fixed-request pattern with separate path and
service units. Installation may occur without a camera. When exactly one UVC
camera is healthy, the root-owned helper writes its identity and its actual
parent hub's identity and physical USB path to the root-owned
`/etc/powerglove-camera-recovery.json` allowlist. A later healthy sighting safely
updates that association if the camera has moved. During an outage the helper
validates both the stored path and hub identity and resets only that hub; it
never accepts a device path from the web application or guesses among hubs.

The helper consumes the request before acting, permits one request per camera
outage, and enforces a root-owned cooldown. Before first enrollment it refuses
to reset anything. A client able to activate vision could still cause one brief
USB interruption during a real camera outage, so the web interface remains
suitable only for a trusted LAN.

Keep both helpers' path units, service units, scripts, and tmpfiles rules owned
by root. Unit and rule permissions are `0644`; the camera helper is `0755`.
Do not replace the fixed `ExecStart` commands with user input, a shell string,
or an arbitrary command runner. Remove or disable the corresponding helper set
if remote shutdown or camera recovery is not wanted.

## Dependency and release integrity

- The App Lab installation ZIP is generated and verified; it is not maintained as a changing source-controlled binary.
- The custom MediaPipe wheel's provenance and checksum are recorded in `THIRD_PARTY_COMPONENTS.md`.
- Google's Hand Landmarker model is installed from the bundled copy, with its pinned download as a fallback only when that copy is absent. Both paths must match the expected SHA-256 digest before atomic installation; the package verifier also checks the bundled model and license text.
- The optional Nestopia core is built from one pinned upstream commit and one checksum-recorded local patch. Its build rejects changes to Nestopia's original Power Glove license header, and installation keeps the upstream `COPYING` file and the local modification ledger beside the separately named core. Stock Nestopia and FCEUmm are not replaced.
- Arduino library versions are pinned in `sketch/sketch.yaml`.
- GitHub Actions rebuilds and inspects documentation and the App Lab installation ZIP on every pull request and push to `main` or `dev`.

Changing a download URL, checksum, dependency source, pairing primitive,
network binding, file permission, or privileged service requires focused review
and corresponding tests and documentation.

## Paired game editing and gesture tuning

The separate RetroPie Games service listens on TCP `55358`. Only the paired UNO
proxy uses it; browsers call the UNO website. Requests and replies use a distinct
HMAC-authenticated protocol. Server challenges expire after fifteen seconds and
are consumed once. The shared token never goes to the browser. This protects
message integrity; the LAN transport does not encrypt ROM filenames.

The service accepts only registry reads, validated writes, and restoration. File
locations come from the administrator's launcher configuration, never from browser
input. Writes use revision checks, atomic replacement, and a previous valid backup.
The service has bounded document sizes, pending challenges, and socket timeouts;
it runs separately from controller input delivery. Its systemd unit confines writes
to the configured registry directory and removes device access and capabilities.

The new Games and Tune browser actions require JSON, an explicit action header,
and matching Origin when supplied; cross-site browser requests are rejected.
They retain the existing trusted-LAN administration model, not per-user accounts.
Normal personalization contains numerical thresholds only. Measurements are held briefly
in memory, previews expire with the owning session, and camera images are not saved.
Tuning suppresses controller delivery even if a game launches or another Dashboard
requests input. Saved settings are validated and atomically replaced.

The optional Advanced diagnostic is the only Academy path that records video.
It is explicitly started and user-paced, remains on the PowerGlove Vision Controller, and is deleted
immediately after aggregate analysis or cancellation. An abandoned AVI expires
after 30 minutes. Its downloadable JSON contains aggregate continuity, latency,
confidence, lighting, and recognized-state names only: no frames, landmarks,
tokens, addresses, or saved personal thresholds.

### Documentation screenshots

Documentation screenshots blur the complete camera image before capture. Keep
controls legible, but never publish unblurred camera frames or screenshots that
contain passwords, private tokens, or pairing codes. The reference images show
the interface; they are not saved gesture recordings.

### Personal hand setup and tuning data

Optional hand setup measures all five fingers; gesture tuning measures selected
components. Both use three short sets of numerical samples in memory. The
version-3 `data/gesture-tuning.json` file stores player names, activation/release
pairs shared across game profiles for each player, Academy progress, and a
required-center flag, plus a bounded pending reference during a calibration
restore. Versions 1 and 2 migrate with private backups. Complete hand-setup
exports contain a name, threshold pairs, and a neutral reference. They exclude
camera images, landmarks, Wi-Fi credentials, pairing tokens, and lesson progress.
Restoring calibration requires an explicit same-position confirmation and strict
finite field validation. A persisted restore resumes after interruption with
output gated; Start controller is still required. Neutral calibration remains
Controller-wide in `data/calibration.json`.
The installer never packages a maintainer's neutral reference: camera position,
player distance, and wrist pose make it installation-specific. Preserve both
files during updates. Expiry or discard removes temporary preview
state, not saved settings. Numerical validity and sample separation do not prove
a pose was performed correctly; preview feedback and physical testing are still
required before release.

## Wi-Fi status sampler

The Wi-Fi sampler runs as `arduino` and only reads host wireless carrier state.
It publishes a small expiring record in `data/wifi-status.json`; it does not
collect SSIDs, addresses, passwords, or scans, and cannot change network settings.
The application retains no controller states while hostname resolution runs in
the background. Controller message authentication remains the existing trusted-LAN
protocol; a signed-message migration still awaits a separate decision.
