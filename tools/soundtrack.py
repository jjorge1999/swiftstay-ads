#!/usr/bin/env python3
"""Original, royalty-free soundtrack generator for SwiftStay reels.

Synthesises a short lo-fi / acoustic-pop music bed from scratch (no samples,
no copyrighted music) plus optional notification "ping" sound effects timed to
story beats, then writes a 44.1 kHz stereo WAV ready for ffmpeg.

usage: soundtrack.py OUT.wav DURATION_S [--seed N] [--bpm N] [--mood warm|upbeat|chill]
                     [--pings 0.4,2.4,4.4] [--whoosh 6.6]
The seed (e.g. the date as YYYYMMDD) changes key, progression, groove and
melody so no two reels sound the same.
"""
import argparse, numpy as np, wave

SR = 44100

def env(n, a=0.005, r=0.3):
    t = np.arange(n) / SR
    e = np.minimum(1, t / a) * np.exp(-t / r)
    return e

def keys_tone(f, dur, bright=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    s = (np.sin(2*np.pi*f*t) + 0.35*bright*np.sin(2*np.pi*2*f*t)*np.exp(-t*3)
         + 0.12*bright*np.sin(2*np.pi*3*f*t)*np.exp(-t*6))
    s *= 1 + 0.004*np.sin(2*np.pi*5*t)  # tiny wobble
    return s * env(n, 0.008, dur*0.55)

def pluck(f, dur):
    n = int(dur*SR); t = np.arange(n)/SR
    return (np.sin(2*np.pi*f*t)+0.5*np.sin(2*np.pi*2*f*t)*np.exp(-t*8)) * env(n, 0.002, 0.18)

def kick(dur=0.35):
    n = int(dur*SR); t = np.arange(n)/SR
    f = 110*np.exp(-t*18)+42
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t*9)

def snare(rng, dur=0.22):
    n = int(dur*SR); t = np.arange(n)/SR
    return (rng.standard_normal(n)*0.6 + np.sin(2*np.pi*190*t)*0.4) * np.exp(-t*22)

def hat(rng, dur=0.06):
    n = int(dur*SR); x = rng.standard_normal(n)
    x = np.diff(np.concatenate([[0], x]))  # crude high-pass
    return x * np.exp(-np.arange(n)/SR*60)

def ping(dur=0.5):
    n = int(dur*SR); t = np.arange(n)/SR
    a = np.sin(2*np.pi*1318.5*t)*env(n, 0.002, 0.12)
    b = np.zeros(n); k = int(0.09*SR)
    b[k:] = np.sin(2*np.pi*1760*t[:n-k])*env(n-k, 0.002, 0.18)
    return 0.5*a + 0.5*b

def whoosh(rng, dur=0.7):
    n = int(dur*SR); t = np.arange(n)/SR
    x = rng.standard_normal(n)
    x = np.convolve(x, np.ones(30)/30, 'same')
    return x * np.sin(np.pi*t/dur)**2

def add(buf, x, at, gain=1.0):
    i = int(at*SR)
    if i >= len(buf): return
    j = min(len(buf), i+len(x)); buf[i:j] += gain*x[:j-i]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('dur', type=float)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--bpm', type=int, default=0)
    ap.add_argument('--mood', default='warm', choices=['warm', 'upbeat', 'chill'])
    ap.add_argument('--pings', default='')
    ap.add_argument('--whoosh', default='')
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    bpm = a.bpm or {'warm': 92, 'upbeat': 112, 'chill': 78}[a.mood] + int(rng.integers(-6, 7))
    beat = 60/bpm
    root = 220*2**(int(rng.integers(-5, 4))/12)
    progs = [[0,9,5,7],[0,7,9,5],[9,5,0,7],[0,4,5,7],[5,7,0,9],[0,9,2,7]]
    prog = progs[int(rng.integers(len(progs)))]
    qual = {0:[0,4,7,11],2:[0,3,7,10],4:[0,3,7,10],5:[0,4,7,11],7:[0,4,7,10],9:[0,3,7,10]}
    scale = [0,2,4,7,9,12,14,16]
    n = int((a.dur+1)*SR); L = np.zeros(n); R = np.zeros(n)
    bar = 4*beat; t = 0.0; ci = 0
    hat_pat = rng.random(8) < (0.85 if a.mood == 'upbeat' else 0.6)
    while t < a.dur:
        deg = prog[ci % 4]
        for k, iv in enumerate(qual[deg]):
            f = root*2**((deg+iv)/12)
            tone = keys_tone(f, bar*1.05, 0.8 if a.mood != 'chill' else 0.5)
            add(L, tone, t+0.012*k, 0.10); add(R, tone, t+0.012*(3-k), 0.10)
        bass = keys_tone(root/2*2**(deg/12), bar*0.9, 0.3)
        add(L, bass, t, 0.22); add(R, bass, t, 0.22)
        for b in range(4):
            bt = t + b*beat
            if b in (0, 2) or (a.mood == 'upbeat' and b == 3 and rng.random() < .4):
                k_ = kick(); add(L, k_, bt, .5); add(R, k_, bt, .5)
            if b in (1, 3):
                s_ = snare(rng); add(L, s_, bt, .16); add(R, s_, bt, .16)
            for h in range(2):
                if hat_pat[(b*2+h) % 8]:
                    hh = hat(rng); add(L, hh, bt+h*beat/2, .05); add(R, hh, bt+h*beat/2+.003, .05)
            if rng.random() < 0.55:
                f = root*2*2**(scale[int(rng.integers(len(scale)))]/12)
                p_ = pluck(f, beat); add(L, p_, bt+beat/2*int(rng.integers(2)), .09); add(R, p_, bt+beat/2, .07)
        t += bar; ci += 1
    vinyl = rng.standard_normal(n)*0.004
    L += vinyl; R += vinyl
    for s in [x for x in a.pings.split(',') if x]:
        pg = ping(); add(L, pg, float(s), .35); add(R, pg, float(s), .35)
    for s in [x for x in a.whoosh.split(',') if x]:
        w = whoosh(rng); add(L, w, float(s)-0.35, .25); add(R, w, float(s)-0.35, .25)
    m = int(a.dur*SR); L, R = L[:m], R[:m]
    fade = np.ones(m); fi = int(0.3*SR); fo = int(1.2*SR)
    fade[:fi] = np.linspace(0, 1, fi); fade[-fo:] = np.linspace(1, 0, fo)
    st = np.stack([L*fade, R*fade], 1)
    st = np.tanh(st*1.6)/np.tanh(1.6)  # gentle saturation / limiter
    st *= 0.89/np.max(np.abs(st))
    with wave.open(a.out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st*32767).astype('<i2').tobytes())
    print(f'{a.out}: {a.dur}s bpm={bpm} root={root:.1f}Hz prog={prog}')

if __name__ == '__main__':
    main()
