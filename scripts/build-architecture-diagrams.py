#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/build-architecture-diagrams.py
# Purpose: Render maintainable architecture flow diagrams for Help and the PDF guide.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added seven source-defined architecture diagrams.
# Full history: docs/CHANGELOG.md and Git history.

"""Render architecture diagrams with Pillow; no camera imagery is used."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/images/architecture'


def font(size):
    """Use an available scalable sans-serif font across developer machines."""
    for name in ['/System/Library/Fonts/Supplemental/Arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'DejaVuSans.ttf']:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    raise RuntimeError('Install Arial or DejaVu Sans to render diagrams')


def diagram(name, title, nodes, edges, footer):
    """Draw a three-column flow with explicitly routed directional arrows."""
    im = Image.new('RGB', (1560, 950), '#f4f7fb'); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1560, 100), fill='#07111f'); d.text((40, 28), title, font=font(36), fill='white')
    positions = {}
    for key, col, row, heading, body in nodes:
        x, y = 45 + col * 510, 160 + row * 240
        positions[key] = (x, y, x + 450, y + 150)
    for a,b in edges:
        x1,y1,x2,y2=positions[a];u1,v1,u2,v2=positions[b]
        if y1==v1:
            points=[(x2,(y1+y2)/2),(u1,(v1+v2)/2)] if x1<u1 else [(x1,(y1+y2)/2),(u2,(v1+v2)/2)]
        elif x1==u1:
            points=[((x1+x2)/2,y2),((u1+u2)/2,v1)]
        else:
            points=[((x1+x2)/2,y2),((x1+x2)/2,y2+45),((u1+u2)/2,y2+45),((u1+u2)/2,v1)]
        d.line(points, fill='#087ebd', width=7)
        px,py=points[-2];qx,qy=points[-1];angle=math.atan2(qy-py,qx-px)
        d.polygon([(qx,qy),(qx-20*math.cos(angle-.5),qy-20*math.sin(angle-.5)),(qx-20*math.cos(angle+.5),qy-20*math.sin(angle+.5))],fill='#087ebd')
    for key,col,row,heading,body in nodes:
        x,y,x2,y2=positions[key];d.rounded_rectangle((x,y,x2,y2),radius=16,fill='white',outline='#087ebd',width=3)
        d.text((x+20,y+16),heading,font=font(29),fill='#07111f')
        for i,line in enumerate(body.split('\n')):d.text((x+20,y+61+i*31),line,font=font(25),fill='#374151')
    d.text((45,905),footer,font=font(24),fill='#526175')
    OUT.mkdir(parents=True,exist_ok=True);im.save(OUT/(name+'.png'))


def main():
    """Build the diagrams used by the architecture Markdown and PDF."""
    diagram('system','01 / System boundaries',[
      ('cam',0,0,'USB camera','Images of the player'),('uno',1,0,'UNO Q / Linux','Vision, recognition, web UI'),('pi',2,0,'RetroPie / Linux','Receiver and virtual gamepad'),
      ('browser',0,1,'Browser','Dashboard, Learn, Tune, Setup'),('mcu',1,1,'UNO Q / microcontroller','Arduino sketch / matrix firmware'),('game',2,1,'RetroArch and game','Consumes ordinary gamepad input'),
      ('hooks',2,2,'Game-launch hooks','Select a profile on the UNO Q')],
      [('cam','uno'),('uno','pi'),('uno','mcu'),('pi','game')],
      'Browser <-> UNO web UI; game hooks -> UNO profile relay. These are separate control paths.')
    diagram('input','02 / One hand movement becomes game input',[
      ('a',0,0,'1. Camera frame','UVC capture through OpenCV'),('b',1,0,'2. Hand observation','MediaPipe landmarks + curls'),('c',2,0,'3. Gesture engine','Calibration + effective thresholds'),
      ('d',2,1,'4. Profile mapping','Held states, pulses and toggles'),('e',1,1,'5. Delivery gate','Enabled; no Learn or Tune'),('f',0,1,'6. UDP state packet','Session + sequence + token'),
      ('g',0,2,'7. Receiver checks','Token, session and sequence'),('h',1,2,'8. Linux uinput','Virtual gamepad state'),('i',2,2,'9. Game response','RetroArch mapping and gameplay')],
      [('a','b'),('b','c'),('c','d'),('d','e'),('e','f'),('f','g'),('g','h'),('h','i')],
      'Status and preview branch from the worker. Browser video is not in the controller delivery path.')
    diagram('modes','03 / Camera activity and controller delivery are separate',[
      ('off',0,0,'Gestures off','Camera closed; web UI available'),('play',1,0,'Active game profile','Camera opens; output is gated'),('learn',2,0,'Ordinary Learn / L','General profile; output paused'),
      ('idle',0,1,'Background preparation','Libraries can preload while off'),('gate',1,1,'Controller enabled?','Only gameplay can send states'),('tune',2,1,'Tune gestures / T','Single owner; output paused'),
      ('restore',2,2,'Exit or lease expiry','Restore selected vision mode')],
      [('off','idle'),('play','gate'),('learn','tune'),('tune','restore')],
      'Open Learn from either mode. After Tune, explicitly start controller delivery from Dashboard.')
    diagram('tuning','04 / Three recordings, preview, then an explicit save',[
      ('a',0,0,'1. Choose scope','All five fingers or one gesture'),('b',1,0,'2. Record open / rest','Three seconds at starting pose'),('c',2,0,'3. Record performed pose','Gesture, fist, or held movement'),
      ('d',2,1,'4. Record open / rest','Return fully; three seconds'),('e',1,1,'5. Analyze separation','Open high end vs performed low'),('f',0,1,'6. Preview and inspect','Check required fingers and release'),
      ('g',0,2,'7. Save for all profiles','Persist selected threshold pairs'),('h',1,2,'Or discard / expire','Remove temporary measurements'),('i',2,2,'Or retry failed samples','Too few samples or overlap')],
      [('a','b'),('b','c'),('c','d'),('d','e'),('e','f'),('f','g')],
      'Three seconds per recording; the complete pose must match in at least 90% of accepted samples.')
    diagram('settings','05 / Effective thresholds and calibration',[
      ('base',0,0,'Profile defaults','config/profiles.json'),('saved',1,0,'Saved personal pairs','data/gesture-tuning.json'),('preview',2,0,'Temporary preview','Only while Tune session lives'),
      ('engine',2,1,'Effective thresholds','Preview > personal > defaults'),('neutral',1,1,'Neutral calibration','data/calibration.json'),('obs',0,1,'Hand measurements','Position, scale, wrist and curls'),
      ('recognize',1,2,'Recognition + mapping','Shared finger and movement states')],
      [('base','saved'),('saved','preview'),('preview','engine'),('obs','neutral'),('neutral','recognize'),('engine','recognize')],
      'Top arrows show override priority, not file writes. Neutral calibration is a separate reference.')
    diagram('profile','06 / A game launch selects a gesture profile',[
      ('a',0,0,'1. RetroPie launches ROM','runcommand start hook'),('b',1,0,'2. Registry lookup','Exact ROM basename -> profile'),('c',2,0,'3. Signed request','UDP 55356 to UNO Q'),
      ('d',2,1,'4. App Lab relay','Forwards bytes; holds no token'),('e',1,1,'5. Worker validates','Accept request and apply profile'),('f',0,1,'6. New controller session','Release old state; reset sequence'),
      ('ack',1,2,'Signed acknowledgement','Reports request outcome')],
      [('a','b'),('b','c'),('c','d'),('d','e'),('e','f'),('e','ack')],
      'Acknowledgement returns through relay to RetroPie. Learn/Tune can keep delivery paused.')
    diagram('deployment','07 / Linux application and matrix firmware update separately',[
      ('source',0,0,'Reviewed project','Python, docs, assets, sketch'),('linux',1,0,'Linux application update','Sync files; recreate containers'),('runtime',2,0,'Website and vision worker','Preserve private data/ settings'),
      ('pins',0,1,'Pinned sketch profile','Board platform + library versions'),('compile',1,1,'Compile-only validation','Builds without flashing hardware'),('flash',2,1,'App Lab Run / restart','Builds and uploads MCU firmware'),
      ('check',2,2,'Verify on the device','Web health, matrix, live gameplay')],
      [('source','linux'),('linux','runtime'),('pins','compile'),('compile','flash'),('flash','check')],
      'Installing a platform alone changes neither application behaviour nor the running matrix firmware.')
    print('Built seven architecture diagrams')


if __name__ == '__main__':
    main()
