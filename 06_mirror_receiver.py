#!/usr/bin/env python3
"""
Apple II side of the live screen mirror. Writes a cassette tape whose BASIC
program POKEs a 151-byte 6502 receiver into $0300 and CALLs it.

The receiver polls the cassette input ($C060 bit 7), decodes FSK at 2x the
standard cassette speed ('0' = 8 kHz cycle, '1' = 4 kHz cycle), hunts
bit-by-bit for the sync byte $A5, then writes 960 bytes straight into
lo-res screen memory, row by row. Pair it with stream_mac.py.

Output: mirror_receiver.wav
"""

from apple2tape import data_lines, write_basic_tape

ML = bytes([
    # $0300  init: graphics, full screen, lo-res
    0xAD, 0x50, 0xC0,        # LDA $C050
    0xAD, 0x52, 0xC0,        # LDA $C052
    0xAD, 0x56, 0xC0,        # LDA $C056
    # $0309  FLOOP
    0x20, 0x33, 0x03,        # JSR WSYNC
    0xA9, 0x00,              # LDA #0
    0x85, 0x04,              # STA $04         ; row = 0
    # $0310  RLOOP
    0xA6, 0x04,              # LDX $04
    0xBD, 0x67, 0x03,        # LDA ROWLO,X
    0x85, 0x00,              # STA $00
    0xBD, 0x7F, 0x03,        # LDA ROWHI,X
    0x85, 0x01,              # STA $01
    0xA0, 0x00,              # LDY #0
    # $031E  CLOOP
    0x20, 0x43, 0x03,        # JSR RBYTE
    0x91, 0x00,              # STA ($00),Y
    0xC8,                    # INY
    0xC0, 0x28,              # CPY #40
    0xD0, 0xF6,              # BNE CLOOP
    # $0328
    0xE6, 0x04,              # INC $04
    0xA5, 0x04,              # LDA $04
    0xC9, 0x18,              # CMP #24
    0xD0, 0xE0,              # BNE RLOOP
    0x4C, 0x09, 0x03,        # JMP FLOOP
    # $0333  WSYNC: shift bits in one at a time until the register == $A5
    0xA9, 0x00,              # LDA #0
    0x85, 0x02,              # STA $02
    # $0337  WS1
    0x20, 0x57, 0x03,        # JSR RBIT
    0x26, 0x02,              # ROL $02
    0xA5, 0x02,              # LDA $02
    0xC9, 0xA5,              # CMP #$A5
    0xD0, 0xF5,              # BNE WS1
    0x60,                    # RTS
    # $0343  RBYTE: 8 bits, MSB first
    0xA9, 0x00,              # LDA #0
    0x85, 0x02,              # STA $02
    0xA9, 0x08,              # LDA #8
    0x85, 0x03,              # STA $03
    # $034B  BLOOP
    0x20, 0x57, 0x03,        # JSR RBIT
    0x26, 0x02,              # ROL $02
    0xC6, 0x03,              # DEC $03
    0xD0, 0xF7,              # BNE BLOOP
    0xA5, 0x02,              # LDA $02
    0x60,                    # RTS
    # $0357  RBIT: time the HIGH half-cycle; carry set = '1' (long)
    0xAD, 0x60, 0xC0,        # LDA $C060
    0x10, 0xFB,              # BPL RBIT        ; wait for HIGH
    0xA2, 0x00,              # LDX #0
    # $035E  RCNT (~9 cycles per pass)
    0xE8,                    # INX
    0xAD, 0x60, 0xC0,        # LDA $C060
    0x30, 0xFA,              # BMI RCNT
    0xE0, 0x0A,              # CPX #10         ; ~7 = '0', ~14 = '1'
    0x60,                    # RTS
    # $0367  ROWLO
    0x00, 0x80, 0x00, 0x80, 0x00, 0x80, 0x00, 0x80,
    0x28, 0xA8, 0x28, 0xA8, 0x28, 0xA8, 0x28, 0xA8,
    0x50, 0xD0, 0x50, 0xD0, 0x50, 0xD0, 0x50, 0xD0,
    # $037F  ROWHI
    0x04, 0x04, 0x05, 0x05, 0x06, 0x06, 0x07, 0x07,
    0x04, 0x04, 0x05, 0x05, 0x06, 0x06, 0x07, 0x07,
    0x04, 0x04, 0x05, 0x05, 0x06, 0x06, 0x07, 0x07,
])

# Sanity-check the label addresses the hand assembly relies on
for addr, opcode in [(0x0333, 0xA9), (0x0337, 0x20), (0x0343, 0xA9),
                     (0x034B, 0x20), (0x0357, 0xAD), (0x035E, 0xE8)]:
    assert ML[addr - 0x0300] == opcode, f"label at ${addr:04X} is off"
assert len(ML) == 0x97

if __name__ == "__main__":
    lines = [
        (5, "REM SCREEN MIRROR RECEIVER"),
        (10, f"FOR I=0 TO {len(ML) - 1}: READ V: POKE 768+I,V: NEXT"),
        (20, "CALL 768"),
    ]
    new, _ = data_lines(ML, 100)
    lines += new
    print(f"6502 receiver: {len(ML)} bytes at $0300-${0x0300 + len(ML) - 1:04X}")
    write_basic_tape(lines, "mirror_receiver.wav")
    print("After RUN the screen goes to GR and waits. Then start stream_mac.py.")
