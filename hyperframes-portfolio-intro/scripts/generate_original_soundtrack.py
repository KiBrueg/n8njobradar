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
# Structure: dark drone + slow pulses + soft risers + subtle ticks synced to scene beats.
beats = [1.2, 9.1, 12.2, 20.1, 25.1, 30.1, 34.0, 37.0, 45.0]
notes = [36.0, 48.0, 54.0, 72.0, 96.0]  # low harmonic bed

# Smooth deterministic noise generator state
noise_state = 0.0
samples = []
for i in range(N):
    t = i / SR

    # Master envelope: fade in, breathe, fade out
    fade_in = min(1.0, t / 3.0)
    fade_out = min(1.0, max(0.0, (DUR - t) / 2.2))
    env = fade_in * fade_out

    # Warm sub/space drone with slow beating
    drone = 0.0
    for idx, f in enumerate(notes):
        wobble = 0.06 * math.sin(2 * math.pi * (0.035 + idx * 0.011) * t)
        drone += math.sin(2 * math.pi * (f + wobble) * t + idx * 0.7) * (0.055 / (idx + 1))

    # Higher shimmer, filtered by slow envelope
    shimmer_env = 0.5 + 0.5 * math.sin(2 * math.pi * 0.045 * t - 0.7)
    shimmer = (
        math.sin(2 * math.pi * 384 * t + 0.7 * math.sin(2 * math.pi * 0.07 * t)) +
        math.sin(2 * math.pi * 512 * t + 0.5 * math.sin(2 * math.pi * 0.05 * t))
    ) * 0.006 * shimmer_env

    # Cinematic impacts at section changes, synthesized sine thumps
    impact = 0.0
    for b in beats:
        dt = t - b
        if 0 <= dt < 1.2:
            impact += math.sin(2 * math.pi * (70 - 32 * min(dt, 1.0)) * dt) * math.exp(-4.8 * dt) * 0.17

    # Credit roll pulse from 37s onward: small low heartbeat
    pulse = 0.0
    if t >= 37.0:
        p = (t - 37.0) % 0.9
        if p < 0.22:
            pulse = math.sin(2 * math.pi * 92 * p) * math.exp(-12 * p) * 0.055

    # Slow riser into credits/final fade
    riser = 0.0
    if 32.0 <= t <= 45.0:
        x = (t - 32.0) / 13.0
        riser = math.sin(2 * math.pi * (180 + 420 * x) * t) * (x * 0.012)

    # Soft deterministic air/noise, one-pole low-pass
    white = random.uniform(-1, 1)
    noise_state = noise_state * 0.985 + white * 0.015
    air = noise_state * 0.012

    mono = (drone + shimmer + impact + pulse + riser + air) * env

    # Gentle saturation/limiting
    mono = math.tanh(mono * 2.1) * 0.72
    val = int(max(-1.0, min(1.0, mono)) * 32767)
    samples.append(val)

with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    frames = bytearray()
    for s in samples:
        # slight stereo width via same signal, safe mono compatibility
        frames += int(s * 0.92).to_bytes(2, "little", signed=True)
        frames += int(s).to_bytes(2, "little", signed=True)
    w.writeframes(frames)

print(out)
