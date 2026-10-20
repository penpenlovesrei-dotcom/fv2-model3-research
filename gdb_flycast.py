"""Client GDB distant pour Flycast, en bibliotheque standard.

Flycast embarque un serveur GDB (`Debug.GDBEnabled = yes`, port 3263 par
defaut). Le protocole est assez simple pour qu'on s'en passe de `sh-elf-gdb` :
un paquet vaut `$<donnees>#<somme sur deux chiffres hex>`, l'autre bout
accuse par `+`.

A quoi ca sert ici : les tables de decors de Fighting Vipers 2 ne sont
referencees par AUCUNE fonction dans Ghidra -- elles sont atteintes par adresse
calculee. Le desassemblage ne dira donc pas qui les lit. **Un point d'arret sur
la lecture le dira en une fois.**

Adresses utiles (le binaire est charge a 0x8C010000) :

    0x8C11763C   la table de decors, 27 enregistrements de 0x70
    0x8C113308   la liste des 8 ressources du decor TEST
    0x8C113314   dans cette liste, l'identifiant de GEOMETRIE (0x001800F0)
    0x8C112420   l'enumeration des 25 creneaux de geometrie

**Le dynarec doit etre desactive** (`Dynarec.Enabled = no`) : il compile le
SH-4 en x86 et les points d'arret materiels n'y sont pas honores.

Usage :
    py -3 gdb_flycast.py etat
    py -3 gdb_flycast.py guette <adresse> [longueur] [--ecriture]
    py -3 gdb_flycast.py lire <adresse> <longueur>
"""

import socket
import sys
import time

HOTE, PORT = "127.0.0.1", 3263

# Ordre des registres rendu par le paquet `g` du stub SH-4 de Flycast :
# r0-r15, puis pc, pr, gbr, vbr, mach, macl, sr, fpul, fpscr, fr0-fr15
NOMS = ([f"r{i}" for i in range(16)]
        + ["pc", "pr", "gbr", "vbr", "mach", "macl", "sr", "fpul", "fpscr"])


class Gdb:
    def __init__(self, hote=HOTE, port=PORT, delai=5.0):
        self.s = socket.create_connection((hote, port), delai)
        self.s.settimeout(delai)
        self.reste = b""

    def envoie(self, data):
        somme = sum(data.encode()) & 0xFF
        self.s.sendall(f"${data}#{somme:02x}".encode())
        # accuse de reception
        a = self.s.recv(1)
        if a not in (b"+", b"-"):
            self.reste += a

    def lit_paquet(self, delai=None):
        if delai is not None:
            self.s.settimeout(delai)
        tampon = self.reste
        self.reste = b""
        while b"#" not in tampon or len(tampon.split(b"#", 1)[1]) < 2:
            m = self.s.recv(4096)
            if not m:
                raise ConnectionError("le serveur a ferme")
            tampon += m
        debut = tampon.index(b"$")
        fin = tampon.index(b"#", debut)
        corps = tampon[debut + 1:fin].decode("latin1")
        self.reste = tampon[fin + 3:]
        self.s.sendall(b"+")
        return corps

    def commande(self, data, delai=None):
        self.envoie(data)
        return self.lit_paquet(delai)

    def registres(self):
        brut = self.commande("g")
        out = {}
        for i, nom in enumerate(NOMS):
            mot = brut[i * 8:(i + 1) * 8]
            if len(mot) == 8:
                out[nom] = int.from_bytes(bytes.fromhex(mot), "big")
        return out

    def memoire(self, adresse, n):
        return bytes.fromhex(self.commande(f"m{adresse:x},{n:x}"))

    def guet(self, adresse, n, genre="lecture"):
        """genre : lecture (Z3), ecriture (Z2), les deux (Z4)."""
        z = {"ecriture": 2, "lecture": 3, "les deux": 4}[genre]
        r = self.commande(f"Z{z},{adresse:x},{n:x}")
        return r, z

    def retire_guet(self, adresse, n, z):
        return self.commande(f"z{z},{adresse:x},{n:x}")

    def continue_(self, delai=600.0):
        self.envoie("c")
        return self.lit_paquet(delai)

    def ferme(self):
        try:
            self.s.close()
        except OSError:
            pass


def decode_arret(reponse):
    """Rend (signal, dictionnaire des champs) d'une reponse T.."""
    if not reponse or reponse[0] not in "TS":
        return reponse, {}
    champs = {}
    if reponse[0] == "T":
        for part in reponse[3:].split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                champs[k] = v
    return reponse[1:3], champs


def cmd_etat():
    g = Gdb()
    print("connecte au serveur GDB de Flycast")
    print("   arret :", g.commande("?"))
    r = g.registres()
    print(f"   pc  {r.get('pc', 0):#010x}   pr  {r.get('pr', 0):#010x}")
    for i in range(0, 16, 4):
        print("   " + "  ".join(f"r{j:<2}={r.get(f'r{j}', 0):#010x}" for j in range(i, i + 4)))
    g.ferme()


def cmd_lire(adresse, n):
    g = Gdb()
    d = g.memoire(adresse, n)
    for o in range(0, len(d), 16):
        bloc = d[o:o + 16]
        print(f"   {adresse + o:#010x}  " + " ".join(f"{b:02x}" for b in bloc))
    g.ferme()


def cmd_guette(adresse, n, genre):
    g = Gdb()
    print(f"point d'arret en {genre} sur {adresse:#010x}, {n} octets")
    r, z = g.guet(adresse, n, genre)
    if r == "":
        print("   le serveur ne connait pas ce type de point d'arret (reponse vide)")
        g.ferme()
        return
    if r != "OK":
        print(f"   refus : {r!r}")
        g.ferme()
        return
    print("   pose. Lance le decor dans le jeu, j'attends...")
    t0 = time.time()
    try:
        rep = g.continue_()
    except socket.timeout:
        print("   rien en 600 s")
        g.ferme()
        return
    sig, champs = decode_arret(rep)
    print(f"   ARRET apres {time.time() - t0:.0f} s, signal {sig}")
    for k, v in champs.items():
        print(f"      {k} = {v}")
    reg = g.registres()
    print(f"   pc = {reg.get('pc', 0):#010x}   pr (retour) = {reg.get('pr', 0):#010x}")
    print("   registres :")
    for i in range(0, 16, 4):
        print("      " + "  ".join(f"r{j:<2}={reg.get(f'r{j}', 0):#010x}"
                                   for j in range(i, i + 4)))
    g.retire_guet(adresse, n, z)
    g.ferme()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    quoi = sys.argv[1]
    try:
        if quoi == "etat":
            cmd_etat()
        elif quoi == "lire":
            cmd_lire(int(sys.argv[2], 0), int(sys.argv[3], 0))
        elif quoi == "guette":
            a = int(sys.argv[2], 0)
            n = int(sys.argv[3], 0) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 4
            genre = "ecriture" if "--ecriture" in sys.argv else "lecture"
            cmd_guette(a, n, genre)
        else:
            raise SystemExit(__doc__)
    except ConnectionRefusedError:
        raise SystemExit(
            "connexion refusee sur 127.0.0.1:3263.\n"
            "Verifie que Flycast tourne, et que emu.cfg porte Debug.GDBEnabled = yes")
