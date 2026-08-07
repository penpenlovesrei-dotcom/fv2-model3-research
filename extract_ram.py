"""Extract the PowerPC main RAM image from a Supermodel save state.

Supermodel keeps Model 3 main RAM byte-reversed within each 32-bit word,
so the raw block has to be word-swapped to read as big-endian PowerPC.
The RAM's offset inside the "Model 3" block is found by evidence: we slide
the swap phase / base until known ASCII reads correctly.

Usage: python extract_ram.py <state.st0> [out.bin]
"""

import struct
import sys
import pathlib

RAM_SIZE = 0x800000

# The "Model 3" block opens with 16 bytes of misc machine state; RAM follows.
# Confirmed against the live process: with this offset, file offset == PPC
# address and the TCRF addresses land exactly.
RAM_OFF_IN_BLOCK = 0x10

EXPECTED = {"MAIN_MENU": 0x88A5C, "SPD: %8f": 0x882B4, "KUMA": 0xB1758}


def blocks(d):
    pos = 0
    while pos + 12 <= len(d):
        nxt, nlen, clen = struct.unpack_from("<III", d, pos)
        name = d[pos + 12: pos + 12 + nlen].split(b"\0")[0].decode("latin1")
        off = pos + 12 + nlen + clen
        end = nxt if pos < nxt < len(d) else len(d)
        yield name, off, end - off
        if not (pos < nxt < len(d)):
            return
        pos = nxt


def swap32(b):
    n = len(b) & ~3
    out = bytearray(b[:n])
    out[0::4], out[1::4], out[2::4], out[3::4] = b[3:n:4], b[2:n:4], b[1:n:4], b[0:n:4]
    return bytes(out)


path = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else path.parent / "fv2_ram.bin"
d = path.read_bytes()

blk = next((o, l) for n, o, l in blocks(d) if n == "Model 3")
off, length = blk
print(f'"Model 3" block: off={off:#x} len={length:#x}')

ram = swap32(d[off + RAM_OFF_IN_BLOCK: off + RAM_OFF_IN_BLOCK + RAM_SIZE])
out.write_bytes(ram)
print(f"RAM at block+{RAM_OFF_IN_BLOCK:#x} -> {out.name} ({len(ram):#x} bytes)")

# cross-check against the addresses The Cutting Room Floor documents
for name, addr in EXPECTED.items():
    got = ram[addr: addr + len(name)]
    print(f"  {addr:#08x} {name:16} {'OK' if got == name.encode() else f'MISMATCH {got!r}'}")
