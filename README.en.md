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
- [Resolving resource identifiers](#resolving-resource-identifiers)
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

The list of 8 identifiers it points to is **entirely audio**. Its fourth slot
carries the stage's **music**, and that is the one and only place the two
versions diverge:

| stage | arcade | Dreamcast |
|---|---|---|
| **TEST** | **`0x00000000` — empty** | **`0x001800F0` — index 24** |
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

The twelve fight stages carry the same index on both sides. The genre's full
enumeration is in plain sight in both images:

- arcade `0x000EC048`: `00A01000` … `00A01013`, **20 slots (0–19)**
- Dreamcast `0x00102420`: `000000F0` … `001800F0`, **25 slots (0–24)**

So the Dreamcast **added five tracks**, and `TEST` points at the last of the
five. The list's first three slots are identical across all 27 records — shared
effect banks — and slots 4 and 5 are a stage-specific effect pair, null for
`TEST`.

**`TEST` is the training stage, and it exists only on Dreamcast.** Consistent
with everything else that is console-only: `EMI` at index 11 in place of
`TECHNO` and `DURAL`, Kuhn's unlock completed.

The arcade carries **everything else** about the stage: its name, its whole
record, its camera parameters, its fog colour, its `0x1F8` block.

---

## Resolving resource identifiers

The hard part of this project. Ghidra saw nothing: only 32.4% of the binary is
disassembled, no function referenced these tables, and the stage table is
pointed to by **no literal at all**. The answer came from a byte scan, which
doesn't try to prove something is code — it just reads it.

### The layout, and the mistake it cost

A resource identifier reads as **three fields**, not two:

```
 31                    16 15        8 7         0
+------------------------+-----------+-----------+
|         index          | sub-genre |   genre   |
+------------------------+-----------+-----------+
```

The music enumeration is perfectly regular — `000000F0`, `000100F0`, …
`001800F0` — which yields a very convincing 16/16 split that is **wrong**. It
holds as long as the sub-genre is 0, and it collapses at `0x000803A9` and
`0x000604A9`: those are not two neighbouring genres but **one**, `0xA9`, with
sub-genres 3 and 4.

What settles it is not the table's regularity. It's the dispatcher.

### The dispatcher: `0x8C047C9E`

One argument, the identifier. It extracts the low byte and compares:

```
extu.b r11,r0        ; r0 = id & 0xFF
cmp/eq #0xA9   ->  0x8C047CCA
cmp/eq #0xFF   ->  0x8C047D44
cmp/eq #0xF0   ->  0x8C047E54
else               0x8C047E68   (nothing)
```

Three genres, and only three.

**Genre `0xF0` — music.** The branch does `shlr16` then `extu.b`: the index is
indeed at the top. It reaches `0x8C0479E8`, which reserves 284,868 bytes, zeroes
a volume float, and reads partition **4** — `adx_dat.afs`. All 13 indices used
by the stage table are valid **CRI ADX** streams, 44,100 Hz stereo, with the
`(c)CRI` marker in place. The training stage's, index 24, is the longest in the
archive: 11.97 MB.

**Genre `0xA9` — sound effects.** Mask `0x0000FF00` then `shlr8`: it's the
sub-genre that is used. The branch reaches `0x8C0C1D20`, which writes the
identifier into a ring from `0xA0800400` to `0xA0800500`, wrapping back to the
start. That is **AICA** RAM over the G2 bus — a command queue to the sound
processor.

**Genre `0xFF`.** A chain of `cmp/eq` on `id & 0x00FF00FF`, written by hand,
one case per index.

### The file system is CRI's

The five archives are **ADXF partitions** — CRI's file system. "AFS" stands for
*ADX File System*. The library leaves its function names in its error messages,
which names the whole layer at once:

| | |
|---|---|
| `ADXF_LoadPartition` | `0x8C12BA6A` |
| `ADXF_Open` | `0x8C12BE4E` |
| `ADXF_GetFileRange` | `0x8C12C5E0` |
| partition table | `0x8C3DE0B8`, 256 pointers indexed by `ptid` |
| file count | `+0x0C` of the partition descriptor |

Versions present: `ADXF Ver.5.55 Build:Sep 08 1999` and
`ADXT Ver.5.76 Build:Jan 28 2000`.

Registration happens in one loop, at `0x8C028988`, which copies two five-word
arrays to the stack and then calls `ADXF_LoadPartition` five times. The two
arrays:

| `ptid` | name, `0x8C0CD278` | usable entries, `0x8C0CD28C` | measured in the archive |
|---|---|---|---|
| 0 | `mot_dat.afs` | 1 | — |
| 1 | `mdl_dat.afs` | 77 | 78 entries |
| 2 | `tex_dat.afs` | 114 | 115 entries |
| 3 | `snd_dat.afs` | 35 | — |
| 4 | `adx_dat.afs` | 25 | 26 entries |

The off-by-one is not an error: **the last entry of every archive is a
zero-length terminator.** Verified on all three readable archives. So
`mdl_dat` holds 77 usable entries, 0 to 76, and the training stage's entry 75
is comfortably inside.

Four near-identical functions each read one partition, and the immediate loaded
into `r4` names them:

| call site | `ptid` | archive |
|---|---|---|
| `0x8C029B2E` | 0 | `mot_dat` |
| `0x8C02A750` | **1** | **`mdl_dat`** (function `0x8C02A5A8`) |
| `0x8C02B6BA` | **2** | **`tex_dat`** |
| `0x8C0474FA` | 3 | `snd_dat` |

Sega also left the table's debug dump in: the format string
`"%2d:%d %08X %08X %4d [%s]\n"` at `0x8C0CD544`, loaded by the instruction at
`0x8C02BA9A`, with `"File Open Error"` just above it.

### Which entry holds which stage, measured before it was read

The code doesn't say, so it was measured. `retrouver.py` finds one emulator-
dumped texture among the disc's 3,709 by signature; a single texture doesn't
settle it, because a sky or a floor serves several stages and lands at distance
0.0 in two entries. So `decor_vers_entree.py` makes **a whole dump folder
vote**: each image votes for every source where it is found at the minimum
distance, and the entry that holds the stage takes the votes.

| dump | MDL entry | TEX entry | votes | likely internal name |
|---|---|---|---|---|
| Great Museum | **55** | 78 | 50 / 50 | `MUSEUM` |
| Serpent's Cage | **68** | 100 | 19 / 19 | `CAPSULE` |
| Hanger of the Dark Royal | **39** | 62 | 17 / 17 | `HANGAR` |
| Training Zone | **75** | 112 | 7 / 7 | `TEST` |
| Deck of the Dark Royal | **0** | 0 | 7 / 7 | `AC_CARRIER` |
| Terror Furnace | **34** | 56 | 3 / 3 | `FURNACE` |
| Cross River Damsite | **26** | 33 | 2 against 1 | `DAM` |
| The Great B.M | **33** | 55 | 1 | `GREAT_BM` |
| Old Armstone Town | **76** | 113 | 1 | `WESTERN` |

The first five rows are unanimous with no rival. The training stage comes out at
MDL 75 / TEX 112 **independently** of the first measurement, which took another
route: that is what validates the method. The last three rows rest on one or two
images — plausible, not established.

The "internal name" column is a reading, not a measurement: the binary carries
only the internal names (`0x8C0DD1D4`, twelve bytes per slot, in the stage
table's order), and the display names are textures.

**So the stages are not entries 0 to 15**, as I had assumed. They are scattered:
0, 26, 33, 34, 39, 55, 68, 75, 76.

An independent cross-check: an MDL entry's header carries its class at `+0x00`,
`1` for a stage and `-1` for a character. Of the 77 usable entries, 43 are of
stage class and 34 of character class — and **all nine entries found above are
of stage class**, without exception.

Four stages are missing — `ROOM_00`, `STORE`, `TOWER`, `BUILDING` — and exactly
four dumps are left without a match: Marble Arena, Neo Armstone City Tower,
Secret Chemical Plant, The Skies of Armstone. The first three have no Dreamcast
texture in the dump; the fourth has thirteen that are not on this disc: they are
arcade-version textures.

### The table that was missing: `0x8C118294`

It is in the code, and it gives the answer in plain sight. **35 records of
`0x34` bytes**, right after the stage table:

| field | content |
|---|---|
| `+0x00` u32 | entry index into `mdl_dat.afs` |
| `+0x04` u32 | entry index into `tex_dat.afs` |
| `+0x08` u32 | a size |
| `+0x0C`, `+0x10` | two pointers, `0x8C112xxx` area |
| `+0x30` u32 | `0xFFFFFFFF`, or `0xFFFF00xx` for the first thirteen |

The rank is the stage table's index, and the blocks read:

- **0 to 12**: the thirteen real stages
- **13 to 18**: `FINISH00` to `FINISH05`, i.e. MDL 28 to 33, consecutive
- **19 to 26**: the seven `ADV_*` and `SELECT` — the `_2` pairs do fall in twos
- **27 to 34**: eight scenes beyond the stage table

| rank | internal name | MDL | TEX |
|---|---|---|---|
| 0 | `TEST` | **75** | 112 |
| 1 | `WESTERN` | **76** | 113 |
| 2 | `AC_CARRIER` | **0** | 0 |
| 3 | `ROOM_00` | **60** | 89 |
| 4 | `GREAT_BM` | **35** | 58 |
| 5 | `FURNACE` | **34** | 56 |
| 6 | `STORE` | **68** | 100 |
| 7 | `HANGAR` | **39** | 62 |
| 8 | `CAPSULE` | **22** | 23 |
| 9 | `DAM` | **26** | 33 |
| 10 | `TOWER` | **74** | 111 |
| 11 | `BUILDING` | **19** | 20 |
| 12 | `MUSEUM` | **55** | 78 |

### Why it was invisible, and what made it visible

The table is reached only by computed address, and the index arrives in a RAM
variable. All twenty-five references to the slot installer (`0x8C02A2A0`) are
`COMPUTED_CALL`. Ghidra could not show them while the literals were untyped:
applying the names the byte scan had established is what closed the graph and
made the calls appear.

The chain then reads at a glance. The slot loader (`0x8C02A39E`) does
three things and nothing else: it sets a flag in a word array indexed by the
slot, calls `0x8C02985E` with the slot **plus five** — the same offset as the
resource dispatcher's `add #-5` — then hands over to the model loader. And its
caller passes it `base + index * 0x34`, where `base` is this table.

### The two measurements agree

The nine stages had been paired **beforehand**, by texture signature, without
touching the code. Seven land exactly on the diagonal rank = stage index:
`TEST` 75/112, `WESTERN` 76/113, `AC_CARRIER` 0/0, `FURNACE` 34/56,
`HANGAR` 39/62, `DAM` 26/33, `MUSEUM` 55/78.

And of the **26 MDL ↔ TEX pairs** the exact-tiling pairing covered, the game's
own table contradicts **none**. The tiling heuristic is therefore validated
across its whole domain.

Two corrections, both of them mine:

- Serpent's Cage is `STORE`, not `CAPSULE` — that was a reading of names, not a
  measurement, and it was wrong.
- My weakest result, a single image for The Great B.M, gave MDL 33. The table
  places MDL 33 at `FINISH05` and `GREAT_BM` at rank 4, so MDL 35. Yet the
  image lands at distance 0.0 on MDL 33, the next candidate at 205: this is not
  a badly broken tie, the texture really lives there. So it probably comes from
  the ending scene rather than the stage — but one image does not settle it.

**The lesson.** The measurement found the answer first, and the code then
confirmed it and corrected it where the measurement was thinnest. Neither alone
would have done: nine texture votes do not give the table's structure, and the
table alone does not say which of its ranks is which visible stage.

### What is still unknown

**What the scene resource table's `+0x08` field holds**, and what its two
pointers into the `0x8C112xxx` area are for. The size matches neither the MDL
entry's nor the TEX entry's.

**Who writes the scene index** in RAM (`0x8C1F56CF` on the `0x8C034D1C` path).
The stage → entry pairing is established, but the step before it — what decides
the rank — is not.

### Three lessons in method

**A table of names says nothing about content.** The two versions' name lists
are identical name for name, which at first led to the conclusion that no stage
was exclusive. That is false: a list of names enumerates the *planned* slots,
full or empty. You have to follow each record to its payload.

**Resource identifiers are not addresses.** The `0x00A0xxxx` values unrolled as
Real3D models with `model3d.py` fail on the very first polygon, on the face
normal's norm.

**A regularity is not a format.** The music enumeration splits 16/16 without a
single discordant note, and that split is wrong. The field only revealed itself
in the dispatcher's `extu.b`. A table that confirms a hypothesis on every one of
its elements may be confirming only a special case: it is the code that states
the format, not the data.

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
| `textures_dc.py` | decode Dreamcast textures — VQ, twiddle, three pixel formats — and pair the MDL and TEX entries |
| `geometrie_dc.py` | export an MDL entry's geometry to OBJ, handling both vertex forms |
| `retrouver.py` | find a dumped texture among the disc's 3,700, by signature |
| `fermer_trous.py` | close an OBJ's boundary-edge loops, and repeat across the four quadrants |
| `rendu_dessus.py` | rasterise an OBJ seen from above — judge an extraction without opening Blender |
| `rendu_face.py` | the same, seen from the front |
| `planche_dc.py` | contact sheet of every texture in one entry |
| `desas_sh4.py` | SH-4 disassembler: reads an address without requiring it to be proven code |
| `tables_sh4.py` | four discoverers — who loads a literal, who branches here, the `BRAF` tables, and the call graph walked upward |
| `decor_vers_entree.py` | make a dump folder vote to find a stage's MDL entry |
| `gdb_flycast.py` | remote GDB client for Flycast, standard library only |

Five `.cmd` launchers chain what is needed, with no command line to retype:
**Reconstruire les ROM arcade**, **Ouvrir le disque Dreamcast**,
**Table des décors**, **Profil des modèles Dreamcast**,
**Sonder le binaire Dreamcast**. The default paths to
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

**How a stage names its geometry.** The resource dispatcher has been found and
read — see [Resolving resource identifiers](#resolving-resource-identifiers) —
but it only handles audio: music, effects, and a third genre with hand-written
cases. A stage's `+0x08` list is audio from end to end. Geometry therefore
loads along another path, and while the `mdl_dat` reader is identified
(`0x8C02A5A8`, partition 1), we do not know which index it receives for a given
stage. The only known pairing, MDL 75 ↔ TEX 112 for the training stage, came
from measuring textures.

**Bit 5 of the strip code.** A strip header is two words,
`(code, vertex count)`, and the count is right on 96.8% of the archive's 52,944
strips. The failures hinge on a single bit: without bit 5, 25,026 strips read
at 100.0%; with it, 27,918 read at 93.9%. Among those failures the most common
shortfall is exactly 2 — the signature of a continued strip, whose first two
vertices would be carried over from the previous one and not stored. A
plausible reading, unproven. Ruled out by measurement: too short an
interleaving window, a normal stored elsewhere, any other uniform stride.

**The role of each character's third, reduced entry** — 42 for Honey, 47 for
Jane: broken armour or a level of detail, undecided. And **how the game picks
Honey's second costume** (MDL 43 and 44), which it names nowhere: `NURSE`,
`COSTUME`, `SECRET`, `MAID`, `APRON`, `OUTFIT`, swept in ASCII and in
Shift-JIS across the whole binary — zero hits.

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
