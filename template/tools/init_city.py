"""Step 1 — start a city from its name only.

usage: python3 -I init_city.py <城市名> <examplesDir>

  * geocodes the city (OpenStreetMap Nominatim) → centre, admin bounding box, English name → slug
  * writes <examplesDir>/<slug>/city.json  (machine fields; the model never edits it)
  * writes <examplesDir>/<slug>/spots.json (skeleton with TODOs, only if it does not exist yet)
  * downloads research material into <slug>/research/:
      wp_<城市>市.txt / bk_<城市>.txt   city articles (zh.wikipedia + baike.com)
      candidates.md                     scenic-spot names found in those texts (5A/4A, 风景名胜区, 古镇 …)
      INDEX.md                          file → source URL
  * prints the slug directory
"""
import json, os, re, subprocess, sys, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
UA = 'CityScenicBot/1.0 (travel research)'
name = sys.argv[1].strip()
root = os.path.abspath(sys.argv[2])
short = re.sub(r'(市|县|区)$', '', name)


def get(url):
    for _ in range(5):
        try:
            return json.loads(subprocess.check_output(['curl', '-s', '-m', '60', '-A', UA, url]))
        except Exception:
            pass
    raise RuntimeError(url)


q = urllib.parse.quote(short + '市')
res = get(f'https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=5&namedetails=1&accept-language=zh')
res = [r for r in res if r.get('class') in ('boundary', 'place')] or res
if not res:
    res = get(f'https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(short)}&format=json&limit=5&namedetails=1&accept-language=zh')
g = res[0]
en = (g.get('namedetails') or {}).get('name:en') or (g.get('namedetails') or {}).get('name:zh-Latn-pinyin') or short
slug = re.sub(r'[^a-z]', '', re.sub(r'\b(city|prefecture|municipality)\b', '', en.lower())) or 'city'
bb = [float(x) for x in g['boundingbox']]          # lat0, lat1, lon0, lon1
out = os.path.join(root, slug)
R = os.path.join(out, 'research')
os.makedirs(R, exist_ok=True)

cp = os.path.join(out, 'city.json')
city = json.load(open(cp, encoding='utf-8')) if os.path.exists(cp) else {}
city.update(slug=slug, name=short, en=en, center={'lon': round(float(g['lon']), 4), 'lat': round(float(g['lat']), 4)},
            adminBBox=[bb[2], bb[0], bb[3], bb[1]])
json.dump(city, open(cp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

sp = os.path.join(out, 'spots.json')
if not os.path.exists(sp):
    json.dump({
        'city': short,
        'subtitle': 'TODO 片头副标题，≤16 字，用“ · ”分隔，如：太湖 · 名山 · 竹乡 · 古镇',
        'subtitleFacts': [{'text': 'TODO 副标题依据', 'quotes': [{'file': 'TODO.txt', 'quote': 'TODO'}]}],
        'question': f'TODO 结尾唯一的问题，如：{short}这8个地方，\\n你最想先去哪一个？',
        'spots': [],
    }, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- research material
W = os.path.join(HERE, 'wiki.py')
subprocess.call([sys.executable, '-I', '-X', 'utf8', W, 'wp', R, short + '市'])
subprocess.call([sys.executable, '-I', '-X', 'utf8', W, 'bk', R, short, short + '市'])
for a, b in (('wp_' + short + '市.txt', 'wp_city.txt'),):
    pa = os.path.join(R, a)
    if os.path.exists(pa) and not os.path.exists(os.path.join(R, b)):
        os.symlink(a, os.path.join(R, b))

# candidates.md: sentences of the city texts that name scenic spots — the model picks from these
KEY = re.compile(r'(5A|4A|AAAAA|AAAA|风景名胜区|旅游区|景区|古镇|古村|古街|历史文化街区|湿地|国家公园|森林公园|塔|寺|遗址|湖|山|故居|博物馆|度假区)')
rows, seen = [], set()
for fn in sorted(os.listdir(R)):
    if not fn.endswith('.txt') or fn in ('wp_city.txt',):
        continue
    body = open(os.path.join(R, fn), errors='ignore', encoding='utf-8').read().split('\n', 2)[-1]
    for sent in re.split(r'(?<=[。！；\n])', body):
        sent = sent.strip()
        if 10 <= len(sent) <= 200 and KEY.search(sent) and ('旅游' in sent or '景' in sent or '名胜' in sent) and sent not in seen:
            seen.add(sent); rows.append((fn, sent))
with open(os.path.join(R, 'candidates.md'), 'w', encoding='utf-8') as f:
    f.write(f'# {short} · 提到景点的句子（摘自 research/ 下的城市条目）\n\n')
    f.write('从这里挑 6–8 个景点；每个景点再用 wiki.py 下载它自己的维基百科条目 + 快懂百科词条，事实从那两个文件里原样摘引文。\n\n')
    for k, (fn, s) in enumerate(rows[:200], 1):
        f.write(f'{k}. [{fn}] {s}\n')

subprocess.call([sys.executable, '-I', W, 'index', R])
print(out)
