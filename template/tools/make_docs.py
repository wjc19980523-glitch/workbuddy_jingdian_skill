"""Write sources.md, image-sources.md and REVIEW.md for a city (from spots.json, research/, assets/).

usage: python3 -I make_docs.py <cityDir>
"""
import json, os, re, sys

CITY = os.path.abspath(sys.argv[1])
R = os.path.join(CITY, 'research')
d = json.load(open(os.path.join(CITY, 'spots.json')))
ver = json.load(open(os.path.join(R, 'verify.json')))
meta = json.load(open(os.path.join(CITY, 'assets', 'img', 'meta.json')))
rej = json.load(open(os.path.join(CITY, 'assets', 'img', 'rejected.json'))) if os.path.exists(os.path.join(CITY, 'assets', 'img', 'rejected.json')) else []
city = json.load(open(os.path.join(CITY, 'city.json')))
tl = json.load(open(os.path.join(CITY, 'build', 'events.json'))) if os.path.exists(os.path.join(CITY, 'build', 'events.json')) else None


def url_of(fn):
    p = os.path.join(R, fn)
    if not os.path.exists(p):
        return ''
    for line in open(p, errors='ignore').read(600).splitlines():
        if line.startswith('# http'):
            return line[2:].strip()
    return ''


review = []
S = [f"# {d['city']} · 景点视频 出处清单", '',
     '每条上屏文字 → 引文（从下载的网页原文逐字摘录，脚本已逐字比对）→ 网址。“已核”= 两个不同网站的原文都支持；“⚠ 待核对”= 只有一个网站。', '',
     f"## 片头副标题：{d['subtitle']}", '']
for f in ver.get('subtitle') or []:
    if not f:
        continue
    S.append(f"- **{f['text']}** — {f['status']}")
    for q in f['quotes']:
        S.append(f"  - {q['file']}：“{q['quote']}” <{url_of(q['file'])}>")
    if f['status'] != '已核':
        review.append(f"片头副标题依据：{f['text']}（{f['status']}）")
S.append('')
for i, s in enumerate(d['spots'], 1):
    S += [f"## {i:02d} {s['name']}（{s['where']}）", '']
    S.append(f"- 坐标：{s.get('lon')}, {s.get('lat')}（{s.get('geoSource', '')}）— 只用于地图上的定位点")
    for f in ver.get(s['id']) or []:
        if not f:
            continue
        S.append(f"- **{f['text']}** — {f['status']}")
        for q in f['quotes']:
            S.append(f"  - {q['file']}：“{q['quote']}” <{url_of(q['file'])}>")
        if f['status'] != '已核':
            review.append(f"{s['name']}：{f['text']}（{f['status']}）")
    S.append('')
S += [f"## 结尾提问", '', d['question'].replace('\\n', '').replace('\n', ''), '']
open(os.path.join(CITY, 'sources.md'), 'w').write('\n'.join(S))

I = [f"# {d['city']} · 景点视频 图片与素材授权清单", '',
     '全部实景照片来自 Wikimedia Commons，授权只限公有领域 / CC0 / CC BY / CC BY-SA（脚本按 Commons 文件页元数据过滤，并排除 Commons 分类或说明里标为 AI 生成的文件）。',
     'CC BY / CC BY-SA 要求署名：每张图出现时，画面底部有“图注｜摄影 作者 · 协议 · Wikimedia Commons”。', '',
     '| 本地文件 | 景点 | 图注（画面） | Commons 文件 | 作者 | 授权 | 拍摄/日期 | AI |', '|---|---|---|---|---|---|---|---|']
names = {s['id']: s['name'] for s in d['spots']}
caps = {im['id']: im.get('caption', '') for s in d['spots'] for im in s.get('images', []) if 'id' in im}
ai_any = False
for iid in sorted(meta):
    m = meta[iid]
    if iid not in caps:
        continue
    ai = '是（画面标注“AI生成画面”）' if m.get('ai') else '否'
    ai_any |= bool(m.get('ai'))
    artist = re.sub(r'\s+', ' ', m.get('artist') or '').strip()[:60]
    I.append(f"| assets/img/{iid}.jpg | {names.get(m.get('node'), '')} | {caps[iid]} | [{m.get('title')}]({m.get('page')}) | {artist} | {m.get('license')} | {(m.get('date') or '')[:20]} | {ai} |")
    if m.get('user_supplied'):
        review.append(f"{iid}：用户自备图片，授权“{m.get('license')}”需人工确认")
I += ['', '## 地图底图', '']
for nm in ('local', 'wide'):
    p = os.path.join(CITY, 'assets', 'map', nm + '.json')
    if os.path.exists(p):
        m = json.load(open(p))
        I.append(f"- assets/map/{nm}.jpg：NASA GIBS WMS，图层 {m.get('layer')}，日期 {', '.join(m.get('dates', []))}。"
                 '<https://gibs.earthdata.nasa.gov/> NASA EOSDIS 影像无使用限制，要求注明出处（HLS 含修改后的 Copernicus Sentinel-2 数据）；画面上已注明。')
I += ['', '## 配乐与音效', '',
      '全部由 `template/tools/music.py` 程序合成（Karplus–Strong 拨弦、合成垫音、合成鼓与音效），没有使用任何第三方音乐或采样，也不是 AI 生成音乐。', '',
      '## AI 内容', '',
      ('片中含 AI 生成画面，均已在出现时于画面右上角标注“AI生成画面”，片尾字幕也有说明。' if ai_any else
       '**全片没有 AI 生成画面。** 所有实景都是 Commons 上的真实照片，地图是卫星影像；转场、运镜、文字动画是程序对真实图片做的变换。'
       '片尾字幕注明“本片由 AI 辅助剪辑；画面均为实拍授权照片与卫星影像，无 AI 生成画面”。'), '']
if rej:
    I += ['## 被拒收的图', ''] + [f"- {r.get('file')}（{r.get('node')}）：{r.get('why')}" for r in rej] + ['']
open(os.path.join(CITY, 'image-sources.md'), 'w').write('\n'.join(I))

V = [f"# {d['city']} · 待人工核对", '']
V += [f"- {x}" for x in review if x] or ['- （无：所有上屏事实都有两个网站的原文支持）']
V += ['', '另请过目：地名小字（where）与图注（caption）由执行模型根据资料/候选说明填写，脚本只查长度和禁用词，未逐字核对。', '']
notes = os.path.join(CITY, 'REVIEW.notes.md')
if os.path.exists(notes):
    V += ['## 人工审校备注', '', open(notes).read()]
open(os.path.join(CITY, 'REVIEW.md'), 'w').write('\n'.join(V))
print('docs ok: sources.md image-sources.md REVIEW.md', len([x for x in review if x]), 'to review')
