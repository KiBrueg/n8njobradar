import math
import random
import wave
from pathlib import Path

SR = 48000
DUR = 46.0
N = int(SR * DUR)
random.seed(20260708)
out = Path(__file__).resolve().parents[1] / "assets" / "original-cinematic-bed.wav"
out.parent.mkdir(parents=True, exist_ok=True)

# Original synthesized soundtrack: no samples, no third-party recordings.
# Audible cinematic bed: low drone + mid-frequency pulse + soft impacts + credit-roll heartbeat.
beats = [1.2, 9.1, 12.2, 20.1, 25.1, 30.1, 34.0, 37.0, 45.0]
root = 55.0  # A1, audible even on laptop speakers with harmonics
chord = [root, root * 1.5, root * 2.0, root * 2.5, root * 3.0, root * 4.0]

noise_state = 0.0
samples_l = []
samples_r = []
for i in range(N):
    t = i / SR
    fade_in = min(1.0, t / 1.8)
    fade_out = min(1.0, max(0.0, (DUR - t) / 1.8))
    env = fade_in * fade_out

    # Musical drone with harmonics in audible mids.
    drone = 0.0
    for idx, f in enumerate(chord):
        wobble = 0.10 * math.sin(2 * math.pi * (0.035 + idx * 0.009) * t)
        amp = [0.11, 0.07, 0.055, 0.035, 0.028, 0.018][idx]
        drone += math.sin(2 * math.pi * (f + wobble) * t + idx * 0.61) * amp

    # A slow ostinato pulse that is very audible on phones/laptops.
    step_len = 0.75
    p = t % step_len
    pulse_env = math.exp(-7.0 * p)
    pulse_freq = 165.0 if int(t / step_len) % 2 == 0 else 220.0
    pulse = math.sin(2 * math.pi * pulse_freq * p) * pulse_env * 0.13
    pulse += math.sin(2 * math.pi * (pulse_freq * 2) * p) * pulse_env * 0.045

    # Section impacts / whoosh-like thumps, entirely synthesized.
    impact = 0.0
    for b in beats:
        dt = t - b
        if 0 <= dt < 1.4:
            sweep = 120 - 55 * min(dt, 1.0)
            impact += math.sin(2 * math.pi * sweep * dt) * math.exp(-4.0 * dt) * 0.24
            impact += math.sin(2 * math.pi * 440 * dt) * math.exp(-10.0 * dt) * 0.035

    # Credits heartbeat: stronger after 37s so the ending is unmistakably alive.
    credit = 0.0
    if t >= 37.0:
        cp = (t - 37.0) % 0.62
        if cp < 0.20:
            credit = math.sin(2 * math.pi * 132 * cp) * math.exp(-10 * cp) * 0.14
            credit += math.sin(2 * math.pi * 264 * cp) * math.exp(-12 * cp) * 0.045

    # Soft high shimmer for cinematic air.
    shimmer = (
        math.sin(2 * math.pi * 660 * t + 0.8 * math.sin(2 * math.pi * 0.05 * t)) +
        math.sin(2 * math.pi * 880 * t + 0.7 * math.sin(2 * math.pi * 0.04 * t))
    ) * 0.012 * (0.45 + 0.55 * math.sin(2 * math.pi * 0.033 * t) ** 2)

    # Gentle deterministic noise layer.
    white = random.uniform(-1, 1)
    noise_state = noise_state * 0.975 + white * 0.025
    air = noise_state * 0.018

    mono = (drone + pulse + impact + credit + shimmer + air) * env

    # Soft limiter; target audible but not clipping.
    mono = math.tanh(mono * 2.4) * 0.82

    # Small stereo movement via phase-dependent pan, mono-compatible.
    pan = 0.10 * math.sin(2 * math.pi * 0.047 * t)
    l = mono * (0.93 - pan)
    r = mono * (0.93 + pan)
    samples_l.append(int(max(-1.0, min(1.0, l)) * 32767))
    samples_r.append(int(max(-1.0, min(1.0, r)) * 32767))

with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    frames = bytearray()
    for l, r in zip(samples_l, samples_r):
        frames += l.to_bytes(2, "little", signed=True)
        frames += r.to_bytes(2, "little", signed=True)
    w.writeframes(frames)

print(out)
