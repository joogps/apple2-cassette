"""
apple2tape.py — shared helpers for the Apple II cassette projects.

- Applesoft BASIC tokenizer (text lines -> tokenized program at $0801)
- Apple II cassette WAV encoder (two-record Applesoft LOAD format)
- Lo-res palette, screen memory layout, image loading helpers

Cassette timing (Apple II Monitor ROM):
  Header tone  : 770 Hz (650 us half-cycles)
  Sync bit     : 200 us + 250 us half-cycles
  '0' bit      : one 2 kHz cycle (250 us half-cycles)
  '1' bit      : one 1 kHz cycle (500 us half-cycles)
  Checksum     : XOR of all data bytes
"""

import io
import struct
import wave
import zipfile

# ── Audio / cassette timing ──────────────────────────────────────
SAMPLE_RATE = 44100
AMPLITUDE = 30000
HEADER_HALF_US = 650
SYNC_HALF1_US = 200
SYNC_HALF2_US = 250
BIT0_HALF_US = 250
BIT1_HALF_US = 500

# ── Apple II lo-res palette (RGB approximations) ─────────────────
LORES_PALETTE = [
    (0, 0, 0),        # 0  Black
    (227, 30, 96),    # 1  Magenta
    (96, 78, 189),    # 2  Dark Blue
    (255, 68, 253),   # 3  Purple
    (0, 163, 96),     # 4  Dark Green
    (156, 156, 156),  # 5  Grey 1
    (20, 207, 253),   # 6  Medium Blue
    (208, 195, 255),  # 7  Light Blue
    (96, 114, 3),     # 8  Brown
    (255, 106, 60),   # 9  Orange
    (156, 156, 156),  # 10 Grey 2
    (255, 160, 208),  # 11 Pink
    (20, 245, 60),    # 12 Green
    (255, 252, 125),  # 13 Yellow
    (114, 255, 208),  # 14 Aqua
    (255, 255, 255),  # 15 White
]

# Base address of each of the 24 text rows (each = 2 lo-res pixel rows)
TEXT_ROW_BASE = [
    0x0400, 0x0480, 0x0500, 0x0580, 0x0600, 0x0680, 0x0700, 0x0780,
    0x0428, 0x04A8, 0x0528, 0x05A8, 0x0628, 0x06A8, 0x0728, 0x07A8,
    0x0450, 0x04D0, 0x0550, 0x05D0, 0x0650, 0x06D0, 0x0750, 0x07D0,
]

# ── Applesoft tokenizer ──────────────────────────────────────────
TOKENS = {
    0x80: "END", 0x81: "FOR", 0x82: "NEXT", 0x83: "DATA", 0x84: "INPUT",
    0x85: "DEL", 0x86: "DIM", 0x87: "READ", 0x88: "GR", 0x89: "TEXT",
    0x8A: "PR#", 0x8B: "IN#", 0x8C: "CALL", 0x8D: "PLOT", 0x8E: "HLIN",
    0x8F: "VLIN", 0x90: "HGR2", 0x91: "HGR", 0x92: "HCOLOR=", 0x93: "HPLOT",
    0x94: "DRAW", 0x95: "XDRAW", 0x96: "HTAB", 0x97: "HOME", 0x98: "ROT=",
    0x99: "SCALE=", 0x9A: "SHLOAD", 0x9B: "TRACE", 0x9C: "NOTRACE",
    0x9D: "NORMAL", 0x9E: "INVERSE", 0x9F: "FLASH", 0xA0: "COLOR=",
    0xA1: "POP", 0xA2: "VTAB", 0xA3: "HIMEM:", 0xA4: "LOMEM:", 0xA5: "ONERR",
    0xA6: "RESUME", 0xA7: "RECALL", 0xA8: "STORE", 0xA9: "SPEED=", 0xAA: "LET",
    0xAB: "GOTO", 0xAC: "RUN", 0xAD: "IF", 0xAE: "RESTORE", 0xAF: "&",
    0xB0: "GOSUB", 0xB1: "RETURN", 0xB2: "REM", 0xB3: "STOP", 0xB4: "ON",
    0xB5: "WAIT", 0xB6: "LOAD", 0xB7: "SAVE", 0xB8: "DEF", 0xB9: "POKE",
    0xBA: "PRINT", 0xBB: "CONT", 0xBC: "LIST", 0xBD: "CLEAR", 0xBE: "GET",
    0xBF: "NEW", 0xC0: "TAB(", 0xC1: "TO", 0xC2: "FN", 0xC3: "SPC(",
    0xC4: "THEN", 0xC5: "AT", 0xC6: "NOT", 0xC7: "STEP", 0xC8: "+", 0xC9: "-",
    0xCA: "*", 0xCB: "/", 0xCC: "^", 0xCD: "AND", 0xCE: "OR", 0xCF: ">",
    0xD0: "=", 0xD1: "<", 0xD2: "SGN", 0xD3: "INT", 0xD4: "ABS", 0xD5: "USR",
    0xD6: "FRE", 0xD7: "SCRN(", 0xD8: "PDL", 0xD9: "POS", 0xDA: "SQR",
    0xDB: "RND", 0xDC: "LOG", 0xDD: "EXP", 0xDE: "COS", 0xDF: "SIN",
    0xE0: "TAN", 0xE1: "ATN", 0xE2: "PEEK", 0xE3: "LEN", 0xE4: "STR$",
    0xE5: "VAL", 0xE6: "ASC", 0xE7: "CHR$", 0xE8: "LEFT$", 0xE9: "RIGHT$",
    0xEA: "MID$",
}
_KEYWORDS = sorted(((kw, tok) for tok, kw in TOKENS.items()),
                   key=lambda kt: -len(kt[0]))


def tokenize_line(text):
    """Tokenize one line of Applesoft BASIC (without its line number)."""
    out = bytearray()
    i = 0
    in_string = in_rem = in_data = False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ord(ch))
            in_string = ch != '"'
            i += 1
            continue
        if in_rem:
            out.append(ord(ch))
            i += 1
            continue
        if in_data:
            if ch == ':':
                in_data = False
            out.append(ord(ch))
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ord(ch))
            i += 1
            continue
        upper = text[i:].upper()
        for kw, tok in _KEYWORDS:
            if upper.startswith(kw):
                out.append(tok)
                i += len(kw)
                in_rem = kw == "REM"
                in_data = kw == "DATA"
                break
        else:
            out.append(ord(ch))
            i += 1
    return bytes(out)


def build_program(lines):
    """[(linenum, text), ...] -> tokenized program bytes, laid out at $0801."""
    out = bytearray()
    addr = 0x0801
    for linenum, text in lines:
        content = tokenize_line(text)
        next_addr = addr + 4 + len(content) + 1
        out += bytes([next_addr & 0xFF, next_addr >> 8,
                      linenum & 0xFF, linenum >> 8])
        out += content
        out.append(0x00)
        addr = next_addr
    out += b"\x00\x00"  # end-of-program marker
    return bytes(out)


def data_lines(values, start_linenum, max_len=200):
    """Pack values into DATA lines of at most ~max_len characters."""
    lines = []
    linenum = start_linenum
    cur = ""
    for v in map(str, values):
        candidate = v if not cur else cur + "," + v
        if cur and len("DATA " + candidate) > max_len:
            lines.append((linenum, "DATA " + cur))
            linenum += 1
            cur = v
        else:
            cur = candidate
    if cur:
        lines.append((linenum, "DATA " + cur))
        linenum += 1
    return lines, linenum


# ── Cassette encoder ─────────────────────────────────────────────
class _Tape:
    def __init__(self):
        self.samples = []
        self.polarity = 1

    def half(self, us):
        n = max(1, round(us * SAMPLE_RATE / 1_000_000))
        self.samples.extend([AMPLITUDE if self.polarity > 0 else -AMPLITUDE] * n)
        self.polarity = -self.polarity

    def silence(self, seconds):
        self.samples.extend([0] * int(SAMPLE_RATE * seconds))

    def header(self, seconds):
        n = int(seconds / (HEADER_HALF_US / 1e6))
        n += n % 2
        for _ in range(n):
            self.half(HEADER_HALF_US)

    def sync(self):
        self.half(SYNC_HALF1_US)
        self.half(SYNC_HALF2_US)

    def byte(self, b):
        for i in range(7, -1, -1):
            h = BIT1_HALF_US if (b >> i) & 1 else BIT0_HALF_US
            self.half(h)
            self.half(h)

    def record(self, data, header_seconds):
        self.header(header_seconds)
        self.sync()
        checksum = 0
        for b in data:
            self.byte(b)
            checksum ^= b
        self.byte(checksum)

    def save(self, path):
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(struct.pack(f"<{len(self.samples)}h", *self.samples))
        return len(self.samples) / SAMPLE_RATE


def write_basic_tape(lines, out_path):
    """
    Tokenize an Applesoft program and write it as a cassette WAV
    in the two-record format that Applesoft's LOAD expects:
      record 1 = program length (2 bytes), record 2 = program.
    Returns (program_length_bytes, duration_seconds).
    """
    program = build_program(lines)
    length = len(program)
    tape = _Tape()
    tape.record(bytes([length & 0xFF, length >> 8]), header_seconds=10.0)
    tape.silence(0.3)
    tape.record(program, header_seconds=5.0)
    tape.silence(0.5)
    duration = tape.save(out_path)
    print(f"Program: {length} bytes  ($0801-${0x0801 + length:04X})")
    print(f"Wrote {out_path}  ({duration:.1f}s)")
    print("On the Apple II:  ] LOAD   -> play the WAV ->   ] RUN")
    return length, duration


# ── Image helpers ────────────────────────────────────────────────
def load_image(path):
    """Open an image file, or the first image inside a .zip (skips __MACOSX)."""
    from PIL import Image
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist()
                     if not n.startswith("__MACOSX")
                     and n.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))]
            if not names:
                raise SystemExit(f"No image found in {path}")
            return Image.open(io.BytesIO(zf.read(names[0])))
    return Image.open(path)


def pack_lores(pixels):
    """48x40 grid of color indices -> 960 screen bytes (text-row order)."""
    out = []
    for row in range(24):
        for col in range(40):
            top = int(pixels[row * 2][col])
            bottom = int(pixels[row * 2 + 1][col])
            out.append((bottom << 4) | top)
    return out


def screen_image_lines(screen_bytes, start_linenum=100):
    """BASIC program that POKEs 960 screen bytes into lo-res memory."""
    lines = [
        (5, "GR: POKE -16302,0"),
        (10, "FOR R=0 TO 23: READ A: FOR C=0 TO 39: READ V: POKE A+C,V: NEXT C,R"),
        (20, "GOTO 20"),
    ]
    linenum = start_linenum
    for row in range(24):
        row_data = [TEXT_ROW_BASE[row]] + list(screen_bytes[row * 40:(row + 1) * 40])
        new_lines, linenum = data_lines(row_data, linenum)
        lines += new_lines
    return lines


def save_lores_preview(pixels, path, scale=10):
    """Save a scaled-up PNG of a 48x40 lo-res index grid."""
    from PIL import Image
    img = Image.new("RGB", (40, 48))
    for y in range(48):
        for x in range(40):
            img.putpixel((x, y), LORES_PALETTE[int(pixels[y][x])])
    img.resize((40 * scale, 48 * scale), Image.NEAREST).save(path)
    print(f"Saved preview {path}")
