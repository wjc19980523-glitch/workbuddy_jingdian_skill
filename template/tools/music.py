"""Step 7 — original score + sound effects, synthesised from build/events.json (no third-party audio).

usage: python3 -I music.py <cityDir>  →  build/score.wav (48 kHz stereo)

120 BPM, D major pentatonic: plucked-string arpeggios (Karplus–Strong), warm pad, sub bass, half-time drums.
Arrangement follows the timeline: hook ticks → impact on the title → groove under the spots → drop-out on the
map hop → drums leave for the closing question. Effects sit on the same events the picture cuts on:
whoosh before whips/rolls/dives, hit on every cut, accent on in-shot reveals, chime under the question.
Deterministic (fixed seed).
"""
import json, os, sys
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

CITY = os.path.abspath(sys.argv[1])
B = os.path.join(CITY, 'build')
tl = json.load(open(os.path.join(B, 'events.json'), encoding='utf-8'))
SR = 48000
DUR = tl['dur'] + 0.6
N = int(DUR * SR)
BEAT = 60 / tl['bpm']
rng = np.random.default_rng(7)
mus = np.zeros((N, 2), np.float32)
sfx = np.zeros((N, 2), np.float32)
shots = tl['shots']
t_spots = next(s['t0'] for s in shots if s['kind'] != 'intro')
fin = shots[-1]
t_q = fin['t0'] + 3.2 + 0.9
hops = [(s['t0'], s['t1']) for s in shots if s['kind'] == 'hop']
hook_end = next(e['t'] for e in tl['events'] if e['kind'] == 'impact')


def add(buf, t, sig, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N or i + len(sig) <= 0:
        return
    if i < 0:
        sig = sig[-i:]; i = 0
    sig = sig[: N - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:i + len(sig), 0] += sig * gain * l * 1.414
    buf[i:i + len(sig), 1] += sig * gain * r * 1.414


def env(n, a=0.005, d=0.3, curve=4.0):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-curve * np.maximum(0, t - a) / max(d, 1e-3))
    return e.astype(np.float32)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], 'band', fs=SR, output='sos'), x).astype(np.float32)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, 'low', fs=SR, output='sos'), x).astype(np.float32)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, 'high', fs=SR, output='sos'), x).astype(np.float32)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def pluck(f, dur=1.6, bright=0.5):
    n = int(dur * SR); p = max(2, int(SR / f))
    buf = (rng.random(p) * 2 - 1).astype(np.float32)
    buf = lp(buf, 1500 + 6000 * bright, 1)
    out = np.zeros(n, np.float32)
    damp = 0.996 if f < 400 else 0.993
    for i in range(n):   # Karplus–Strong
        j = i % p
        v = buf[j]
        out[i] = v
        buf[j] = damp * 0.5 * (v + buf[(j + 1) % p])
    out *= env(n, 0.002, dur * 0.5, 2.5)
    return out


_pl_cache = {}


def pluck_c(m, dur=1.4, bright=0.5):
    k = (m, dur, bright)
    if k not in _pl_cache:
        _pl_cache[k] = pluck(midi(m), dur, bright)
    return _pl_cache[k]


def pad(fs, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.zeros(n, np.float32)
    for f in fs:
        for det in (-0.12, 0.0, 0.13):
            ph = rng.random() * 6.28
            s += np.sign(np.sin(2 * np.pi * f * (1 + det / 100) * t + ph)) * 0.15 + np.sin(2 * np.pi * f * (1 + det / 100) * t + ph) * 0.5
    s = lp(s, 1400, 2)
    a = np.minimum(1, t / 0.6) * np.minimum(1, (dur - t) / 0.6)
    return (s * a / max(1, len(fs) * 3)).astype(np.float32)


def kick(a=1.0):
    n = int(0.45 * SR); t = np.arange(n) / SR
    f = 48 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * 7.5) + 0.25 * (rng.random(n) * 2 - 1) * np.exp(-t * 120)
    return (s * a).astype(np.float32)


def clap(a=1.0):
    n = int(0.35 * SR)
    s = bp((rng.random(n) * 2 - 1).astype(np.float32), 900, 3500)
    e = np.zeros(n, np.float32)
    for k, off in enumerate((0, 0.011, 0.022)):
        i = int(off * SR); e[i:] += env(n - i, 0.001, 0.02 if k < 2 else 0.12, 3)
    return s * e * a * 1.6


def hat(a=1.0, open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    s = hp((rng.random(n) * 2 - 1).astype(np.float32), 7000)
    return s * env(n, 0.001, 0.08 if open_ else 0.015, 3) * a


def whoosh(dur=0.5, up=True):
    n = int(dur * SR); t = np.arange(n) / SR
    x = (rng.random(n) * 2 - 1).astype(np.float32)
    u = t / dur if up else 1 - t / dur
    pos = u * 5
    out = np.zeros(n, np.float32)
    for j in range(6):   # crossfade through six bands: a sweep without block clicks
        fc = 300 * 12 ** (j / 5)
        wgt = np.clip(1 - np.abs(pos - j), 0, 1)
        out += bp(x, fc * 0.6, min(fc * 2.2, 20000)) * wgt
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    return lp(out * e, 9000) * 1.8


def boom(a=1.0, dur=2.2):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 38 + 60 * np.exp(-t * 6)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    s += lp((rng.random(n) * 2 - 1).astype(np.float32), 1800) * np.exp(-t * 4) * 0.5
    return (s * a).astype(np.float32)


def riser(dur=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 200 * 6 ** (t / dur)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3 + whoosh(dur, True)[:n] * 0.8
    return s * (t / dur) ** 2


def bell(f, dur=2.5):
    n = int(dur * SR); t = np.arange(n) / SR
    mod = np.sin(2 * np.pi * f * 3.5 * t) * 2.2 * np.exp(-t * 3)
    return (np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 1.8)).astype(np.float32)


def tick():
    n = int(0.08 * SR)
    s = bp((rng.random(n) * 2 - 1).astype(np.float32), 1800, 5000) * env(n, 0.0005, 0.012, 3)
    return s + pluck_c(86, 0.08, 0.9)[:n] * 0.6


# ---------------------------------------------------------------- music
# progression per bar (2 s): D  Bm  G  A   (D major pentatonic melody notes: D E F# A B)
ROOTS = [50, 47, 43, 45]
CHORDS = {50: [62, 66, 69], 47: [59, 62, 66], 43: [55, 59, 62], 45: [57, 61, 64]}
PENTA = [62, 64, 66, 69, 71, 74, 76, 78, 81]
ARP = [0, 2, 4, 3, 5, 4, 2, 3, 1, 3, 5, 6, 4, 3, 2, 1]   # indices into PENTA, 16ths
bar = 4 * BEAT
nb = int(np.ceil(DUR / bar))


def in_hop(t):
    return any(a <= t < b for a, b in hops)


for b in range(nb):
    t0 = b * bar
    root = ROOTS[b % 4]
    # pad across the whole film (soft in hook, full after)
    g = 0.28 if t0 < hook_end else 0.45
    if t0 >= t_q - 0.1:
        g = 0.55
    add(mus, t0, pad([midi(m) for m in CHORDS[root]], bar + 0.6), g, 0)
    if t0 + bar <= hook_end:
        continue
    groove = t_spots - 0.01 <= t0 < t_q - 0.5
    # sub bass: root on 1, octave pop on the and of 2
    for k, (off, m, ln) in enumerate(((0, root - 12, 0.9), (1.5 * BEAT, root, 0.25), (2 * BEAT, root - 12, 0.7), (3.5 * BEAT, root - 5, 0.3))):
        tt = t0 + off
        if tt < hook_end or in_hop(tt) or (not groove and k % 2):
            continue
        n = int(ln * SR); tt_ = np.arange(n) / SR
        s = np.sin(2 * np.pi * midi(m) * tt_) * env(n, 0.005, ln * 0.6, 2.5) + 0.3 * np.sin(4 * np.pi * midi(m) * tt_) * env(n, 0.003, 0.08, 3)
        add(mus, tt, s.astype(np.float32), 0.5 if groove else 0.3)
    # plucked arpeggio, 16ths, transposed with the chord
    shift = {50: 0, 47: -3, 43: -7, 45: -5}[root]
    for k in range(16):
        tt = t0 + k * BEAT / 4
        if tt < hook_end or (in_hop(tt) and k % 2):
            continue
        if not groove and k % 2:
            continue
        idx = ARP[(k + b * 3) % 16]
        m = PENTA[idx] + (shift if shift > -5 else shift + 12) - 12 * (k % 4 == 0)
        acc = 1.0 if k % 4 == 0 else 0.62
        add(mus, tt, pluck_c(m, 1.2, 0.45 + 0.2 * acc), 0.16 * acc, 0.35 * np.sin(k * 1.7))
    if not groove:
        continue
    # drums: half-time — kick on 1 and the and of 2, clap on 3, hats on 8ths
    for off, kind in ((0, 'k'), (1.5 * BEAT, 'k'), (2 * BEAT, 'c'), (3 * BEAT + 0.75 * BEAT, 'k2')):
        tt = t0 + off
        if in_hop(tt):
            continue
        if kind == 'k':
            add(mus, tt, kick(), 0.85)
        elif kind == 'k2':
            add(mus, tt, kick(0.6), 0.5)
        else:
            add(mus, tt, clap(), 0.33, 0.1)
    for k in range(8):
        tt = t0 + k * BEAT / 2
        if not in_hop(tt):
            add(mus, tt, hat(0.8 if k % 2 else 0.5, open_=(k == 7)), 0.16, -0.3 if k % 2 else 0.3)

# ---------------------------------------------------------------- effects on the picture's events
for e in tl['events']:
    t, k, a = e['t'], e['kind'], e.get('a', 1)
    if k == 'tick':
        add(sfx, t, tick(), 0.35 * a, 0.2 * np.sin(t * 9))
        add(sfx, t, kick(0.5)[: int(0.12 * SR)], 0.35)
    elif k == 'impact':
        add(sfx, t, boom(1.0, 2.6), 0.9); add(sfx, t, clap(1.2), 0.4)
        add(sfx, t, bell(midi(74), 3.0), 0.12, -0.2); add(sfx, t, bell(midi(81), 3.0), 0.08, 0.2)
    elif k == 'riser':
        add(sfx, t, riser(e.get('d', 1.0)), 0.35)
    elif k == 'whoosh':
        w = whoosh(0.42, e.get('trans') not in ('pull',))
        add(sfx, t - 0.12, w, 0.5 * a, -0.4 if e.get('trans') == 'whip' else 0.3)
    elif k == 'hit':
        add(sfx, t, kick(0.9)[: int(0.3 * SR)], 0.45)
        add(sfx, t, lp((rng.random(int(0.5 * SR)) * 2 - 1).astype(np.float32), 5000) * env(int(0.5 * SR), 0.002, 0.15, 3), 0.12)
        if e.get('trans') in ('dive', 'pull'):
            add(sfx, t, boom(0.6, 1.4), 0.45)
    elif k == 'accent':
        add(sfx, t, whoosh(0.3, True), 0.3); add(sfx, t + 0.2, bell(midi(86), 1.2), 0.05)
    elif k == 'chime':
        for j, m in enumerate((74, 78, 81, 86)):
            add(sfx, t + j * 0.12, bell(midi(m), 3.0), 0.09, -0.3 + 0.2 * j)

# ---------------------------------------------------------------- room, duck, master
ir_n = int(1.9 * SR); ti = np.arange(ir_n) / SR
ir = np.stack([(rng.random(ir_n) * 2 - 1) * np.exp(-ti * 3.2) for _ in range(2)], 1).astype(np.float32)
ir[:, 0] = lp(ir[:, 0], 6000); ir[:, 1] = lp(ir[:, 1], 6000)
ir /= np.sqrt((ir ** 2).sum(0, keepdims=True))
wet_m = np.stack([fftconvolve(mus[:, c], ir[:, c])[:N] for c in range(2)], 1)
wet_s = np.stack([fftconvolve(sfx[:, c], ir[:, c])[:N] for c in range(2)], 1)
mix_m = mus + 0.22 * wet_m
mix_s = sfx + 0.14 * wet_s
# duck the music a little under hits
duck = np.ones(N, np.float32)
for e in tl['events']:
    if e['kind'] in ('hit', 'impact'):
        i = int(e['t'] * SR); n = int(0.35 * SR)
        if i < N:
            seg = 1 - 0.35 * np.exp(-np.arange(min(n, N - i)) / SR / 0.12)
            duck[i:i + len(seg)] = np.minimum(duck[i:i + len(seg)], seg)
out = mix_m * duck[:, None] + mix_s
# fades
fi = int(0.05 * SR); out[:fi] *= np.linspace(0, 1, fi)[:, None]
fo = int(2.2 * SR); out[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
out /= max(1e-6, np.abs(out).max()) / 0.89
import wave
pcm = (np.clip(out, -1, 1) * 32767).astype('<i2')
with wave.open(os.path.join(B, 'score.wav'), 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('score.wav', round(DUR, 2), 's')
