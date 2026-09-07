# Existing sample review and smoothing model

The gameplay and dot recordings contain aggregate timings and sampled validity;
they do not retain recognized, flow, selected, and filtered coordinates for each
individual move. They cannot establish how many camera images or presented game
frames contained intermediate hand positions. Receiver publications are not
necessarily new measurements or different coordinates.

## Observed evidence

| 30-second window | Valid Controller samples | Observed tracking losses |
| --- | ---: | ---: |
| Earlier flow revision, dot movement | 579/591 (98.0%) | 6 |
| Recognition fallback, fast dot movement | 447/589 (75.9%) | 34 |
| Recognition fallback, actual gameplay | 568/590 (96.3%) | 3 |

These were different physical movements, not controlled before/after trials.
In gameplay, 395/590 polls reported `flow_unavailable`, 61 reported
`flow_seed_unavailable`, and one reported `correction_budget`. Fallback therefore
frequently delivered recognition coordinates rather than a newer flow estimate.
These are sampled frame counts, not distinct recognition-result counts.
The receiver observed 1,367 distinct valid publications in 30 seconds, not 1,367
new recognized positions or displayed images.

## Smoothing-only experiment

`scripts/analyze-motion-samples.py` exercises the actual native movement engine
with an ideal instantaneous measured-position step. It assumes 60 updates/second,
no input noise or loss, and the code defaults (minimum .70, maximum 1.00, motion
boost 4.00). Read-only verification found those same values in the Controller profile
configuration and no custom worker `--config` argument. Personal tuning overlays
change gesture thresholds, not these smoothing settings.

| Step in normalized camera X | Time from first step sample to 95% of target |
| --- | ---: |
| 0.010 | 200 ms |
| 0.025 | 200 ms |
| 0.050 | 167 ms |
| 0.100 | Immediate on first sample |
| 0.200 | Immediate on first sample |

With smoothing disabled, every modeled step passes through on its first sample.
That comparison does **not** measure the jitter cost of disabling smoothing.
The elapsed times exclude capture, recognition, transport, game simulation and
display. They must not be added to independent timing percentiles. The final
five-percent criterion includes a small settling tail; it is not a delay before
movement begins.

The speed-dependent behavior deserves attention: the current coefficient uses
position error, then adjusts for elapsed time. It is adaptive, but is not a One
Euro velocity-based filter. Large errors can bypass damping while small aiming
corrections retain it. This is a plausible contributor to the reported difficulty
catching and directing the ball, not proof of the complete cause.

Prediction accuracy cannot be tested from these aggregate reports. A predictor
can extrapolate an old measurement, but abrupt stops and reversals can cause
overshoot. Do not fit or enable prediction using these reports as ground truth.

## Prepared trace extension

The optional finite diagnostic trace now includes, on each vision event:

- New recognition completion, its original capture timestamp, X/Y, confidence,
  and detection flag. In-flight frames contain no fabricated recognition event.
- Accepted anchor's original capture timestamp.
- Attempted optical-flow X/Y and a separate acceptance flag; a correction that
  exceeded its budget must not be counted as accepted flow.
- Selected normalized X/Y, fallback reason, and invalid-input reason.
- Final filtered normalized X/Y, smoothing parameters, and mapped native axes.

Capture sequence/timestamp and transport sequence remain available for correlation.
Raw and filtered normalized coordinates share camera space; native axes use the
player's reach mapping. Invalid selected coordinates are null. A repeated source
is identifiable by anchor timestamp and must not be treated as a fresh velocity
measurement. The existing trace remains opt-in, finite, buffered, and asynchronous.
No video is recorded by this extension.

The instrumentation was subsequently deployed with the medium-jump trial below;
trace collection has not yet been enabled. Before the next physical trial,
enable a finite trace, then record the real hand
and cabinet screen together with the iPhone. Test small corrections, a large move,
a stop, and a reversal. Trace replay can compare smoothing outputs, while video
supplies physical timing and overshoot evidence. Cross-device clocks require
alignment; do not subtract them directly.

Reproduce the offline report with:

```sh
python3 scripts/analyze-motion-samples.py \
  --samples-dir /tmp/uno-dot-baseline-x8heur1f \
  --output /tmp/new-motion-analysis.json
```

Analyze one finite per-frame trace without replaying controller input:

```sh
python3 scripts/analyze-motion-trace.py /tmp/controller.trace.json \
  --output /tmp/controller-motion-analysis.json
```

For a controlled directory whose filenames follow
`min0.70-boost8.trace.json`, compare every configuration with:

```sh
python3 scripts/compare-motion-matrix.py /tmp/controller-motion-matrix \
  --output /tmp/controller-motion-matrix.json
```

Both tools create new reports rather than overwriting existing evidence. Their
settling estimates describe normalized software coordinates, not physical
hand-to-screen latency.

## Medium-jump and bounded extrapolation trial

The optional `motion_coordinate_boost` overrides the boost only in experimental
`update_native_motion`; null preserves the baseline value. The Controller experiment
uses boost 15.0 instead of the baseline 4.0, with minimum .70. An additional
experimental `motion_coordinate_max` cap is currently 1.30, allowing bounded
extrapolation beyond the newest measured position. This is an error relative to
the filtered position, not a speed threshold or a percentage of the game screen.
It does not remove recognition age.

The actual-engine 60 Hz step model gives 0 ms additional settling time for .04
and .05 steps with boost 8, compared with 183 and 167 ms respectively at boost 4.
A .005 step remains damped (200 ms to 95%, previously 217 ms). Noise and physical
response still require the paired recording. Baseline synchronous tracking is
unchanged. Both experimental overrides are reversible by removing them from the
UNO recognition configuration; values above 1.00 can overshoot on stops and
reversals. Trace collection must be explicitly enabled for a physical test.

## Six-configuration trace matrix

The matrix varied minimum smoothing and experimental motion boost while holding
the 250 ms freshness limit, 320 px flow width, 25 ms correction budget, and
maximum smoothing 1.00 fixed. Each window produced a finite trace with zero
dropped records. The analysis uses `scripts/compare-motion-matrix.py`.

| Minimum / boost | Vision events | Valid % | Losses | Age p95 (ms) | Medium settling p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.70 / 4 | 834 | 69.18 | 14 | 104.5 | 0.0 |
| 0.70 / 8 | 751 | 56.72 | 17 | 175.0 | 0.0 |
| 0.70 / 12 | 895 | 90.17 | 7 | 87.2 | 84.6 |
| 0.85 / 4 | 884 | 89.37 | 4 | 104.1 | 114.0 |
| 0.85 / 8 | 886 | 97.74 | 1 | 85.4 | 96.9 |
| 0.85 / 12 | 897 | 97.44 | 2 | 83.1 | 63.8 |

These windows did not contain a controlled, repeated movement sequence, so the
rows cannot select a production candidate. Validity and recognition age varied
enough to confound settling comparisons. The results are a harness check and
preliminary range, not proof that 0.85 / 12 is better. The live setting was
restored to 0.70 / 8; calibration was unchanged.

## Controlled three-window follow-up

The follow-up repeated the same center, small-correction, medium-jump, reversal,
and center sequence for the baseline and two candidates. All three finite traces
had zero dropped records.

| Configuration | Vision events | Valid % | Losses | Age p95 (ms) | X error median / p95 | Medium settling p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.70 / 8 (baseline) | 778 | 94.47 | 6 | 87.5 | 0.0011 / 0.0122 | 120.8 |
| 0.85 / 8 | 883 | 92.87 | 5 | 91.5 | 0.0006 / 0.0052 | 17.9 |
| 0.85 / 12 | 894 | 90.27 | 7 | 111.5 | 0.0004 / 0.0041 | 112.1 |

The controlled follow-up showed `0.85 / 8` was a useful intermediate smoothing
candidate, but later gameplay testing found it too floaty. The live experiment
was returned to minimum smoothing 0.70 and then raised to boost 15 with cap 1.30.
Those later values are a user-driven exploratory setting, not a production
default; repeat controlled traces before promoting them.
