"""Extrait et reinjecte le programme de Fighting Vipers 2, qui est un GZIP.

Le depot de notes dit depuis le debut que le programme est compresse en LZSS.
**C'est faux.** Mesure du 2026-08-22 : la CROM de FV2 commence, a l'offset 0,
par un fichier gzip complet -- magie `1f 8b`, methode 8 (deflate), drapeau
FNAME -- dont l'en-tete porte le nom d'origine `foo.bin` et la date de
compression du **26 mars 1998 a 16:01:08 UTC**, systeme Unix.

Ce qui l'a fait croire : le menu de test du jeu nomme lui-meme son entree
`LZSS_INFO`. L'etiquette de Sega ne decrit pas l'algorithme.

La preuve tient en trois points, tous verifies :

  - les trois tables canoniques de DEFLATE sont dans l'amorce, en 16 bits
    big-endian : `cplens` en 0xFFF03604, `cplext` en 0xFFF03642, `cpdist` en
    0xFFF03680, et le decompresseur est le `huft_build` de zlib ;
  - `zlib.decompressobj(-15)` decompresse le flux d'un bout a l'autre, et le
    CRC32 du pied gzip **concorde** ;
  - les 2 701 982 octets obtenus se posent en **RAM a l'adresse 0**, identiques
    a 99,9 % a un releve de la RAM en cours de jeu -- l'ecart etant ce que le
    jeu a ecrit depuis le demarrage.

Consequence pratique : **plus rien n'est a reverser**. On decompresse, on
modifie, on recompresse avec la bibliotheque standard. Et la place ne manque
pas : le gzip d'origine fait 897 277 octets, celui de Python en niveau 9 en
fait 882 023 pour le meme contenu, soit **15 254 octets de marge**.

Il reste une derniere marche pour un vrai zip de ROM : re-entrelacer la CROM
sur les quatre EPROM. `build_crom.py` fait le chemin dans un sens seulement.

Usage :
    python gzip_crom.py extraire              -> foo.bin
    python gzip_crom.py injecter foo.bin      -> fv2_crom_patchee.bin
"""

import gzip
import io
import pathlib
import struct
import sys
import zlib

ICI = pathlib.Path(__file__).parent
# L'image CROM deinterleavee, telle que la produit build_crom.py. Le chemin se
# surcharge par la variable d'environnement FV2_CROM si elle est ailleurs.
import os
CROM = pathlib.Path(os.environ.get("FV2_CROM", ICI / "fv2_crom_swap16.bin"))
MTIME = 890928068          # 1998-03-26 16:01:08 UTC, celui de Sega
NOM = "foo.bin"


def lit_entete(d, p=0):
    """Rend (offset du flux deflate, nom d'origine)."""
    magie, methode, drapeaux = struct.unpack_from("<HBB", d, p)
    if magie != 0x8B1F or methode != 8:
        raise SystemExit(f"pas de gzip a l'offset {p:#x}")
    q = p + 10
    nom = ""
    if drapeaux & 8:
        fin = d.index(b"\0", q)
        nom = d[q:fin].decode("latin1")
        q = fin + 1
    return q, nom


def extraire():
    d = CROM.read_bytes()
    q, nom = lit_entete(d)
    o = zlib.decompressobj(-15)
    out = o.decompress(d[q:])
    crc, taille = struct.unpack_from("<II", o.unused_data, 0)
    if zlib.crc32(out) != crc or taille != len(out):
        raise SystemExit("le pied gzip ne concorde pas : image suspecte")
    fin = len(d) - len(o.unused_data) + 8
    sortie = ICI / (nom or "foo.bin")
    sortie.write_bytes(out)
    print(f"{sortie.name} : {len(out)} octets, decompresses depuis {fin} octets de gzip")
    print(f"  CRC32 {crc:#010x} verifie, se pose en RAM a l'adresse 0")
    return fin


def injecter(chemin):
    d = bytearray(CROM.read_bytes())
    budget = extraire_taille(bytes(d))
    contenu = pathlib.Path(chemin).read_bytes()
    buf = io.BytesIO()
    with gzip.GzipFile(filename=NOM, mode="wb", fileobj=buf,
                       compresslevel=9, mtime=MTIME) as f:
        f.write(contenu)
    neuf = buf.getvalue()
    print(f"gzip d'origine : {budget} octets")
    print(f"gzip reconstruit : {len(neuf)} octets  ({len(neuf)-budget:+d})")
    if len(neuf) > budget:
        raise SystemExit("le flux recompresse depasse la place d'origine : "
                         "reduire les modifications, ou verifier ce qui suit "
                         "dans la CROM avant d'empieter dessus")
    d[0:len(neuf)] = neuf
    d[len(neuf):budget] = b"\0" * (budget - len(neuf))
    sortie = ICI / "fv2_crom_patchee.bin"
    sortie.write_bytes(bytes(d))
    print(f"{sortie.name} ecrite. Reste a re-entrelacer sur les quatre EPROM.")


def extraire_taille(d):
    q, _ = lit_entete(d)
    o = zlib.decompressobj(-15)
    o.decompress(d[q:])
    return len(d) - len(o.unused_data) + 8


if __name__ == "__main__":
    quoi = sys.argv[1] if len(sys.argv) > 1 else "extraire"
    if quoi == "extraire":
        extraire()
    elif quoi == "injecter":
        injecter(sys.argv[2])
    else:
        raise SystemExit(__doc__)
