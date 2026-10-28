"""Quick look without rendering the film: screenshots at chosen times → one contact sheet.

usage: python3 -I stills.py <cityDir> <out.jpg> [t1,t2,...]   (default: one still per second)
"""
import asyncio, io, json, os, sys
from PIL import Image, ImageDraw

CITY = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
B = os.path.join(CITY, 'build')
dur = json.load(open(os.path.join(B, 'events.json')))['dur']
ts = [float(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else [k + 0.5 for k in range(int(dur))]


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        br = await pw.chromium.launch(executable_path=os.environ.get('CHROME', '/usr/bin/google-chrome'),
                                      args=['--disable-gpu', '--allow-file-access-from-files', '--hide-scrollbars'])
        pg = await br.new_page(viewport={'width': 1080, 'height': 1920}, device_scale_factor=0.25)
        logs = []
        pg.on('console', lambda m: logs.append(m.text)); pg.on('pageerror', lambda e: logs.append('PAGEERROR ' + str(e)))
        await pg.goto('file://' + os.path.join(B, 'index.html'))
        await pg.evaluate('window.__ready')
        ims = []
        for t in ts:
            await pg.evaluate(f'window.__seek({t})')
            ims.append((t, Image.open(io.BytesIO(await pg.screenshot(type='jpeg', quality=85))).convert('RGB')))
        await br.close()
        for l in logs:
            print(l)
    w, h = ims[0][1].size
    cols = min(8, len(ims)); rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * w, rows * (h + 22)), (0, 0, 0)); d = ImageDraw.Draw(sheet)
    for k, (t, im) in enumerate(ims):
        x, y = (k % cols) * w, (k // cols) * (h + 22)
        sheet.paste(im, (x, y + 22)); d.text((x + 4, y + 4), f'{t:.2f}s', fill=(255, 220, 0))
    sheet.save(OUT, quality=88)
    print(OUT, len(ims))


asyncio.run(main())
