#!/bin/sh
# Copyright (c) 2026 Iain Bennett. All rights reserved.
# Call this from the cabinet's existing runcommand-onstart.sh, preserving its
# controller, RGB, and trackball setup. RetroPie supplies these four arguments.
/opt/powerglove/bin/powerglove-retropie-hook start "$1" "$2" "$3" "$4"
exit 0
