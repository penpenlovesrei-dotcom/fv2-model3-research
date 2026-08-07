"""Construit la carte de symboles de Fighting Vipers 2.

Deux sources :
  - les tables du menu de debug, où Sega a lui-même nommé ses variables
    (entrées de 0x20 octets : +00 pointeur vers le libellé, +0C adresse de
    la variable, +1C type ; quand l'octet de poids fort du type vaut 0x10,
    le champ +0C est un index et non une adresse, on l'ignore) ;
  - nos propres identifications, établies par mesure au fil des séances.

Produit `symbols.csv` (adresse,nom), réinjectable dans Ghidra par
ApplySymbols.java.
"""

import pathlib
import re
import struct

RAM = pathlib.Path(__file__).parent / "fv2_ram.bin"
OUT = pathlib.Path(__file__).parent / "symbols.csv"

# identifiés par la mesure, pas par le jeu : ils n'ont pas de nom d'origine
NOTRE_TRAVAIL = {
    0x00279668: "curseur_select_P1",
    0x00279669: "curseur_select_P2",
    0x0027966C: "curseur_select_copie2_P1",
    0x0027967C: "curseur_select_copie3_P1",
    0x00279691: "verrou_code_secret",
    0x00279693: "verrou_deplacement_curseur",
    0x0011F060: "progression_desactive_secret",
    0x0011F061: "progression_delsol_acquis",
    0x0011F06F: "progression_kuhn_dispo",
    0x00581408: "compteur_ecran_selection",
    0x00580D20: "compteur_ecran_miroir",
    0x00580F00: "port_entree_operateur",
    0x00120557: "reglage_pays",
    0x000B16B8: "table_curseur_vers_perso",
    0x000B1658: "table_id_texte_noms",
    0x000B1758: "table_noms_objets",
    0x000B17D0: "liste_positions_courte",
    0x000B17DC: "liste_positions_complete",
    0x0008C637: "liste_noms_personnages",
    0x002924CC: "table_chaines_pays",
    0x0005F3BC: "test_boutons_operateur_PATCH_ROSTER",
    0x0005F340: "fn_deplacement_curseur",
    0x0005FE38: "fn_affichage_selection",
    0x00060D34: "fn_init_curseurs",
    0x00060184: "fn_curseur_vers_perso",
    0x0000ABC4: "fn_ecrit_progression",
    0x0006CCA4: "fn_menu_game_assignments",
    0x000392C0: "fn_lecture_entrees",
}


def charge():
    d = RAM.read_bytes()

    def chaine(a):
        if 0 < a < len(d) - 32:
            m = re.match(rb"[ -~]{2,30}\x00", d[a: a + 31])
            if m:
                return m.group()[:-1].decode()
        return None

    syms = {}
    # Bornes des deux tables de debug. Sans elles, le test structurel seul
    # attrape des milliers de faux positifs : n'importe quelle donnée suivie
    # d'un pointeur plausible ressemble à une entrée.
    PLAGES = ((0x116A00, 0x117400), (0x11D100, 0x11D400))
    for a in [a for lo, hi in PLAGES for a in range(lo, hi, 4)]:
        lbl = chaine(struct.unpack_from(">I", d, a)[0])
        if not lbl or len(lbl) < 3:
            continue
        var = struct.unpack_from(">I", d, a + 0x0C)[0]
        typ = struct.unpack_from(">I", d, a + 0x1C)[0]
        if (typ >> 24) == 0x10:          # +0C est un index, pas une adresse
            continue
        if not (0x1000 < var < 0x800000):
            continue
        nom = re.sub(r"[^A-Za-z0-9]+", "_", lbl).strip("_").lower()
        if nom and var not in syms:
            base = "dbg_" + nom
            if base in syms.values():          # même libellé, adresse différente
                base = f"{base}_{var:06X}"
            syms[var] = base
    return syms


syms = charge()
avant = len(syms)
syms.update(NOTRE_TRAVAIL)          # nos noms priment sur ceux du debug

with OUT.open("w", encoding="utf-8") as f:
    f.write("# adresse,nom\n")
    for a in sorted(syms):
        f.write(f"{a:08X},{syms[a]}\n")

print(f"{avant} symboles issus des tables de debug du jeu")
print(f"{len(NOTRE_TRAVAIL)} identifiés par nos mesures")
print(f"{len(syms)} au total -> {OUT.name}")
