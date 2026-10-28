"""Step 6 — spots.json + downloaded images + map → build/timeline.js (the film's whole script, in seconds).

usage: python3 -I build_timeline.py <cityDir>

Nothing here is for the model to tune. It decides automatically:
  * a camera recipe per spot from the photos it has (wide panorama → pano, ≥3 tall photos → strips, a tall photo → tilt,
    ≥3 photos → carousel / bands, 2 photos → ring, last spot → bloom …), every recipe used at most once while possible;
    a spot may force one with "move": "<recipe>" (ring tilt bands pano carousel strips bloom truck)
  * a different transition into every spot (whip, zoom, vertical whip, roll, iris, diagonal whip, flash)
  * one map "hop" at the longest jump between consecutive spots (≥5 spots)
  * all times on a 120 BPM grid (bars of 2 s) so cuts land on the music written by music.py
Writes build/timeline.js, build/events.json and copies template/src/{index.html,app.js} into build/.
"""
import itertools, json, math, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CITY = os.path.abspath(sys.argv[1])
B = os.path.join(CITY, 'build'); os.makedirs(B, exist_ok=True)
data = json.load(open(os.path.join(CITY, 'spots.json'), encoding='utf-8'))
city = json.load(open(os.path.join(CITY, 'city.json'), encoding='utf-8'))
mp = os.path.join(CITY, 'assets', 'map')
FPS = int(os.environ.get('CS_FPS', '30'))
BPM = 120

DUR = dict(ring=6, tilt=6, bands=4, pano=6, carousel=6, strips=4, bloom=6, truck=4, card=4)
TRANS = ['whip', 'zoom', 'whipV', 'roll', 'iris', 'whipD', 'flash']


def score(rec, ims, last):
    n = len(ims)
    ar = [im['w'] / im['h'] for im in ims]
    port = sum(1 for a in ar if a < 0.87)
    land = sum(1 for a in ar if a > 1.15)
    if n == 0:
        return 10 if rec == 'card' else None
    if rec == 'card':
        return None
    s = {
        'pano': 10 if max(ar) >= 2.2 else (3 if land and n >= 2 else None),
        'strips': 9 if port >= 3 else (4 if n >= 3 else None),
        'tilt': (8 if ar[0] < 0.87 else 4 if port else None),
        'carousel': 6 if n >= 3 else None,
        'bands': 5 if n >= 3 else None,
        'ring': 5 if n >= 2 else None,
        'bloom': 4 + (5 if last else 0),
        'truck': 1,
    }[rec]
    return s


def assign(spots):
    recs = list(DUR)
    forced = {i: s['move'] for i, s in enumerate(spots) if s.get('move') in DUR}
    free = [i for i in range(len(spots)) if i not in forced]
    pool = [r for r in recs if r not in forced.values()]
    best, bestv = None, -1e9
    if len(free) <= len(pool):
        for perm in itertools.permutations(pool, len(free)):
            v = 0
            for i, r in zip(free, perm):
                sc = score(r, spots[i]['images'], i == len(spots) - 1)
                if sc is None:
                    v = -1e9; break
                v += sc
            if v > bestv:
                bestv, best = v, perm
    out = dict(forced)
    if best and bestv > -1e9:
        out.update(zip(free, best))
    for i in range(len(spots)):   # anything left (more spots than recipes): best fitting, may repeat
        if i not in out:
            cands = [(score(r, spots[i]['images'], i == len(spots) - 1) or -1, r) for r in recs]
            out[i] = max(cands)[1]
    return [out[i] for i in range(len(spots))]


meta = json.load(open(os.path.join(CITY, 'assets', 'img', 'meta.json'), encoding='utf-8')) if os.path.exists(os.path.join(CITY, 'assets', 'img', 'meta.json')) else {}
spots = []
for k, s in enumerate(data['spots']):
    ims = []
    for im in s.get('images', []):
        f = os.path.join(CITY, 'assets', 'img', im['id'] + '.jpg')
        if not os.path.exists(f):
            continue
        m = meta.get(im['id'], {})
        ims.append(dict(src='../assets/img/' + im['id'] + '.jpg', w=im['w'], h=im['h'], caption=im.get('caption', ''),
                        credit=im.get('credit', ''), ai=bool(m.get('ai') or im.get('ai'))))
    files = sorted({q['file'] for f in s['facts'] for q in f['quotes']})
    names = []
    for fn in files:
        nm = '维基百科' if fn.startswith('wp_') else '快懂百科' if fn.startswith('bk_') else '维基文库' if fn.startswith('ws_') else '网页资料'
        if nm not in names:
            names.append(nm)
    spots.append(dict(id=s['id'], index=k + 1, name=s['name'], where=s['where'], lon=s['lon'], lat=s['lat'],
                      facts=[f['text'] for f in s['facts']], src=' · '.join(names), images=ims, move=s.get('move')))

recipes = assign(spots)
# the photo that opens a tilt should be the tallest one
for s, r in zip(spots, recipes):
    if r == 'tilt' and s['images']:
        k = min(range(len(s['images'])), key=lambda i: s['images'][i]['w'] / s['images'][i]['h'])
        s['images'].insert(0, s['images'].pop(k))

# where to put the map hop: the longest jump between consecutive spots (not into the first two)
hop_before = None
if len(spots) >= 5:
    d = [(math.hypot(spots[i]['lon'] - spots[i - 1]['lon'], spots[i]['lat'] - spots[i - 1]['lat']), i) for i in range(2, len(spots))]
    hop_before = max(d)[1]

shots, t = [], 0.0
n = len(spots)
hook_cut = 0.25
intro = 8.0 if n <= 8 else 8.0 + math.ceil((n - 8) * hook_cut / 2) * 2
shots.append(dict(kind='intro', t0=0.0, t1=intro, inT='cut')); t = intro
ti = 0
for i, s in enumerate(spots):
    inT = 'dive'
    if i == hop_before:
        shots.append(dict(kind='hop', t0=t, t1=t + 2.0, inT='pull', **{'from': i - 1, 'to': i})); t += 2.0
    elif i > 0:
        inT = TRANS[ti % len(TRANS)]; ti += 1
    D = DUR[recipes[i]]
    shots.append(dict(kind='spot', spot=i, recipe=recipes[i], layout=i, t0=t, t1=t + D, inT=inT)); t += D
shots.append(dict(kind='finale', t0=t, t1=t + 8.0, inT='pull')); t += 8.0
dur = t

# events for music.py and the flashes / light leaks in app.js
ev = []
nm = n * hook_cut
for k in range(n):
    ev.append(dict(t=round(k * hook_cut, 3), kind='tick', a=0.6))
    ev.append(dict(t=round(k * hook_cut, 3), kind='flash', a=0.18))
ev.append(dict(t=nm, kind='impact', a=1.0)); ev.append(dict(t=nm, kind='flash', a=0.85)); ev.append(dict(t=nm, kind='leak', a=1))
ev.append(dict(t=round(intro - 1.0, 3), kind='riser', a=0.8, d=1.0))
for sh in shots[1:]:
    ty = sh['inT']
    ev.append(dict(t=sh['t0'], kind='hit', a=1.0, trans=ty))
    if ty in ('whip', 'whipV', 'whipD', 'roll', 'dive', 'pull', 'zoom'):
        ev.append(dict(t=round(sh['t0'] - 0.25, 3), kind='whoosh', a=0.9, trans=ty))
    if ty in ('zoom', 'flash'):
        ev.append(dict(t=sh['t0'], kind='flash', a=0.55))
    if ty in ('roll', 'iris', 'dive'):
        ev.append(dict(t=sh['t0'], kind='leak', a=1))
    if sh['kind'] == 'spot':   # in-shot moves that deserve a hit (half-way reveals)
        D = sh['t1'] - sh['t0']
        frac = dict(ring=0.48, tilt=0.55, bands=0.5, pano=0.68, carousel=0.72, strips=0.5, bloom=0.6).get(sh['recipe'])
        if frac:
            ev.append(dict(t=round(sh['t0'] + D * frac, 3), kind='accent', a=0.7))
fin = shots[-1]
ev.append(dict(t=round(fin['t0'] + 3.2 + 0.9, 3), kind='chime', a=0.8))
ev.sort(key=lambda e: e['t'])

credits = ['资料：' + '、'.join(sorted({x for s in spots for x in s['src'].split(' · ')}, key=['维基百科', '快懂百科', '维基文库', '网页资料'].index)),
           '图片：Wikimedia Commons（作者与授权见各画面署名）', city.get('mapCredit', '卫星影像：NASA GIBS')]
if any(im['ai'] for s in spots for im in s['images']):
    credits.append('本片含 AI 生成画面（已在画面中标注“AI生成画面”）')
else:
    credits.append('本片由 AI 辅助剪辑；画面均为实拍授权照片与卫星影像，无 AI 生成画面')

maps = {}
for nmp in ('local', 'wide'):
    f = os.path.join(mp, nmp + '.json')
    if os.path.exists(f):
        m = json.load(open(f, encoding='utf-8')); m['src'] = '../assets/map/' + nmp + '.jpg'; maps[nmp] = m
city_name = data['city']
TLd = dict(W=1080, H=1920, fps=FPS, bpm=BPM, dur=dur, city=city_name, hook='飞越' + city_name, hookCut=hook_cut,
           subtitle=data['subtitle'], question=data['question'].replace('\\n', '\n'), mapCredit=city.get('mapCredit', '卫星影像：NASA GIBS'),
           endCredits=credits, map=maps, spots=spots, shots=shots, events=ev)
txt = ''.join([TLd['hook'], city_name, TLd['subtitle'], TLd['question'], TLd['mapCredit'], '下一站', '资料：', '｜', '/0123456789', ''.join(credits)]
              + [s['name'] + s['where'] + ''.join(s['facts']) + s['src'] + ''.join(im['caption'] + im['credit'] for im in s['images']) for s in spots])
TLd['allText'] = ''.join(sorted(set(txt)))
open(os.path.join(B, 'timeline.js'), 'w', encoding='utf-8').write('window.TL = ' + json.dumps(TLd, ensure_ascii=False, indent=1) + ';\n')
json.dump(dict(dur=dur, bpm=BPM, events=ev, shots=shots), open(os.path.join(B, 'events.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for f in ('index.html', 'app.js'):
    shutil.copy(os.path.join(HERE, '..', 'src', f), os.path.join(B, f))
print(f'timeline {dur:.1f}s · {len(shots)} shots · ' + ' '.join(f"{s['name']}:{r}" for s, r in zip(spots, recipes)) + (f' · hop before {spots[hop_before]["name"]}' if hop_before else ''))
