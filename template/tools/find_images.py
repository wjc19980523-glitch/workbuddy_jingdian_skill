"""Step 3 — list licence-checked Wikimedia Commons photos for every spot; the model only picks codes.

usage: python3 -I find_images.py <cityDir>

For every spot with "imageQuery": "词1 | word 2 | ..." (Chinese and English keywords, separated by |):
  * searches Commons (file namespace), keeps only photos (jpg/png/tif) whose short side ≥ 1200 px,
    licence = public domain / CC0 / CC BY / CC BY-SA, not categorised/described as AI-generated
  * writes research/images.md (readable list) and research/image_candidates.json
  * writes research/images_contact/<spot id>.jpg — numbered thumbnails for a human to glance at
Each candidate has a code like  s03-2 . To use it the spot gets
    "images": [{"pick": "s03-2", "caption": "图注（据候选说明/文件名写，不要编）"}]
fetch_images.py resolves the code to the Commons file; codes not in the list are rejected.
"""
import io, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import commons  # noqa: E402
from fetch_images import licence_ok, AI  # noqa: E402

CITY = os.path.abspath(sys.argv[1])
data = json.load(open(os.path.join(CITY, 'spots.json')))
cp = os.path.join(CITY, 'research', 'image_candidates.json')
cand = json.load(open(cp)) if os.path.exists(cp) else {}
changed = set()
OKMIME = ('image/jpeg', 'image/png', 'image/tiff')
SKIP = re.compile(r'(map|地图|简介|introduction|sign|标志|指示|bus|logo|plan|diagram|ticket|门票|menu|\.pdf|\.djvu)', re.I)

md = ['# 图片候选（Wikimedia Commons，已按授权过滤：公有领域 / CC0 / CC BY / CC BY-SA；已排除 AI 生成图）', '',
      '用法：在 spots.json 对应景点写 "images": [{"pick": "编号", "caption": "图注"}]，选 2–3 张（至少 1 张）。',
      '只能用下面列出的编号。选“是这个景点本身”的风景/建筑照片：说明或文件名里有景点名的优先；横图（宽>高）和竖图都要有更好。',
      '不要选：地图、简介牌、路牌、室内局部、和景点无关的。图注只写说明/文件名里有的内容（地点、物名、拍摄年份）。', '']
for n in data['spots']:
    q = (n.get('imageQuery') or '').strip()
    sid = n['id']
    if not q:
        md += [f"## {sid} {n.get('name', '')}  （没有 imageQuery，跳过）", '']
        continue
    if sid not in cand or cand[sid].get('query') != q:
        per, seen = [], set()
        for part in [p.strip() for p in q.split('|') if p.strip()]:
            try:
                res = commons.search(part, 30)
            except Exception:
                res = []
            got = []
            for x in res:
                if x['title'] in seen:
                    continue
                seen.add(x['title'])
                if x.get('mime') not in OKMIME or min(x.get('w') or 0, x.get('h') or 0) < 1200 or not licence_ok(x.get('license', '')):
                    continue
                if AI.search((x.get('desc') or '') + ' ' + x['title']) or SKIP.search(x['title']):
                    continue
                got.append(x)
            per.append(got)
        rows, series = [], {}
        for k in range(30):
            for got in per:
                if k < len(got):
                    stem = re.sub(r'[\d\s_\-,.()（）]+', '', got[k]['title'].rsplit('.', 1)[0])
                    if series.get(stem, 0) < 4:
                        series[stem] = series.get(stem, 0) + 1; rows.append(got[k])
        cand[sid] = {'query': q, 'items': []}; changed.add(sid)
        for k, x in enumerate(rows[:14], 1):
            cand[sid]['items'].append(dict(code=f'{sid}-{k}', title=x['title'], w=x['w'], h=x['h'], license=x['license'],
                                           artist=(x.get('artist') or '')[:60], date=(x.get('date') or '')[:30],
                                           desc=re.sub(r'\s+', ' ', x.get('desc') or '')[:220], page=x.get('page')))
    items = cand[sid]['items']
    md += [f"## {sid} {n.get('name', '')}  （搜索：{q}）", '']
    if not items:
        md += ['（没有授权合规的候选 → 换 imageQuery 关键词再运行；仍没有就写 "images": []，该景点改成文字卡）', '']
    for x in items:
        shape = '横图' if x['w'] > x['h'] * 1.1 else ('竖图' if x['h'] > x['w'] * 1.1 else '方图')
        md.append(f"- **{x['code']}**  {x['title']}  | {shape} {x['w']}x{x['h']} | {x['license']} | 作者 {x['artist'] or '—'} | {x['date'] or '—'}\n  说明：{x['desc'] or '—'}")
    md.append('')
if changed or not os.path.exists(cp):
    json.dump(cand, open(cp, 'w'), ensure_ascii=False, indent=1)
open(os.path.join(CITY, 'research', 'images.md'), 'w').write('\n'.join(md))

# contact sheets for a human (the model does not need them)
try:
    from PIL import Image, ImageDraw, ImageFont
    out = os.path.join(CITY, 'research', 'images_contact'); os.makedirs(out, exist_ok=True)
    try:
        font = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', 28)
    except Exception:
        font = ImageFont.load_default()
    for sid, v in cand.items():
        f = os.path.join(out, sid + '.jpg')
        if os.path.exists(f) and sid not in changed:
            continue
        thumbs = []
        for x in v['items']:
            try:
                t = commons.info([x['title']], 320)[0].get('thumb')
                raw = subprocess.check_output(['curl', '-s', '-f', '-m', '60', '-A', commons.UA, t])
                im = Image.open(io.BytesIO(raw)).convert('RGB'); im.thumbnail((320, 320))
                thumbs.append((x['code'], im))
            except Exception:
                pass
        if not thumbs:
            continue
        cols = 4; rows_ = (len(thumbs) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * 330, rows_ * 360), (20, 20, 20)); d = ImageDraw.Draw(sheet)
        for k, (code, im) in enumerate(thumbs):
            x0, y0 = (k % cols) * 330 + 5, (k // cols) * 360 + 5
            sheet.paste(im, (x0, y0)); d.text((x0, y0 + 322), code, fill=(255, 220, 120), font=font)
        sheet.save(f, quality=85)
except Exception as e:
    print('contact sheets skipped:', e)
print('candidates:', {k: len(v['items']) for k, v in cand.items()})
