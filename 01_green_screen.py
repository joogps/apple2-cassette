#!/usr/bin/env python3
"""Fill the Apple II lo-res screen with light green.  Output: green_screen.wav"""

from apple2tape import write_basic_tape

LINES = [
    (10, "GR: POKE -16302,0"),                      # lo-res, full screen
    (20, "FOR I=1024 TO 2047: POKE I,204: NEXT"),   # $CC = green in both nibbles
    (30, "GOTO 30"),
]

if __name__ == "__main__":
    write_basic_tape(LINES, "green_screen.wav")
