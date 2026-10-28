"""Step 5 — satellite maps for the fly-over shots (open data, no keys).

usage: python3 -I fetch_map.py <cityDir>

Reads spots.json (lon/lat filled by geocode.py) and writes <cityDir>/assets/map/:
  local.jpg + local.json   spots' bounding box (+ margin), NASA GIBS HLS (Harmonized Landsat Sentinel-2, 30 m),
                           least-cloudy cool-season date picked automatically, gaps filled from the next-best dates
  wide.jpg  + wide.json    ~4° around the city, NASA GIBS VIIRS (NOAA-20 / SNPP) true colour, clearest date
Both are web-mercator images; the json holds lon0/lon1/lat0/lat1 and the dates used (credited on screen + in
image-sources.md). Re-running reuses downloaded tiles.
"""
import concurrent.futures as cf
import datetime, json, math, os, subprocess, sys
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
CITY = os.path.abspath(sys.argv[1])
M = os.path.join(CITY, 'assets', 'map'); TMP = os.path.join(CITY, 'build', 'mapdl')
os.makedirs(M, exist_ok=True); os.makedirs(TMP, exist_ok=True)
UA = 'CityScenicBot/1.0 (travel film; open data)'
R = 6378137.0
spots = json.load(open(os.path.join(CITY, 'spots.json')))['spots']
city = json.load(open(os.path.join(CITY, 'city.json')))
WMS = 'https://gibs.earthdata.nasa.gov/wms/{crs}/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0'
HLS = {'S30': 'HLS_S30_Nadir_BRDF_Adjusted_Reflectance', 'L30': 'HLS_L30_Nadir_BRDF_Adjusted_Reflectance'}
WIDE_LAYERS = ['VIIRS_NOAA20_CorrectedReflectance_TrueColor', 'VIIRS_SNPP_CorrectedReflectance_TrueColor', 'MODIS_Aqua_CorrectedReflectance_TrueColor']


def merc(lon, lat):
    return R * math.radians(lon), R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def inv(x, y):
    return math.degrees(x / R), math.degrees(2 * math.atan(math.exp(y / R)) - math.pi / 2)


def curl(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 100:
        try:
            Image.open(path).load(); return True
        except Exception:
            os.remove(path)
    for _ in range(5):
        subprocess.call(['curl', '-s', '-m', '120', '-A', UA, '-o', path, url])
        try:
            Image.open(path).load(); return True
        except Exception:
            pass
    return False


def probe(layer, bbox, dates, tag):
    """score each date on a 200 px preview: coverage minus 3 × cloud (bright) fraction"""
    def one(d):
        f = os.path.join(TMP, f'probe_{tag}_{layer[:12]}_{d}.png')
        u = (WMS.format(crs='epsg4326') + f'&LAYERS={layer}&CRS=EPSG:4326&BBOX={bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}'
             f'&WIDTH=200&HEIGHT=180&FORMAT=image/png&TRANSPARENT=TRUE&TIME={d}')
        if not curl(u, f):
            return None
        a = np.asarray(Image.open(f).convert('RGBA'), np.float32)
        ok = (a[..., 3] > 0) & (a[..., :3].sum(-1) > 30)   # transparent or black = no data
        cov = ok.mean(); rgb = a[..., :3][ok]
        cloud = (rgb.mean(1) > 170).mean() if len(rgb) else 1.0
        return dict(layer=layer, date=str(d), cov=float(cov), cloud=float(cloud), score=float(cov - 3 * cloud))
    with cf.ThreadPoolExecutor(8) as ex:
        res = [r for r in ex.map(one, dates) if r and r['cov'] > 0.3]
    return sorted(res, key=lambda r: -r['score'])


def mosaic(name, bbox, W, picks, tile=2048):
    x0, y0 = merc(bbox[0], bbox[1]); x1, y1 = merc(bbox[2], bbox[3])
    mpp = (x1 - x0) / W; H = int((y1 - y0) / mpp)
    nx, ny = math.ceil(W / tile), math.ceil(H / tile)
    acc = np.zeros((ny * tile, nx * tile, 3), np.uint8); have = np.zeros(acc.shape[:2], bool); used = []
    for p in picks:
        img = np.zeros((ny * tile, nx * tile, 4), np.uint8)
        for j in range(ny):
            for i in range(nx):
                bx0, bx1 = x0 + i * tile * mpp, x0 + (i + 1) * tile * mpp
                by1, by0 = y1 - j * tile * mpp, y1 - (j + 1) * tile * mpp
                f = os.path.join(TMP, f"{name}_{p['layer'][:12]}_{p['date']}_{i}_{j}.png")
                u = (WMS.format(crs='epsg3857') + f"&LAYERS={p['layer']}&CRS=EPSG:3857&BBOX={bx0},{by0},{bx1},{by1}"
                     f"&WIDTH={tile}&HEIGHT={tile}&FORMAT=image/png&TRANSPARENT=TRUE&TIME={p['date']}")
                if curl(u, f):
                    img[j * tile:(j + 1) * tile, i * tile:(i + 1) * tile] = np.asarray(Image.open(f).convert('RGBA'))
        ok = (img[..., 3] > 0) & (img[..., :3].astype(np.int32).sum(-1) > 30)
        if used:
            ok &= img[..., :3].mean(-1) < 170
        fill = ok & ~have
        if fill.mean() > 0.0005 or not used:
            acc[fill] = img[..., :3][fill]; have |= fill; used.append(f"{p['layer']} {p['date']}")
        print(name, p['date'], 'coverage', round(float(have[:H, :W].mean()), 4), flush=True)
        if have[:H, :W].mean() > 0.998:
            break
    acc = acc[:H, :W]; have = have[:H, :W]
    if not have.all():   # holes: fill with the mean colour of the known pixels, blurred in
        from PIL import ImageFilter
        mean = acc[have].mean(0) if have.any() else np.array([60, 70, 60])
        acc[~have] = mean.astype(np.uint8)
        bl = np.asarray(Image.fromarray(acc).filter(ImageFilter.GaussianBlur(12)))
        acc = np.where(have[..., None], acc, bl)
    # gentle grade: lift HLS/MODIS flat reflectance into a punchy but natural picture
    a = acc.astype(np.float32) / 255
    lo, hi = np.percentile(a, 1), np.percentile(a, 99.5)
    a = np.clip((a - lo) / max(hi - lo, 1e-3), 0, 1) ** 0.85
    g = a.mean(-1, keepdims=True); a = np.clip(g + (a - g) * 1.25, 0, 1)
    lon0, lat0 = inv(x0, y0); lon1, lat1 = inv(x0 + W * mpp, y0 + H * mpp)
    Image.fromarray((a * 255).astype(np.uint8)).save(os.path.join(M, name + '.jpg'), quality=90)
    meta = dict(w=W, h=H, lon0=lon0, lon1=lon1, lat0=lat0, lat1=lat1, dates=used, layer=picks[0]['layer'])
    json.dump(meta, open(os.path.join(M, name + '.json'), 'w'), indent=1)
    return meta


pts = [(s['lon'], s['lat']) for s in spots if s.get('lon') is not None]
pts.append((city['center']['lon'], city['center']['lat']))
lons, lats = [p[0] for p in pts], [p[1] for p in pts]
cx, cy = (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2
hw = max((max(lons) - min(lons)) / 2 + .14, .3); hh = max((max(lats) - min(lats)) / 2 + .14, .3)
hw = max(hw, hh * 1.0); hh = max(hh, hw * 0.75)
local = [round(cx - hw, 4), round(cy - hh, 4), round(cx + hw, 4), round(cy + hh, 4)]
wide = [round(cx - 2.2, 4), round(cy - 1.9, 4), round(cx + 2.2, 4), round(cy + 1.9, 4)]
today = datetime.date.today()

if not os.path.exists(os.path.join(M, 'local.json')):
    dates = [today - datetime.timedelta(days=d) for d in range(30, 760, 3)]
    dates = [d for d in dates if d.month in (10, 11, 12, 1, 2, 3, 4)]
    ranked = []
    for L in HLS.values():
        ranked += probe(L, local, dates, 'local')
    ranked.sort(key=lambda r: -r['score'])
    print('local best', ranked[:3])
    mosaic('local', local, 4096, ranked[:6])
if not os.path.exists(os.path.join(M, 'wide.json')):
    dates = [today - datetime.timedelta(days=d) for d in range(20, 400, 3)]
    ranked = []
    for L in WIDE_LAYERS:
        ranked = probe(L, wide, dates, 'wide')
        if ranked and ranked[0]['score'] > 0.6:
            break
    print('wide best', ranked[:3])
    mosaic('wide', wide, 2048, ranked[:3])
city['mapCredit'] = '卫星影像：NASA GIBS（HLS / VIIRS）'
json.dump(city, open(os.path.join(CITY, 'city.json'), 'w'), ensure_ascii=False, indent=1)
print('map ok')
