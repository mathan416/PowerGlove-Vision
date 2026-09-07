# Project: PowerGlove Vision
# File: scripts/benchmark-motion-correction.py
# Purpose: Compare native-motion correction revisions with synthetic frames.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Added a deterministic before/after correction benchmark.
# Full history: docs/CHANGELOG.md and Git history.
"""Synthetic frames and delayed recognition only: no camera, packets or game input."""
import argparse,hashlib,importlib.util,json,time,math,sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import cv2,numpy as np
from powerglove_vision.model import HandObservation
from powerglove_vision.tracker import TrackingResult
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--before',type=Path,required=True)
parser.add_argument('--after',type=Path,default=Path(__file__).resolve().parents[1]/'src/powerglove_vision/motion.py')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if args.output.exists():parser.error('Choose a new output file')
files={'before':args.before,'after':args.after}
rng=np.random.default_rng(10)
base=np.zeros((480,640),dtype=np.uint8);base[195:285,275:365]=rng.integers(40,240,(90,90),dtype=np.uint8)
frames=[cv2.cvtColor(cv2.warpAffine(base,np.float32([[1,0,x],[0,1,0]]),(640,480)),cv2.COLOR_GRAY2BGR) for x in range(-16,17)]

def summary(values):
 """Return compact percentiles for a non-empty timing sequence."""
 s=sorted(values)
 return {'count':len(s),'p50':s[math.ceil(.5*len(s))-1],'p95':s[math.ceil(.95*len(s))-1],'max':s[-1]} if s else {}

def run(lane, seconds=4):
 """Run one imported motion implementation against deterministic frames."""
 spec=importlib.util.spec_from_file_location('powerglove_vision.bench_'+lane,files[lane]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 class Recognizer:
  """Provide deterministic observations after a simulated inference delay."""
  cv2=cv2;mirror=False;backend='synthetic';backend_label='synthetic 60ms'
  def process(self,frame,timestamp=None):
   """Return a synthetic tracked palm encoded by the supplied frame."""
   time.sleep(.060)
   x=int(frame[0,0,0])-16
   pose=HandObservation(timestamp,True,.95,.5+x/640,.5,.068)
   points=[(.43+x/640,.4),(.57+x/640,.4),(.57+x/640,.59),(.5+x/640,.60),(.43+x/640,.59)]
   return TrackingResult(pose,frame,palm_points=points)
  def close(self):
   """Release no resources; the synthetic recognizer owns none."""
   pass
 tracker=m.MotionTracker(Recognizer());times=[];flow_times=[];valid_times=[];ages=[];failures={};valid=total=0
 original_advance=tracker.flow.advance
 # Count time inside the actual optical-flow routine, including replay calls.
 def measured(gray):
  """Time one call to the selected implementation's optical-flow routine."""
  start=time.monotonic();result=original_advance(gray);flow_times.append((time.monotonic()-start)*1000);return result
 tracker.flow.advance=measured
 start=time.monotonic();deadline=start+seconds;next_frame=start
 try:
  while time.monotonic()<deadline:
   time.sleep(max(0,next_frame-time.monotonic()));at=time.monotonic();index=round(16+12*math.sin((at-start)*2));frame=frames[index].copy();frame[0,0]=index
   begin=time.monotonic();result=tracker.process(frame,at,fast=True);elapsed=(time.monotonic()-begin)*1000
   total+=1;times.append(elapsed)
   if result.observation.detected:valid+=1;valid_times.append(elapsed)
   age=result.diagnostics.get('gesture_age_ms')
   if age is not None:ages.append(age)
   reason=result.diagnostics.get('motion_failure')
   if reason:failures[reason]=failures.get(reason,0)+1
   next_frame=max(next_frame+1/60,time.monotonic())
 finally:tracker.close()
 return {'lane':lane,'seconds':seconds,'frames':total,'valid_frames':valid,'process_ms':summary(times),'valid_process_ms':summary(valid_times),'flow_call_ms':summary(flow_times),'gesture_age_ms':summary(ages),'failures':failures}
result={'source_sha256':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in files.items()},'opencv':cv2.__version__,'opencv_threads':cv2.getNumThreads(),'limitations':['Synthetic textured palm; simulated 60ms recognition sleeps, not real MediaPipe CPU work.','No camera, transport or display; not a physical latency or hand-recognition result.'],'lanes':[run(lane) for lane in ('before','after','before','after')]}
print(json.dumps(result,indent=2))
with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
