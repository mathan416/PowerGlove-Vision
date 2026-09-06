# Nestopia PowerGlove core

`lr-nestopia-powerglove` is a separately named modification of the libretro
Nestopia core. It is built from upstream revision
`5a1cd378cb46ca9ccc2dd6f8b2b6a79ab986052e` with
`nestopia-powerglove.patch`. It is not an MIT-licensed component of
PowerGlove Vision.

PowerGlove Vision's additions and corrections are recorded separately in
[`CHANGES.md`](CHANGES.md). The patch retains upstream source-file headers;
this project does not replace them with PowerGlove Vision attribution.

Upstream Nestopia and the resulting modified core are distributed under the
GNU General Public License, version 2. The pinned upstream source contains the
author notices and complete `COPYING` text. The local installer copies that
license beside the installed core. Applying or distributing this patch as part
of a modified Nestopia build remains subject to those GPL terms.

Upstream source: <https://github.com/libretro/nestopia>

PowerGlove Vision patch SHA-256:
`3172ef337bfbb37c67ea2507544f21c7de3cedd25733802b062b0d02ef679397`

The ordinary PowerGlove Vision release distributes this patch and reproducible
build recipe, not a compiled core. The RetroPie installer can download the
pinned source and build it locally as an explicit option. ROM images are never
downloaded, copied, or included.

If compiled cores are published later, provide a separate build for each tested
RetroPie architecture. Accompany every binary release with its exact complete
corresponding source archive, this patch, build instructions, upstream notices,
and the GPLv2 license. Keep the FCEUmm fallback available.

## Controller transport compatibility

PowerGlove Vision v0.3.2-rc.6 requires matching signed-controller software on the Controller and RetroPie. The receiver validates that transport before publishing the existing version-1 native-state record; this candidate does not change the core patch or require a native-core rebuild. Follow the [coordinated upgrade instructions](../../docs/CONFIGURATION_REFERENCE.md#signed-controller-transport-and-upgrades). Native gameplay and full camera-to-display latency still need validation on the candidate; FCEUmm remains the explicit fallback.
