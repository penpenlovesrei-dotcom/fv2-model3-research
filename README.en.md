# Fighting Vipers 2 (Sega Model 3) — reverse engineering notes

Findings on the **arcade** version of *Fighting Vipers 2* (Sega Model 3,
Step 2.0, 1998), obtained under the
[Supermodel](https://github.com/trzy/Supermodel) emulator, together with the
tools used to establish them.

Most of what follows appears neither on The Cutting Room Floor, nor in cheat
databases, nor in the Dreamcast guides.

---

## Contents

- [Starting point: a compressed program](#starting-point-a-compressed-program)
- [Main finding: the unlock Sega designed](#main-finding-the-unlock-sega-designed)
- [The real roster](#the-real-roster)
- [Unlocking the whole roster](#unlocking-the-whole-roster-one-and-a-half-bytes)
- [Playing in English](#playing-in-english)
- [Survival mode](#survival-mode)
- [Tools](#tools)
- [Open questions](#open-questions)
- [Scope and limits](#scope-and-limits)

---

## Starting point: a compressed program

The obvious first move — deinterleave the ROMs and look for PowerPC code —
yields nothing. The *Fighting Vipers 2* CROM contains no readable strings and
no usable code beyond a short boot stub.

**The program is compressed and decompressed into RAM at startup** — and the
format is **gzip**, not LZSS.

> **Corrected 2026-08-22.** These notes long said "LZSS", on the strength of
> the internal test menu's `LZSS_INFO` entry. Sega's label does not describe
> the algorithm. The CROM opens, at offset 0, with a **complete gzip file**:
> magic `1f 8b`, method 8 (deflate), original filename `foo.bin`, compressed
> on **1998-03-26 at 16:01:08 UTC** on a Unix system. 897,285 bytes yielding
> 2,701,982.
>
> Three concordant checks: DEFLATE's canonical tables sit in the boot stub as
> 16-bit big-endian words (`cplens` `0xFFF03604`, `cplext` `0xFFF03642`,
> `cpdist` `0xFFF03680`) and the decompressor is zlib's `huft_build`;
> `zlib.decompressobj(-15)` runs the whole stream and **the gzip trailer's
> CRC32 matches**; the result lands in **RAM at address 0**, identical to
> 99.9% against a RAM capture taken mid-game.

Two practical consequences shape everything that follows:

1. The object to analyse is the **decompressed image**, not the raw ROM.
   Loaded into a disassembler as big-endian PowerPC at base 0, it yields
   readable code — and the addresses documented by The Cutting Room Floor land
   exactly. It can come from a RAM capture or straight from the zip.
2. **A permanent ROM patch is possible.** Nothing needs reversing: decompress,
   edit, recompress with the standard library. The original gzip is 897,285
   bytes; Python at level 9 produces 882,022 for the same content — **15,263
   bytes of headroom**, so a patch fits in place. One step remains:
   re-interleaving the CROM across the four EPROMs to rebuild a playable zip.

### Getting the RAM image

Two routes, one offline and one live. In both cases RAM is stored with
**32-bit words byte-reversed**: a 32-bit byte swap is required to read it
back as big-endian PowerPC.

**From a Supermodel save state** (CBlockFile format): each block opens with
three little-endian 32-bit integers — next block offset, name length, comment
length — followed by the name, the comment, then the data. The block of
interest is `"Model 3"`, and **RAM starts at offset `0x10` within the block**,
not at its beginning. With that shift, file offset equals PowerPC address.

**From the running process**: build `0.3a-20251120` x64 keeps a pointer to the
RAM base at `Supermodel.exe + 0x65D098`. Note that Supermodel **reallocates
its memory pool after ROM loading** — a tool that reads this pointer once at
startup gets a stale base and writes into nothing, with no error reported.

---

## Main finding: the unlock Sega designed

*Fighting Vipers 2* contains a complete progressive unlock mechanism for its
hidden characters, never documented for the arcade version.

### The input

On the character select screen, player 1's cursor on **Emi** (the first slot):

> **push up, hold, then roll to the up-left diagonal**

An equivalent second entry point exists from **slot 10** — the empty slot at
the end of the row — using up then up-right.

The input only works **early in the select screen countdown**: the code
requires the timer to still be above a threshold.

The "button" in the code is in fact a **direction**. That is why it stayed
invisible: on a keyboard, holding up while pressing left as two separate keys
does not come to mind, and the motion only makes sense on a stick. It is also
why it never confirms a character in passing.

### Three-stage progression

The cursor movement code has three branches, selected by two progression
flags:

| State | Row reachable | The input gives |
|---|---|---|
| initial | 0–10 | **Del Sol** |
| first flag set | 0–11 | nothing — Del Sol is acquired |
| both flags set | 0–11 | **Kuhn** |

Once unlocked, **Del Sol becomes a permanent slot**, reached by wrapping left
from Emi. **Kuhn never does**: the wrap bound rises from 10 to 11 but never
to 12. Kuhn therefore briefly occupies Emi's slot and vanishes as soon as the
cursor moves — transient by design, to be re-triggered every time.

A **one-shot latch** disables the whole secret block once an input has
succeeded, preventing a second unlock in the same session.

### The Kuhn unlock is orphaned on arcade

The flag that opens the third stage is **written nowhere in the ROM**:
analysis finds a single reference to it, a read, from the cursor code. The
branch exists; no gameplay path activates it.

This is very likely why no Kuhn code was ever documented on arcade hardware:
there isn't one. The first flag, by contrast, is written, under a threshold
condition on a counter.

On **Dreamcast** the unlock is complete and documented: beating Mahler on
stage 7 within a time limit with enough health, or via a Super K.O., opens a
bonus stage where defeating Kuhn unlocks him. The simplest hypothesis is that
Sega finished this system for the console port, leaving the arcade version
half-wired.

### Addresses

| Purpose | Address |
|---|---|
| Select cursor, player 1 | `0x00279668` |
| Select cursor, player 2 | `0x00279669` |
| Secret-code latch | `0x00279691` |
| "Del Sol acquired" flag | `0x0011F061` |
| "Kuhn available" flag | `0x0011F06F` |
| Flag disabling the secret block | `0x0011F060` |
| Select screen countdown | `0x00581408` |
| Cursor movement handler | `0x0005F340` |

The displayed countdown derives from the halfword at `0x0058140A` shifted
right by 6. Topping it up to something below 99 once displayed removes the
time pressure — but **never freeze it**: the game decrements it itself, and
pinning it stalls screen transitions.

---

## The real roster

The game uses **two distinct numbering schemes**, a persistent source of
confusion.

**Cursor position** on the select screen: Emi 0, Bahn 1, Picky 2, Jane 3, and
so on. Slot 10 is a random-select slot with no character. Del Sol, Kuhn and
BM sit at 11, 12 and 13.

**In-match character ID**, readable at `0x007005B8` for player 1 and
`0x007075B8` for player 2, following an internal string list:

| | | | |
|---|---|---|---|
| 0 Grace | 1 Bahn | 2 Raxel | 3 Tokio |
| 4 Sanman | 5 Jane | 6 Honey | 7 Picky |
| 8 Mahler | 9 BM | 10 Charlie | 11 Techno |
| 12 Dural | 13 Kuhn | 14 Del Sol | **15 Kuma** |

Conversion between the two goes through a 15-byte table at `0x000B16B8`.

Two takeaways:

**ID 15 is Kuma**, the bonus-stage bear — playable by forcing the ID, though
plainly never intended to be. ID 16 hangs the game: the fighter list ends
there, later entries being animation names.

**Dural is Kuhn's former name.** IDs 12 and 13 load the same character. Kuhn
being the series' copycat android, he most likely carried the name of the
*Virtua Fighter* boss during development before being renamed — both entries
survived.

**BM has no displayable name**: his entry in the text-ID table is null. Sega
never assigned him one, consistent with a character never meant to be
selectable.

---

## Unlocking the whole roster: one and a half bytes

The cursor handler has an "extended roster" mode where the cursor wraps at 14
instead of 10 — making Del Sol, Kuhn, BM and Kuma all reachable with the
d-pad, and **permanent**.

That mode is gated on both **operator buttons** (Service and Test) being held.
Unusable by hand, since Test opens the service menu. The variable tested is
not a progression flag but the **raw hardware input port state**, refreshed
every frame: writing to it achieves nothing.

The comparison itself, however, can be patched:

```
0x0005F3BC :  2C 80 00 C0   (cmpwi r0,192)
           →  2C 80 00 00   (cmpwi r0,0)
```

The condition becomes true when no operator button is pressed — that is,
permanently.

**Two mandatory precautions.** The game reloads this code section, so the
patch must be reapplied — but **only after re-reading the original
instruction at the target address**. Writing blindly during startup corrupts
a region not yet decompressed and derails the emulated CPU.

Known limitation: beyond index 10, names and portraits are wrong or missing.
The drawing routine refuses to draw past that point, and its position table
holds only 11 entries.

---

## Playing in English

The available ROM is the Japanese revision. The test menu does show a
`COUNTRY` setting, but **read-only** — unlike the other settings on the same
page, which edit normally.

The lock is in the menu UI, not in game logic. Region is a single byte:

```
0x00120557 :  0 = Japan   1 = U.S.A.   2 = Export   3 = Asia
```

Writing it works, the game does not overwrite it, and text switches to
English. A warning screen absent from the Japanese version then appears —
evidence of a genuine region change rather than a relabelling.

The NVRAM save does not contain this setting in any directly recognisable
form; making it permanent outside the emulator would require decoding the
backup RAM layout.

---

## Survival mode

Writing 1 to **`0x0058145F`** (with the corresponding setting at 1 in
`0x00120550`) switches the game into Survival mode — the label appears at the
top left of the screen.

There is no distinct **Versus** mode: in *Fighting Vipers 2* it is arcade mode
with a second player joining in. There is no **Training** mode.

### The debug menu, a goldmine

The game retains Sega's internal test menu tables, where each entry pairs a
label with the address of its variable. This is the **developers' own
documentation**, left in the ROM: their names for energy, round timers, bonus
stage flags, character IDs and display settings come for free, with nothing to
guess.

Entry layout, `0x20` bytes long: label pointer first, variable address at
offset `0x0C`, type at offset `0x1C`. When the high byte of the type is
`0x10`, the field at `0x0C` is an index rather than an address.

The bundled `symbols.csv` lists 84 symbols, 56 of them from these tables.

---

## Tools

Python scripts, no dependencies, for Windows.

| File | Purpose |
|---|---|
| `mem.py` | read and write Model 3 RAM in the running process |
| `play.py` | launch the game forcing a character and/or region |
| `roster.py` | apply and maintain the full-roster unlock |
| `extract_ram.py` | extract the RAM image from a save state |
| `dump_state.py` | list and extract save state blocks |
| `symbols.py` | rebuild the symbol map from the RAM image |
| `gzip_crom.py` | extract and reinject the program, which is a gzip file |
| `displaylist.py` | decode the display list: which elements are drawn |
| `dl_watch.py` | watch graphic elements continuously |

`symbols.csv` can be reapplied to a Ghidra project to recover original names
instead of auto-generated labels.

---

## Open questions

**What sets the first progression flag in normal play.** The code gates it on
a threshold over a counter whose meaning is not established. The Dreamcast
conditions — stage 7 time, health remaining, Super K.O. — are a plausible but
unverified lead.

**Screen dispatch.** Three avenues were explored without success: no function
pointer table for screens exists; the screen functions have no direct callers,
so they are reached through computed addresses; and searching for a state
variable by comparing four save states taken on four different screens
produced nothing convincing. Progress requires **observing execution flow**,
which the public Supermodel build does not allow — its debugger is a compile
time option absent from distributed binaries.

**Adding elements on screen.** The drawing API is understood: a routine pushes
packets into a display list, drawing from an element table, and each element
ID is an immediate constant just before the call — hence substitutable. But
substituting is not adding: a menu would require injecting code.

---

## Scope and limits

These notes cover the Japanese revision `fvipers2` as recognised by
Supermodel. The addresses quoted are **RAM** addresses, valid once the program
is decompressed. They are found unchanged in the image pulled from the CROM's
gzip, which is what makes a permanent patch possible.

This repository contains **no decompiler output**: mechanisms are described,
not transcribed. Addresses, values and behaviours are documentation, in the
spirit of preservation projects.

No game data is distributed here. The tools assume you already have your own
copy and a Supermodel installation.
