"""Read Model 3 RAM out of a running Supermodel.exe via the static pointer.

The 8MB RAM base lives at Supermodel.exe+0x65D098 (build 0.3a-20251120 x64,
md5 f2dfe94e9038c1dc51d6a7530db83e3d). RAM is stored byte-reversed inside
each 32-bit word, so reads are word-swapped back to big-endian PowerPC.

Usage:
    python mem.py verify                 sanity-check the pointer
    python mem.py dump <out.bin>         snapshot all 8MB (PPC address == file offset)
    python mem.py read <addr> [len]      hexdump at a PowerPC address
    python mem.py write <addr> <hex>     patch bytes at a PowerPC address

Writes save the previous bytes to undo_<addr>.txt so a patch can be rolled
back without restarting the emulator.
"""

import ctypes as C
import ctypes.wintypes as W
import sys

RAM_PTR_RVA = 0x65D098
RAM_SIZE = 0x800000

k32 = C.WinDLL("kernel32", use_last_error=True)
psapi = C.WinDLL("psapi")


def swap32(b):
    n = len(b) & ~3
    o = bytearray(b[:n])
    o[0::4], o[1::4], o[2::4], o[3::4] = b[3:n:4], b[2:n:4], b[1:n:4], b[0:n:4]
    return bytes(o)


ACCESS = 0x0438  # QUERY_INFORMATION | VM_OPERATION | VM_READ | VM_WRITE


def attach(name="supermodel.exe"):
    arr = (W.DWORD * 4096)()
    got = W.DWORD()
    psapi.EnumProcesses(C.byref(arr), C.sizeof(arr), C.byref(got))
    buf = C.create_unicode_buffer(512)
    for pid in arr[: got.value // 4]:
        h = k32.OpenProcess(ACCESS, False, pid)
        if not h:
            continue
        if psapi.GetModuleBaseNameW(h, None, buf, 512) and buf.value.lower() == name:
            mods = (C.c_void_p * 512)()
            need = W.DWORD()
            psapi.EnumProcessModulesEx(h, C.byref(mods), C.sizeof(mods), C.byref(need), 3)
            return h, pid, mods[0]
        k32.CloseHandle(h)
    sys.exit("Supermodel.exe is not running")


h, pid, mod = attach()


def read(addr, size):
    buf = (C.c_char * size)()
    got = C.c_size_t()
    if not k32.ReadProcessMemory(h, C.c_void_p(addr), buf, size, C.byref(got)):
        return b""
    return buf.raw[: got.value]


ram_base = int.from_bytes(read(mod + RAM_PTR_RVA, 8), "little")


def ppc(a, n):
    """Read n PowerPC-ordered bytes at address a (any length/alignment)."""
    start = a & ~3
    end = (a + n + 3) & ~3
    return swap32(read(ram_base + start, end - start))[a - start: a - start + n]

def write_ppc(addr, data):
    """Patch PowerPC-ordered bytes, honouring the 32-bit word swap."""
    start = addr & ~3
    end = (addr + len(data) + 3) & ~3
    cur = swap32(read(ram_base + start, end - start))
    buf = bytearray(cur)
    buf[addr - start: addr - start + len(data)] = data
    out = swap32(bytes(buf))
    n = C.c_size_t()
    ok = k32.WriteProcessMemory(h, C.c_void_p(ram_base + start),
                                out, len(out), C.byref(n))
    return bool(ok), cur[addr - start: addr - start + len(data)]


cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"

if cmd == "verify":
    print(f"pid={pid} module={mod:#x} ram={ram_base:#x} (rva {RAM_PTR_RVA:#x})")
    for a, want in ((0x88A5C, b"MAIN_MENU"), (0xB1758, b"KUMA"), (0x882B4, b"SPD")):
        got = ppc(a, 0x10)
        print(f"  {a:#08x}: {got[:12]!r}  {'OK' if want in got else 'MISMATCH'}")
elif cmd == "dump":
    open(sys.argv[2], "wb").write(ppc(0, RAM_SIZE))
    print(f"wrote {sys.argv[2]} ({RAM_SIZE:#x} bytes, PPC address == file offset)")
elif cmd == "write":
    addr = int(sys.argv[2], 16)
    data = bytes.fromhex(sys.argv[3])
    ok, old = write_ppc(addr, data)
    print(f"{addr:#08x}: {old.hex(' ')} -> {data.hex(' ')}  {'ok' if ok else 'FAILED'}")
elif cmd == "freeze":
    # hold values against the game's own writes, the way ArtMoney's freeze does
    import time
    pairs = [(int(a, 16), bytes.fromhex(v)) for a, v in
             (p.split("=") for p in sys.argv[2].split(","))]
    secs = float(sys.argv[3]) if len(sys.argv) > 3 else 20.0
    for a, v in pairs:
        print(f"  freezing {a:#08x} = {v.hex(' ')}")
    end = time.time() + secs
    n = 0
    while time.time() < end:
        for a, v in pairs:
            write_ppc(a, v)
        n += 1
        time.sleep(0.005)
    print(f"held for {secs}s ({n} passes); values now:")
    for a, v in pairs:
        print(f"  {a:#08x} = {ppc(a, len(v)).hex(' ')}")
elif cmd == "read":
    a = int(sys.argv[2], 16)
    n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x40
    d = ppc(a, n)
    for i in range(0, len(d), 16):
        row = d[i:i + 16]
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in row)
        print(f"{a + i:08X}  {row.hex(' '):<47}  {txt}")

k32.CloseHandle(h)
