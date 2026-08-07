"""Décode la liste d'affichage : dit quels éléments graphiques sont dessinés.

Remplace la déduction par la mesure. Plutôt que de deviner quelle fonction
dessine l'écran affiché, on lit ce que le jeu vient réellement d'empiler.

Mécanique, tirée de `FUN_00006B3C` :
  - chaque appel écrit un paquet de 10 mots (40 octets) commençant par
    `0x06000000`, dans un tampon en RAM principale ;
  - le mot 7 du paquet contient `table[element]` **en boutisme inversé**,
    la table étant en `0x3003CC` ;
  - on inverse donc le mot, et on cherche la valeur dans la table pour
    retrouver l'identifiant à passer à `FUN_00006B3C`.

Usage: python displaylist.py [image.bin]
       sans argument, prend un instantané du jeu en cours.
"""

import pathlib
import struct
import subprocess
import sys

ICI = pathlib.Path(__file__).parent
TABLE = 0x003003CC
TABLE_MAX = 0x2000          # indices plausibles, couvre les 0x12xx observés
ZONE = (0x7D8000, 0x800000)
ENTETE = b"\x06\x00\x00\x00"
PAS = 40

if len(sys.argv) > 1:
    img = pathlib.Path(sys.argv[1])
else:
    img = ICI / "dl_snapshot.bin"
    subprocess.run([sys.executable, str(ICI / "mem.py"), "dump", str(img)], check=True)

d = img.read_bytes()

# table pointeur -> identifiant
vers_id = {}
for i in range(TABLE_MAX):
    v = struct.unpack_from(">I", d, TABLE + i * 4)[0]
    vers_id.setdefault(v, i)

paquets = [a for a in range(ZONE[0], ZONE[1] - PAS, 4) if d[a:a + 4] == ENTETE]
print(f"{len(paquets)} paquets entre {ZONE[0]:#08x} et {ZONE[1]:#08x}")

vus, inconnus = [], 0
for a in paquets:
    brut = struct.unpack_from(">I", d, a + 28)[0]
    ptr = int.from_bytes(brut.to_bytes(4, "big")[::-1], "big")   # boutisme inversé
    eid = vers_id.get(ptr)
    if eid is None:
        inconnus += 1
    else:
        vus.append(eid)

uniques = sorted(set(vus))
print(f"{len(vus)} éléments identifiés, {len(uniques)} distincts, {inconnus} non résolus\n")

# regroupement par plage : chaque écran utilise sa propre tranche d'identifiants
plages = {}
for e in uniques:
    plages.setdefault(e >> 8, []).append(e)
for p in sorted(plages):
    ids = plages[p]
    print(f"  plage {p << 8:#06x} : {len(ids):3} éléments   "
          + " ".join(f"{e:#06x}" for e in ids[:12])
          + (" ..." if len(ids) > 12 else ""))
