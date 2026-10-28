"""Wikimedia Commons helper.

  python3 -I -X utf8 commons.py search "<query>" [limit]   list files with license / author
  python3 -I -X utf8 commons.py info "File:..."            full metadata as JSON
  python3 -I -X utf8 commons.py get "File:..." <out_dir> [width]   download (thumb if width)
"""
import json, os, re, subprocess, sys, tempfile, time, urllib.parse

API = 'https://commons.wikimedia.org/w/api.php'
UA = 'CityScenicBot/1.0 (documentary research)'


def _retry_after(hdr_path):
    """Parse Retry-After seconds from a curl -D header dump, if present."""
    if not os.path.exists(hdr_path):
        return None
    try:
        with open(hdr_path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.lower().startswith('retry-after:'):
                    val = line.split(':', 1)[1].strip()
                    try:
                        return int(val)
                    except ValueError:
                        return None
    finally:
        try:
            os.remove(hdr_path)
        except OSError:
            pass
    return None


def download(url, out_path, tries=8):
    """Download url → out_path with exponential backoff on 429/5xx/empty.

    Honors Retry-After when present. Verifies final file size > 0.
    """
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = out_path + '.part'
    hdr = out_path + '.hdr'
    backoff = 5
    last = None
    for attempt in range(tries):
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
            code = subprocess.check_output(
                ['curl', '-sS', '-L', '--noproxy', '*', '-m', '180', '-A', UA,
                 '-D', hdr, '-o', tmp, '-w', '%{http_code}', url],
                text=True, stderr=subprocess.STDOUT,
            ).strip()
            ra = _retry_after(hdr)
            code_i = int(code) if code.isdigit() else 0
            size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
            if code_i == 200 and size > 0:
                os.replace(tmp, out_path)
                return out_path
            last = f'HTTP {code_i} size={size}'
            if code_i == 429 or code_i >= 500 or size == 0 or code_i == 0:
                wait = ra if ra is not None else backoff
                print(f'commons download retry {attempt+1}/{tries}: {last}; sleep {wait}s', flush=True)
                time.sleep(wait)
                backoff = min(backoff * 2, 40)
                continue
            raise RuntimeError(f'commons download failed: {last} for {url}')
        except subprocess.CalledProcessError as e:
            last = str(e)
            ra = _retry_after(hdr)
            wait = ra if ra is not None else backoff
            print(f'commons download retry {attempt+1}/{tries}: curl err; sleep {wait}s', flush=True)
            time.sleep(wait)
            backoff = min(backoff * 2, 40)
    raise RuntimeError(f'commons download failed after {tries} tries ({last}): {url}')


def call(params, tries=8):
    """Commons API GET with 429/5xx/empty backoff (honors Retry-After)."""
    url = API + '?' + urllib.parse.urlencode(dict(params, format='json'))
    backoff = 5
    last = None
    for attempt in range(tries):
        hdr = os.path.join(tempfile.gettempdir(), f'commons-api-{os.getpid()}.hdr')
        try:
            out = subprocess.check_output(
                ['curl', '-sS', '-L', '--noproxy', '*', '-m', '60', '-A', UA,
                 '-D', hdr, '-w', '\n%{http_code}', url],
                text=True, stderr=subprocess.STDOUT,
            )
            # body then newline then http_code
            if '\n' in out:
                body, code = out.rsplit('\n', 1)
            else:
                body, code = out, '0'
            ra = _retry_after(hdr)
            code_i = int(code) if code.isdigit() else 0
            if code_i == 429 or code_i >= 500 or not body.strip():
                last = f'HTTP {code_i} empty={not body.strip()}'
                wait = ra if ra is not None else backoff
                print(f'commons api retry {attempt+1}/{tries}: {last}; sleep {wait}s', flush=True)
                time.sleep(wait)
                backoff = min(backoff * 2, 40)
                continue
            if code_i not in (0, 200):
                # odd non-retryable
                last = f'HTTP {code_i}'
                time.sleep(backoff)
                backoff = min(backoff * 2, 40)
                continue
            r = json.loads(body)
            if 'error' in r:
                last = r['error']
                time.sleep(backoff)
                backoff = min(backoff * 2, 40)
                continue
            return r
        except Exception as e:
            last = e
            ra = _retry_after(hdr) if os.path.exists(hdr) else None
            wait = ra if ra is not None else backoff
            print(f'commons api retry {attempt+1}/{tries}: {e}; sleep {wait}s', flush=True)
            time.sleep(wait)
            backoff = min(backoff * 2, 40)
    raise RuntimeError(f'commons api failed after {tries} tries: {last}')


def strip(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html or '')).strip()


def info(titles, width=None, page=None):
    p = dict(action='query', titles='|'.join(titles), prop='imageinfo',
             iiprop='url|size|extmetadata|mime')
    if width:
        p['iiurlwidth'] = width
    if page:
        p['iiurlparam'] = f'page{page}-{width or 1600}px'
    pages = call(p)['query']['pages']
    res = []
    for pg in pages.values():
        ii = (pg.get('imageinfo') or [{}])[0]
        em = ii.get('extmetadata', {})
        g = lambda k: strip(em.get(k, {}).get('value', ''))
        res.append(dict(title=pg.get('title'), url=ii.get('url'), thumb=ii.get('thumburl'),
                        page=ii.get('descriptionurl'), w=ii.get('width'), h=ii.get('height'),
                        mime=ii.get('mime'), license=g('LicenseShortName'), license_url=g('LicenseUrl'),
                        artist=g('Artist'), credit=g('Credit')[:200], date=g('DateTimeOriginal')[:80],
                        desc=g('ImageDescription')[:300]))
    return res


def search(q, limit=12):
    r = call(dict(action='query', list='search', srsearch=q, srnamespace=6, srlimit=limit))
    titles = [x['title'] for x in r['query']['search']]
    return info(titles) if titles else []


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'search':
        for x in search(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12):
            print(f"{x['title']} | {x['w']}x{x['h']} | {x['license']} | {x['artist'][:50]} | {x['date'][:30]} | {x['desc'][:110]}")
    elif cmd == 'info':
        print(json.dumps(info([sys.argv[2]]), ensure_ascii=False, indent=1))
    elif cmd == 'get':
        width = int(sys.argv[4]) if len(sys.argv) > 4 else None
        page = int(sys.argv[5]) if len(sys.argv) > 5 else None
        x = info([sys.argv[2]], width, page)[0]
        url = x['thumb'] if width and x.get('thumb') else x['url']
        os.makedirs(sys.argv[3], exist_ok=True)
        name = re.sub(r'[^\w.\-]+', '_', x['title'].split(':', 1)[1])
        if page:
            name += f'.p{page}.jpg'
        out = os.path.join(sys.argv[3], name)
        download(url, out)
        x['local'] = out
        print(json.dumps(x, ensure_ascii=False))
