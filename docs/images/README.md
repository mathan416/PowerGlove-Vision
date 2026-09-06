# Guide screenshots and illustrations

Refresh application screenshots from the repository root with:

```sh
PYTHONPATH=src python scripts/capture-guide-screenshots.py
```

The development environment needs Playwright and Chrome. The script renders the
current application templates against isolated sample responses and temporary
player state. It never contacts a live Controller or RetroPie. Camera areas use
a labelled placeholder; pairing inputs are non-secret examples. These images
illustrate the interface, not measured recognition, delivery, or hardware status.

The capture covers Dashboard, Play, Academy learning and personalization,
player settings and restoration, Setup, Games, Help, attract settings, and all
guided-pairing states. Existing filenames are shared across guides, so refresh
them once and rebuild every affected PDF with `scripts/build-docs-pdf.py`.
Review images and PDF pages before publishing. The script also checks the
Security network table at phone, tablet, and desktop widths.

Gesture artwork, architecture illustrations, and physical matrix photographs
are separate from application screenshots. Preserve the intentional extra-finger
artwork. See [asset provenance](../THIRD_PARTY_COMPONENTS.md#documentation-and-website-assets)
and [compact web illustrations](web/README.md).
