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

# Original synthesized soundtrack: soft Reiki-style ambient bed.
# No samples, no loops, no external recordings, no AI voice/model.
# Design: warm drones, gentle bell-like overtones, very soft breath/noise, no hard impacts.
base = 136.10  # C#3-ish, warm but audible
# A soft major/add9-ish harmonic field, intentionally slow and non-rhythmic.
freqs = [base / 2, base, base * 1.25, base * 1.5, base * 2.0, base * 2.5, base * 3.0]
amps =  [0.035,    0.052, 0.026,       0.034,      0.020,      0.014,      0.010]

noise_state = 0.0
samples_l = []
samples_r = []
for i in range(N):
    t = i / SR
    fade_in = min(1.0, t / 5.0)
    fade_out = min(1.0, max(0.0, (DUR - t) / 5.0))
    env = fade_in * fade_out

    pad = 0.0
    for idx, (f, a) in enumerate(zip(freqs, amps)):
        # Slow drifting pitch/phase for organic calm movement.
        drift = 0.18 * math.sin(2 * math.pi * (0.011 + idx * 0.004) * t + idx)
        breath = 0.72 + 0.28 * math.sin(2 * math.pi * (0.025 + idx * 0.003) * t + idx * 0.8)
        pad += math.sin(2 * math.pi * (f + drift) * t + idx * 0.53) * a * breath

    # Soft singing-bowl-like partials, no sharp attack.
    bowl = 0.0
    for start, f, a in [(7.5, 528.0, 0.018), (18.0, 432.0, 0.014), (29.5, 660.0, 0.012), (37.0, 396.0, 0.014)]:
        dt = t - start
        if 0 <= dt <= 10.0:
            attack = min(1.0, dt / 1.2)
            decay = math.exp(-0.18 * dt)
            bowl += math.sin(2 * math.pi * f * dt + 0.35 * math.sin(2 * math.pi * 0.08 * dt)) * a * attack * decay

    # Gentle airy texture, low-passed deterministic noise.
    white = random.uniform(-1, 1)
    noise_state = noise_state * 0.992 + white * 0.008
    air = noise_state * 0.010

    # Very slow shimmer, kept quiet to avoid harshness.
    shimmer_env = 0.5 + 0.5 * math.sin(2 * math.pi * 0.018 * t - 1.2)
    shimmer = (
        math.sin(2 * math.pi * 792 * t + 0.4 * math.sin(2 * math.pi * 0.031 * t)) +
        math.sin(2 * math.pi * 1056 * t + 0.3 * math.sin(2 * math.pi * 0.027 * t))
    ) * 0.0045 * shimmer_env

    mono = (pad + bowl + air + shimmer) * env

    # Soft limiter, intentionally below loudness-war levels.
    mono = math.tanh(mono * 1.8) * 0.72
    pan = 0.12 * math.sin(2 * math.pi * 0.021 * t)
    l = mono * (0.94 - pan)
    r = mono * (0.94 + pan)
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
