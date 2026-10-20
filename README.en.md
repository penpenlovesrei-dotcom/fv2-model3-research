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
- [The stage table and the training stage](#the-stage-table-and-the-training-stage)
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

## The stage table and the training stage

Measured 2026-10-20 on the arcade program image and on the Dreamcast version's
`1ST_READ.BIN`, by searching for references to the stage name pointers. This
table is documented nowhere else.

**27 records of `0x70` bytes**, in the order of the name list, and both
versions keep it in the same logical place:

| | arcade | Dreamcast |
|---|---|---|
| table | RAM `0x00075170` | file `0x0010763C` |
| names | `0x000887D9` | `0x000CD1D4` |
| load base | 0 | `0x8C010000` |

The names are the same on both sides, in the same order: `TEST`, `WESTERN`,
`AC_CARRIER`, `ROOM_00`, `GREAT_BM`, `FURNACE`, `STORE`, `HANGAR`, `CAPSULE`,
`DAM`, `TOWER`, `BUILDING`, `MUSEUM`, then `FINISH00` to `FINISH05`, the seven
`ADV_*` of the attract mode, and `SELECT`.

### The fields

```
+0x00  pointer to the name
+0x04  pointer to a byte list, shared between several stages
+0x08  pointer to the resource list — 8 identifiers, see below
+0x0C ) up to three code pointers (arcade: 0x00018424-0x00018CC4).
+0x10 ) TEST has none, WESTERN two, TOWER and BUILDING use +0x0C.
+0x18 ) Candidates for the interactive and destructible objects.
+0x1C  pointer to byte lists (arcade 0x001154B0-0x001155CE)
+0x20  pointer to a 0x1F8-byte block, one per stage, in order
+0x24  identical for all 27: a shared block
+0x28  identical for all 27: the same one
+0x2C  5.0f, identical for all 27
+0x30..+0x48  camera floats (distances and limits)
+0x4C..+0x54  small floats, often zero
+0x58  0.0040833f, identical for all 27
+0x5C  colour pairs, highly variable
+0x60  an index (0x27-0x3A) in the high half, 0xFF in the low — role unestablished
+0x64  ARGB: fog or ambient (TEST: 0xFFAA0000, unique)
+0x68  0x000001FF, or 0x010001FF for TOWER and BUILDING
+0x6C  3, identical for all 27
```

The `0x1F8`-byte block at `+0x20` holds a family of normalised plane triplets
(±0.05, ±1.083, ±0.05): collision or cage, **not proven**.

### The field that decides: `+0x08`

The list of 8 identifiers it points at has the stage's **own geometry** as its
fourth entry. That is where — and only where — the two versions diverge:

| stage | arcade | Dreamcast |
|---|---|---|
| **TEST** | **`0x00000000` — empty** | **`0x001800F0` — index 0x18** |
| WESTERN | `0x00A01001` | `0x000100F0` |
| FURNACE | `0x00A01002` | `0x000200F0` |
| AC_CARRIER | `0x00A01003` | `0x000300F0` |
| CAPSULE | `0x00A01004` | `0x000400F0` |
| HANGAR | `0x00A01005` | `0x000500F0` |
| MUSEUM | `0x00A0100A` | `0x000A00F0` |
| BUILDING | `0x00A0100B` | `0x000B00F0` |
| ROOM_00 | `0x00A0100C` | `0x000C00F0` |
| STORE | `0x00A0100D` | `0x000D00F0` |
| DAM | `0x00A0100E` | `0x000E00F0` |
| TOWER | `0x00A01010` | `0x001000F0` |
| GREAT_BM | `0x00A01012` | `0x001200F0` |

The twelve fighting stages carry the same index on both sides. The kinds map
one to one: arcade `0xA0/0x10` ↔ Dreamcast `0x00F0` (stage geometry),
`0xA0/0x2E` ↔ `0x03A9`, `0xA0/0x2F` ↔ `0x04A9`, `0xA1/0x0B` ↔ `0x00FF`.

And the full enumeration of the stage-geometry kind reads in the clear in both
images:

- arcade `0x000EC048`: `00A01000` … `00A01013`, **20 slots (0x00–0x13)**
- Dreamcast `0x00102420`: `000000F0` … `001800F0`, **25 slots (0x00–0x18)**

**`TEST` is the training stage, and its geometry exists only on Dreamcast.**
The console added slots 0x14 to 0x18 and pointed `TEST` at the last of the five
— the signature of a late addition, consistent with the rest of what exists
only on console (`EMI` at index 11 in place of `TECHNO` and `DURAL`, Kuhn's
unlock completed).

The arcade carries **everything else** about the stage: its name, the whole
record, its camera parameters, its own fog colour, its `0x1F8` block. Only the
geometry resource is missing. And its own kind has eight enumerated, unused
slots — 0, 6, 7, 8, 9, 0xF, 0x11, 0x13.

### Two lessons in method

**A name table says nothing about content.** Both versions' name lists are
identical name for name, which at first led to the conclusion that no stage was
exclusive. That is wrong: a name list enumerates the slots that were
*planned*, filled or empty. Each record has to be followed through to its
payload.

**Resource identifiers are not addresses.** The `0x00A0xxxx` values, walked as
Real3D models with `model3d.py`, fail at the very first polygon on the face
normal's magnitude. They are `(kind, index)` identifiers, resolved by code that
has not yet been found.

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
| `build_crom.py` | reinterleave the zip's ROMs into CROM and VROM, and split a patched CROM back into EPROMs |
| `decors.py` | the stage table of both versions, and what separates them |
| `model3d.py` | walk a Real3D model out of the VROM, and tell whether an address is one |
| `cdi.py` | open the Dreamcast image and extract its files |
| `afs.py` | read the Dreamcast version's AFS archives |
| `nuage.py` | render a point cloud of the Dreamcast models, with no decoder |

Four `.cmd` launchers chain what is needed, with no command line to retype:
**Reconstruire les ROM arcade**, **Ouvrir le disque Dreamcast**,
**Table des décors**, **Profil des modèles Dreamcast**. The default paths to
the MAME zip and the Dreamcast image are overridden by the `FV2_ZIP` and
`FV2_CDI` environment variables.

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

**Resolving a resource identifier.** A stage names its geometry by a
`(kind, index)` pair, and the kind's enumeration reads in the clear in both
versions — but the code that turns that pair into data has not been found.
That is the only lock left on the training stage: it would tell which entry of
`MDL_DAT.AFS` carries index 0x18.

**The model format of `MDL_DAT.AFS`.** A record begins with four PowerVR2 Tile
Accelerator parameter words baked into the file (Parameter Control, ISP/TSP,
TSP, Texture Control), followed by a bounding box, counters and blocks of
floats. The Texture Control's address field is 0: it is filled in at load
time, which is why the entries of `TEX_DAT.AFS` carry no `PVRT` or `GBIX`
header. The texture format itself is documented elsewhere: `celsowm/vf3-decomp`,
`docs/formats/TEX.md` — no header, little-endian RGB565, PVR twiddle by tiles.
Size and format read out of the model's own words: TSP bits 0-5 for U and V,
Texture Control bits 30-27 for the format.

**The role of the stage table's `+0x60` and `+0x68` fields**, and proof that
the `0x1F8`-byte block really carries the collision.

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
