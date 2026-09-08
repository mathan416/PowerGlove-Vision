# Project: PowerGlove Vision
# File: src/powerglove_vision/statistics_web.py
# Purpose: Share the optional Dashboard statistics preference across web pages.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Added the browser-local, default-off statistics preference.
# Full history: docs/CHANGELOG.md and Git history.

"""Share the browser's optional Dashboard statistics preference with Setup."""

STATISTICS_SWITCH = """<label class=check><input id=show-statistics type=checkbox role=switch aria-describedby=statistics-help> Show statistics</label>"""

STATISTICS_CONTENT = """<section class=card id=statistics-settings style="margin-top:14px" aria-labelledby=statistics-title>
<h2 id=statistics-title>Show statistics</h2>""" + STATISTICS_SWITCH + """
<p id=statistics-help>Show Controller output, Axes, Finger curl, Performance, and Recent events on the Dashboard. Off by default. When off, the Dashboard stops updating these details and collecting recent events. Camera and controller operation continue.</p>
<p>You can also switch statistics on or off directly on the Dashboard. This preference is saved in this browser.</p></section>"""

STATISTICS_SCRIPT = r"""(()=>{
const key='powerglove.showStatistics',toggle=document.getElementById('show-statistics');
let enabled=false;
function apply(value){enabled=value;toggle.checked=value;window.dispatchEvent(new Event('statisticschange'));}
function restore(){try{apply(localStorage.getItem(key)==='true')}catch(e){apply(enabled)}}
window.dashboardStatisticsEnabled=()=>enabled;
toggle.onchange=()=>{apply(toggle.checked);try{localStorage.setItem(key,String(enabled))}catch(e){}};
window.addEventListener('storage',e=>{if(e.key===key||e.key===null)restore()});
window.addEventListener('pageshow',restore);
restore();
})();"""
