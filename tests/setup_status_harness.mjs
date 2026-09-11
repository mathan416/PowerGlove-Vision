/*
 * Project: VirtualGlove
 * File: tests/setup_status_harness.mjs
 * Purpose: Exercise Setup's rendered Controller-output status without a browser.
 * Author: Iain Bennett
 * Copyright (c) 2026 Iain Bennett
 * SPDX-License-Identifier: MIT
 * Change log:
 *   2026-09-09 - Added armed-idle and active-delivery status coverage.
 * Full history: docs/CHANGELOG.md and Git history.
 */

import vm from 'node:vm';

let html='';
for await(const chunk of process.stdin)html+=chunk;
const start=html.indexOf('function controllerOutputStatus(w)');
const end=html.indexOf('async function refreshStatus()',start);
if(start<0||end<0)throw new Error('Controller-output helper was not rendered');
const context={};
vm.runInNewContext(html.slice(start,end),context);

function expectStatus(input,state,label){
  const actual=context.controllerOutputStatus(input);
  if(actual.state!==state||actual.label!==label){
    throw new Error(`Expected ${state}/${label}; received ${actual.state}/${actual.label}`);
  }
}

expectStatus({controller_enabled:true,controller_context_active:false,
  receiver_available:false,profile:'off',vision_profile:'off'},
  'good','Armed — waiting for game');
expectStatus({controller_enabled:true,controller_context_active:true,
  receiver_available:false,profile:'super_glove_ball',vision_profile:'super_glove_ball'},
  'bad','Receiver unavailable');
expectStatus({controller_enabled:true,controller_context_active:true,
  receiver_available:true,profile:'super_glove_ball',vision_profile:'super_glove_ball'},
  'good','Delivering');
expectStatus({controller_enabled:true,controller_context_active:true,
  receiver_available:false,practice_mode:true,profile:'off',vision_profile:'general'},
  'good','Paused for practice');
expectStatus({controller_enabled:false,controller_context_active:false,
  receiver_available:false,profile:'off',vision_profile:'off'},
  'unknown','Stopped');
process.stdout.write('Setup status harness passed\n');
