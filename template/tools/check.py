"""Validate spots.json before anything is rendered. Prints ERROR lines (exit 1) or CHECK OK (exit 0).

usage: python3 -I check.py <cityDir> [--stage text|images]

text   : fields, lengths, forbidden words, the single closing question, every quote found verbatim in research/,
         every number on screen present in its quotes. Writes research/verify.json (per-fact status).
images : additionally every spot has 1–4 picked images whose codes exist in research/images.md, captions ≤ 30 字.
A fact backed by quotes from two different websites is 已核; one website → ⚠ 待核对 (allowed, listed in REVIEW.md).
"""
import json, os, re, sys, unicodedata

CITY = os.path.abspath(sys.argv[1])
STAGE = sys.argv[sys.argv.index('--stage') + 1] if '--stage' in sys.argv else 'text'
R = os.path.join(CITY, 'research')
errs, warns = [], []
try:
    d = json.load(open(os.path.join(CITY, 'spots.json'), encoding='utf-8'))
except Exception as e:
    print(f'ERROR spots.json 不是合法 JSON：{e}'); sys.exit(1)

FORBID = ['粉丝群', '粉丝', '关注', '点赞', '收藏', '转发', '下期', '账号', '主页', '私信', '加群', '进群', '抖音号', '视频号',
          '据本人称', '继续测', '继续拆', '小编', '博主', '链接', '扫码', 'TODO']
SITE = lambda fn: 'wp' if fn.startswith('wp_') else 'bk' if fn.startswith('bk_') else 'ws' if fn.startswith('ws_') else ('web:' + fn)


def norm(s):
    s = unicodedata.normalize('NFKC', s)
    return re.sub(r'[\s\W_]+', '', s)


_cache = {}


def text_of(fn):
    if fn not in _cache:
        p = os.path.join(R, fn)
        _cache[fn] = norm(open(p, errors='ignore', encoding='utf-8').read()) if os.path.exists(p) and os.path.isfile(p) else None
    return _cache[fn]


def width(s):   # 全角=1，半角=0.5
    return sum(1 if unicodedata.east_asian_width(c) in 'WF' else 0.55 for c in s)


def check_fact(where, f):
    if not isinstance(f, dict) or not f.get('text') or not isinstance(f.get('quotes'), list) or not f['quotes']:
        errs.append(f'{where}：facts 每项要有 text 和至少 1 条 quotes'); return None
    ok_sites, bad, alltxt = set(), [], ''
    for q in f['quotes']:
        fn, qt = q.get('file', ''), q.get('quote', '')
        t = text_of(os.path.basename(fn))
        if t is None:
            errs.append(f'{where}：引文文件 research/{fn} 不存在（先用 wiki.py 下载，file 只写文件名）'); continue
        nq = norm(qt)
        if len(nq) < 6:
            errs.append(f'{where}：引文太短（至少连续 6 个字）：{qt}'); continue
        if nq in t:
            ok_sites.add(SITE(fn)); alltxt += qt
        else:
            bad.append(f'{fn}：{qt[:30]}')
    for b in bad:
        errs.append(f'{where}：引文在文件里找不到（要从文件原样复制）→ {b}')
    nums = re.findall(r'\d+', unicodedata.normalize('NFKC', f['text']))
    for n_ in nums:
        if n_ not in re.findall(r'\d+', unicodedata.normalize('NFKC', alltxt)):
            errs.append(f'{where}：画面上的数字 {n_} 在引文里没有（改文字或补引文）')
    status = '已核' if len(ok_sites) >= 2 else ('⚠ 待核对（只有一个网站）' if ok_sites else '✗ 引文未通过')
    return dict(text=f['text'], status=status, sites=sorted(ok_sites), quotes=f['quotes'])


def bad_words(where, s):
    for w in FORBID:
        if w in s:
            errs.append(f'{where}：含禁用词“{w}”：{s}')


city = d.get('city', '')
sub = d.get('subtitle', '')
if not sub or 'TODO' in sub or width(sub) > 18:
    errs.append('subtitle：片头副标题要填，≤18 字（如“太湖 · 名山 · 竹乡 · 古镇”）')
bad_words('subtitle', sub)
verify = {'subtitle': [check_fact('subtitleFacts', f) for f in d.get('subtitleFacts', [])]}
if not d.get('subtitleFacts'):
    warns.append('subtitleFacts 为空：副标题没有出处（会进 REVIEW.md）')

q = d.get('question', '').replace('\\n', '\n')
bad_words('question', q)
if q.count('？') + q.count('?') != 1 or not q.rstrip().endswith(('？', '?')):
    errs.append('question：全句恰好一个问号，并且以问号结尾')
lines = q.split('\n')
if len(lines) > 2 or any(width(l) > 13 for l in lines):
    errs.append('question：最多 2 行（用 \\n 分行），每行 ≤13 字')
spots = d.get('spots', [])
if not 5 <= len(spots) <= 8:
    errs.append(f'spots：要 5–8 个景点，现在 {len(spots)} 个')
for n_ in re.findall(r'\d+', q):
    if int(n_) != len(spots):
        errs.append(f'question：问题里的数字 {n_} 和景点数 {len(spots)} 不一致')

cand = {}
cp = os.path.join(R, 'image_candidates.json')
if os.path.exists(cp):
    cand = {x['code']: x for v in json.load(open(cp, encoding='utf-8')).values() for x in v['items']}
ids = set()
for i, s in enumerate(spots, 1):
    w = f"景点 {i}（{s.get('id', '?')} {s.get('name', '')}）"
    sid = s.get('id', '')
    if not re.fullmatch(r's\d\d', sid) or sid in ids:
        errs.append(f'{w}：id 写成 s01 s02 …，不能重复')
    ids.add(sid)
    for k, lim in (('name', 6), ('where', 12)):
        v = s.get(k, '')
        if not v or width(v) > lim:
            errs.append(f'{w}：{k} 必填，≤{lim} 字（现在“{v}”）')
        bad_words(w, v)
    if not s.get('geo'):
        errs.append(f'{w}：geo 必填（维基百科条目名或地名，用来查坐标）')
    if not s.get('imageQuery'):
        errs.append(f'{w}：imageQuery 必填（中英文关键词，用 | 分隔）')
    fs = s.get('facts', [])
    if not 1 <= len(fs) <= 2:
        errs.append(f'{w}：facts 写 1–2 条')
    vs = []
    for j, f in enumerate(fs, 1):
        t = (f or {}).get('text', '')
        if width(t) > 18:
            errs.append(f'{w} 事实 {j}：太长，≤18 字（现在 {width(t):.0f}）：{t}')
        bad_words(f'{w} 事实 {j}', t)
        vs.append(check_fact(f'{w} 事实 {j}', f))
    verify[sid] = vs
    if s.get('move') and s['move'] not in ('ring', 'tilt', 'bands', 'pano', 'carousel', 'strips', 'bloom', 'truck'):
        errs.append(f'{w}：move 只能是 ring tilt bands pano carousel strips bloom truck 之一（或不写）')
    if STAGE == 'images':
        ims = s.get('images')
        if ims is None:
            errs.append(f'{w}：还没写 images（见 research/images.md；没有合适的写 "images": []）')
            continue
        if len(ims) > 4:
            errs.append(f'{w}：images 最多 4 张')
        for im in ims:
            if im.get('pick') and im['pick'] not in cand:
                errs.append(f'{w}：图片编号 {im["pick"]} 不在 research/images.md 的候选里')
            if im.get('pick') and not im['pick'].startswith(sid + '-'):
                errs.append(f'{w}：图片编号 {im["pick"]} 不是这个景点的候选（要以 {sid}- 开头）')
            if width(im.get('caption', '')) > 30:
                errs.append(f'{w}：图注 ≤30 字：{im.get("caption")}')
            bad_words(w + ' 图注', im.get('caption', ''))
        if not ims:
            warns.append(f'{w}：没有图片，会做成地图文字卡')

json.dump(verify, open(os.path.join(R, 'verify.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for x in warns:
    print('WARN', x)
for v in verify.values():
    for f in v or []:
        if f and f['status'] != '已核':
            print('待核对', f['status'], '：', f['text'])
for e in errs:
    print('ERROR', e)
print('CHECK OK' if not errs else f'CHECK FAILED（{len(errs)} 处）')
sys.exit(1 if errs else 0)
