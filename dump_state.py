"""List and extract blocks from a Supermodel save state.

Each block is laid out as:
    uint32 nextBlockOffset, uint32 nameLength, uint32 commentLength,
    char name[], char comment[], byte data[]
The nextBlockOffset chain is not reliable to walk here, so blocks are
located by their comment marker instead - every block Supermodel writes
carries its source file path ("Src/.../Foo.cpp") right after the name.

Usage:
    python dump_state.py <state.st0>                  list blocks
    python dump_state.py <state.st0> <substring>      also extract matches
"""

import re
import struct
import sys
import pathlib

path = pathlib.Path(sys.argv[1])
want = sys.argv[2].lower() if len(sys.argv) > 2 else None
d = path.read_bytes()

# every block's comment is its source path; the name sits just before it
marks = []
for m in re.finditer(rb"Src/[A-Za-z0-9_/]+\.cpp\x00", d):
    pre = d[max(0, m.start() - 64): m.start()]
    names = re.findall(rb"[ -~]{2,48}\x00", pre)
    if not names:
        continue
    name_end = m.start()
    name_start = name_end - len(names[-1])
    hdr = name_start - 12
    if hdr < 0:
        continue
    _, nlen, clen = struct.unpack_from("<III", d, hdr)
    marks.append((names[-1][:-1].decode(), hdr, name_start + nlen + clen))

print(f"{path.name}: {len(marks)} blocs")
for i, (name, hdr, data_off) in enumerate(marks):
    end = marks[i + 1][1] if i + 1 < len(marks) else len(d)
    size = end - data_off
    note = ""
    if want and want in name.lower():
        out = path.parent.parent / "fv2mod" / (
            re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower() + ".bin")
        out.write_bytes(d[data_off: end])
        note = f"  -> {out.name}"
    print(f"  {name:<22} off={data_off:#010x} len={size:#x} "
          f"({size / 1024:.0f} KiB){note}")
