# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
"""Exercise Setup slider saves, live states, retries and player changes in isolated browsers."""
import asyncio
from urllib.parse import urlsplit
from playwright.async_api import async_playwright, expect
from powerglove_vision.joystick_web import JOYSTICK_CONTENT, JOYSTICK_SCRIPT
from powerglove_vision.web_common import _page

async def main():
    async with async_playwright() as pw:
        for engine in ('chromium', 'webkit'):
            browser = await getattr(pw, engine).launch(**({'channel':'chrome'} if engine=='chromium' else {}))
            page = await browser.new_page(viewport={'width':390,'height':844})
            state=dict(active='default',generation=1,players=[dict(id='default',name='Iain')],joystick={d:dict(on=.28,off=.14) for d in ('left','right','up','down')})
            calls=[]; errors=[]; flags={'fail':False, 'tracking':True}
            page.on('pageerror',lambda e:errors.append(str(e)))
            async def route(r):
                path=urlsplit(r.request.url).path
                if path=='/setup':return await r.fulfill(body=_page('Joystick test',JOYSTICK_CONTENT,JOYSTICK_SCRIPT),content_type='text/html')
                if path=='/status':return await r.fulfill(json=dict(vision_state='active',detected=flags['tracking'],calibrated=True,dpad=dict(left=True)))
                if path=='/api/players':
                    data=r.request.post_data_json
                    if data['action']=='joystick_deadzone':
                        calls.append(data)
                        if flags['fail']:return await r.fulfill(status=400,json={'error':'Save failed; retry.'})
                        state['generation']+=1
                        state['joystick']={d:dict(on=data['value'],off=data['value']/2) for d in state['joystick']}
                    return await r.fulfill(json=state)
                return await r.fulfill(status=404)
            await page.route('**/*',route);await page.goto('http://joystick.test/setup')
            await expect(page.locator('#joystick-size')).to_be_enabled()
            await expect(page.locator('[data-direction=left]')).to_have_text('Left: pressed')
            await page.locator('#joystick-size').focus();await page.keyboard.press('Home')
            for _ in range(36):await page.keyboard.press('ArrowRight')
            await page.wait_for_timeout(1200)
            await expect(page.locator('#joystick-size')).to_have_value('0.5')
            await page.locator('#joystick-save').click(delay=300)
            await expect(page.locator('#joystick-notice')).to_contain_text('Dead zone saved')
            assert calls[-1]['value']==.5 and calls[-1]['generation']==1
            await page.locator('#joystick-default').click();flags['fail']=True
            await page.locator('#joystick-save').click();await expect(page.locator('#joystick-notice')).to_contain_text('Save failed')
            await expect(page.locator('#joystick-size')).to_have_value('0.28')
            flags['fail']=False
            await page.locator('#joystick-save').click();await expect(page.locator('#joystick-notice')).to_contain_text('Dead zone saved')
            await page.locator('#joystick-size').focus();await page.keyboard.press('End')
            state['active']='second';state['generation']+=1;state['players'].append(dict(id='second',name='Scott'))
            await expect(page.locator('#joystick-player')).to_have_text('Player: Scott')
            await expect(page.locator('#joystick-size')).to_have_value('0.28')
            flags['tracking']=False
            await expect(page.locator('[data-direction=left]')).to_have_text('Left: off')
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            await page.locator('#joystick-settings').screenshot(path='/tmp/joystick-'+engine+'.png')
            assert not errors,errors
            await browser.close()
            print(engine+' joystick checks passed')
asyncio.run(main())
