#!/usr/bin/env python3
"""
stream_mac.py — Mac side of the live screen mirror.

Captures the primary display, downsamples to 40x48, quantizes to the 16
Apple II lo-res colors, and plays each frame as FSK audio out the headphone
jack for the receiver from 06_mirror_receiver.py.

  pip3 install mss Pillow sounddevice numpy
  python3 stream_mac.py          (Ctrl+C to stop)

Setup: 3.5mm cable from Mac headphone out -> Apple II cassette IN,
volume ~65-75%, audio effects off, Do Not Disturb on.

Frame = 200 '1' bits of lead-in + sync byte $A5 + 960 screen bytes.
'0' = one 8 kHz cycle, '1' = one 4 kHz cycle  ->  roughly 0.7 fps.
"""

import sys
import time
import numpy as np

try:
    import mss
    import sounddevice as sd
    from PIL import Image
except ImportError as e:
    sys.exit(f"Missing dependency ({e.name}). Run: pip3 install mss Pillow sounddevice numpy")

SAMPLE_RATE = 44100
AMPLITUDE = 0.9
BIT0_HALF = 62.5e-6     # 8 kHz
BIT1_HALF = 125.0e-6    # 4 kHz
SYNC_BYTE = 0xA5
LEAD_IN_BITS = 200

PALETTE = np.array([
    [0, 0, 0], [227, 30, 96], [96, 78, 189], [255, 68, 253],
    [0, 163, 96], [156, 156, 156], [20, 207, 253], [208, 195, 255],
    [96, 114, 3], [255, 106, 60], [156, 156, 156], [255, 160, 208],
    [20, 245, 60], [255, 252, 125], [114, 255, 208], [255, 255, 255],
], dtype=np.float32)
WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)

# Pre-rendered audio for each bit value (one full cycle each)
def _cycle(half):
    n = max(1, round(half * SAMPLE_RATE))
    return np.concatenate([np.full(n, AMPLITUDE), np.full(n, -AMPLITUDE)]).astype(np.float32)

BIT_AUDIO = {0: _cycle(BIT0_HALF), 1: _cycle(BIT1_HALF)}
BYTE_AUDIO = [np.concatenate([BIT_AUDIO[(b >> i) & 1] for i in range(7, -1, -1)])
              for b in range(256)]
LEAD_IN = np.tile(BIT_AUDIO[1], LEAD_IN_BITS)


def capture_frame(sct):
    shot = sct.grab(sct.monitors[1])
    img = Image.frombytes("RGB", shot.size, shot.rgb).resize((40, 48), Image.LANCZOS)
    px = np.asarray(img, dtype=np.float32).reshape(-1, 1, 3)
    idx = np.argmin((((px - PALETTE[None]) ** 2) * WEIGHTS).sum(axis=2), axis=1)
    idx = idx.reshape(48, 40)
    return ((idx[1::2] << 4) | idx[0::2]).astype(np.uint8).ravel()  # 960 bytes


def encode_frame(screen_bytes):
    return np.concatenate([LEAD_IN, BYTE_AUDIO[SYNC_BYTE]] +
                          [BYTE_AUDIO[b] for b in screen_bytes])


def main():
    print("Streaming to Apple II — make sure the receiver is RUNning. Ctrl+C to stop.")
    sct = mss.mss()
    frames = 0
    try:
        while True:
            t0 = time.time()
            audio = encode_frame(capture_frame(sct))
            sd.play(audio, SAMPLE_RATE)
            sd.wait()
            frames += 1
            dt = time.time() - t0
            print(f"\r  frame {frames}  {dt * 1000:.0f} ms  ({1 / dt:.2f} fps)", end="", flush=True)
    except KeyboardInterrupt:
        sd.stop()
        print(f"\nStopped after {frames} frames.")


if __name__ == "__main__":
    main()
