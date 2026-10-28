"""Step 8 — render build/index.html frame by frame (headless Chrome), with real motion blur.

usage: python3 -I render.py <cityDir> [--scale 1] [--fps 30] [--workers N] [--shutter 180] [--from F --to F]

* Frames go to <cityDir>/build/frames/f00000.jpg … ; existing frames are kept (resume after a crash or timeout).
  Changing --scale / --fps empties the folder (stamp file frames/.params).
* Motion blur: for every frame the page reports how far anything moves on screen across the open shutter
  (window.__motion); fast frames are captured several times inside the shutter and averaged in linear light.
  A frame whose shutter straddles a hard cut is captured once.
* Chrome: $CHROME, else common OS paths, else Playwright bundled Chromium.
"""
import argparse, asyncio, io, json, math, os, sys, time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from PIL import Image


def resolve_chrome():
    """Prefer $CHROME; else common OS paths; else None → Playwright bundled Chromium."""
    env = os.environ.get('CHROME')
    if env and os.path.isfile(env):
        return env
    candidates = [
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%PROGRAMFILES%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe'),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


ap = argparse.ArgumentParser()
ap.add_argument('city'); ap.add_argument('--scale', type=float, default=float(os.environ.get('CS_SCALE', 1)))
ap.add_argument('--fps', type=int, default=int(os.environ.get('CS_FPS', 30)))
ap.add_argument('--workers', type=int, default=int(os.environ.get('CS_WORKERS', max(1, min(6, (os.cpu_count() or 4) - 2)))))
ap.add_argument('--shutter', type=float, default=180); ap.add_argument('--gap', type=float, default=7)
ap.add_argument('--maxs', type=int, default=int(os.environ.get('CS_MAXSAMPLES', 12)))
ap.add_argument('--from', dest='f0', type=int, default=0); ap.add_argument('--to', dest='f1', type=int, default=-1)
A = ap.parse_args()
CITY = os.path.abspath(A.city)
B = os.path.join(CITY, 'build'); FR = os.path.join(B, 'frames'); os.makedirs(FR, exist_ok=True)
CHROME = resolve_chrome()
_u = np.arange(256) / 255.0
S2L = np.where(_u <= 0.04045, _u / 12.92, ((_u + 0.055) / 1.055) ** 2.4).astype(np.float32)


def l2s(x):
    x = np.clip(x, 0, 1)
    return (np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055) * 255 + 0.5).astype(np.uint8)


async def worker_main(wid, frames, fps, scale, shutter, gap, maxs):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        launch_kwargs = dict(args=['--disable-gpu', '--force-color-profile=srgb', '--hide-scrollbars',
                                   '--disable-web-security', '--allow-file-access-from-files'])
        if CHROME:
            launch_kwargs['executable_path'] = CHROME
        br = await pw.chromium.launch(**launch_kwargs)
        pg = await br.new_page(viewport={'width': 1080, 'height': 1920}, device_scale_factor=scale)
        await pg.goto('file://' + os.path.join(B, 'index.html'))
        await pg.evaluate('window.__ready')
        half = shutter / 360 / fps / 2
        done = 0; caps = 0
        for f in frames:
            out = os.path.join(FR, f'f{f:05d}.jpg')
            if os.path.exists(out):
                continue
            t = f / fps
            n = 1
            if shutter > 0:
                same = await pg.evaluate(f'window.__shotsAt({t - half}) === window.__shotsAt({t + half})')
                if same:
                    mv = await pg.evaluate(f'window.__motion({t - half}, {t + half})')
                    n = int(min(maxs, max(1, math.ceil(mv * scale / gap))))
            if n == 1:
                await pg.evaluate(f'window.__seek({t})')
                png = await pg.screenshot(type='jpeg', quality=93)
                open(out + '.tmp', 'wb').write(png); os.replace(out + '.tmp', out); caps += 1
            else:
                acc = None
                for k in range(n):
                    tk = t - half + (k + 0.5) * (2 * half / n)
                    await pg.evaluate(f'window.__seek({tk})')
                    im = np.asarray(Image.open(io.BytesIO(await pg.screenshot(type='jpeg', quality=96))).convert('RGB'))
                    lin = S2L[im]
                    acc = lin if acc is None else acc + lin
                    caps += 1
                Image.fromarray(l2s(acc / n)).save(out + '.tmp', 'JPEG', quality=93); os.replace(out + '.tmp', out)
            done += 1
            if done % 25 == 0:
                print(f'[w{wid}] {done} frames, {caps} captures, last f{f}', flush=True)
        await br.close()
    return done, caps


def run(args):
    return asyncio.run(worker_main(*args))


def main():
    tl = json.load(open(os.path.join(B, 'events.json'), encoding='utf-8'))
    total = int(round(tl['dur'] * A.fps))
    stamp = os.path.join(FR, '.params'); params = f'{A.scale} {A.fps}'
    if os.path.exists(stamp) and open(stamp, encoding='utf-8').read().strip() != params:
        for fn in os.listdir(FR):
            if fn.endswith('.jpg'):
                os.remove(os.path.join(FR, fn))
    open(stamp, 'w', encoding='utf-8').write(params)
    f1 = total if A.f1 < 0 else min(total, A.f1)
    todo = [f for f in range(A.f0, f1) if not os.path.exists(os.path.join(FR, f'f{f:05d}.jpg'))]
    print(f'render {total} frames total, {len(todo)} to do, {A.workers} workers, scale {A.scale}, {A.fps} fps', flush=True)
    t0 = time.time()
    if todo:
        chunks = [todo[k::A.workers] for k in range(A.workers)]
        with ProcessPoolExecutor(A.workers) as ex:
            res = list(ex.map(run, [(k, c, A.fps, A.scale, A.shutter, A.gap, A.maxs) for k, c in enumerate(chunks) if c]))
        print('captures', sum(r[1] for r in res), f'in {time.time() - t0:.0f}s', flush=True)
    missing = [f for f in range(total) if not os.path.exists(os.path.join(FR, f'f{f:05d}.jpg'))]
    print('RENDER', 'OK' if not missing else f'MISSING {len(missing)}', flush=True)
    sys.exit(0 if not missing else 1)


if __name__ == '__main__':
    main()
