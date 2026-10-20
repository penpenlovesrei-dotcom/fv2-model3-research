"""Extrait la geometrie d'une entree de MDL_DAT.AFS, et la sort en OBJ.

Format etabli le 2026-10-20 sur l'entree 75 (le decor d'entrainement), par la
mesure -- chaque champ ci-dessous a ete verifie, aucun n'est suppose.

**En-tete d'entree**, 24 octets :

    +0x00 u32   1 (classe decor) ou -1 (classe personnage)
    +0x04 u32   3
    +0x08 3f    boite englobante de l'entree : centre x, y, z
    +0x14 f     son rayon

**Une PARTIE** commence par quatre mots de parametre du Tile Accelerator du
PowerVR2, pre-cuits dans le fichier, puis :

    +0x00 u32   TA Parameter Control (0x8xxxxxxx)
    +0x04 u32   TA ISP/TSP           (0x83xxxxxx)
    +0x08 u32   TA TSP
    +0x0C u32   TA Texture Control   (champ adresse nul : rempli au chargement)
    +0x10 3f    boite englobante de la partie : centre x, y, z
    +0x1C f     son rayon
    +0x20 u32   compteur
    +0x24 u32   0xFFFFFFFF, sentinelle
    +0x28 9f    bloc d'eclairage (0.75, 1,1,1, 1, 0, puis une couleur)
    +0x4C u32   taille en octets de ce qui suit
    +0x50 ...   les rubans

**Un RUBAN**, deux mots d'en-tete puis ses sommets :

    +0x00 u32   code de format
    +0x04 u32   nombre de sommets
    +0x08 ...   les sommets

Mesure sur les 78 entrees de l'archive, 52 944 rubans : le compte annonce est
**juste a 96,8 %**. Les echecs ne sont pas disperses, ils tiennent a **un seul
bit du code, le bit 5** :

    bits 4-7    rubans   compte juste
    0x00, 0x10, 0x50, 0x90, 0xD0   25 026   100,0 %   (bit 5 efface)
    0x30, 0x70, 0xB0, 0xF0         27 918    93,9 %   (bit 5 mis)

Dans ces 3,2 % d'echecs, l'ecart le plus frequent est **exactement 2** --
(7,5), (6,4), (10,8), (18,16), (9,7), (14,12). C'est la signature d'un **ruban
continue** : les deux premiers sommets sont repris du ruban precedent et ne
sont pas stockes. Non prouve, mais c'est la seule lecture qui rende compte de
l'ecart constant. Les ecarts plus grands sont vraisemblablement ce meme
mecanisme en cascade.

Ecarte par la mesure : ce n'est ni une fenetre d'intercalation trop courte (la
porter de 64 a 512 octets ne gagne que 0,1 point), ni une normale rangee
ailleurs, ni un autre pas uniforme (aucune des dispositions (offset, pas)
essayees ne valide un seul des 1 716 rubans en echec).

**Un SOMMET** commence toujours par position xyz puis **normale unitaire** xyz
-- 24 octets -- suivis des coordonnees de texture :

    +0x00 3f   position x, y, z
    +0x0C 3f   normale x, y, z, unitaire
    +0x18 1f   u
    +0x1C u32  v, ou le marqueur 0x80000001 dans la forme longue
    +0x20 u32  couleur 1   )  forme longue (40 octets)
    +0x24 u32  couleur 2   )  seulement

Et le pas n'est pas constant dans un ruban : des **mots d'etat s'intercalent**
entre les sommets, par blocs de deux ou quatre mots. Les ecarts mesures entre
sommets consecutifs valent 32, 40 ou 48 octets -- 40 - 32 = 8 et 48 - 32 = 16,
soit deux et quatre mots. C'est une liste d'affichage, pas un format de sommet
variable : le ruban (0xF2, 6) de la partie 1 de l'entree 75 donne bien ses six
sommets, aux ecarts 40, 40, 48, 32, 32.

La norme de la normale est ce qui permet de tout verifier sans rien supposer :
elle vaut 1 a 1e-3 pres pour un decoupage juste, et n'importe quoi sinon. Le
script **mesure donc le pas** de chaque ruban au lieu de le deduire du code, et
rend la table des codes rencontres pour qu'on la documente.

Les positions sont deja en espace modele : aucune matrice de partie n'a ete
trouvee, et les boites englobantes des parties se placent d'elles-memes dans
celle de l'entree.

Usage :
    py -3 geometrie_dc.py <indice>              -> geometrie_dc/<indice>.obj
    py -3 geometrie_dc.py <indice> --rapport    la structure, sans ecrire
"""

import math
import pathlib
import struct
import sys

ICI = pathlib.Path(__file__).parent
sys.path.insert(0, str(ICI))
import textures_dc as T

NL = chr(10)
PAS_CANDIDATS = (32, 40, 48, 24, 20)
TOLERANCE = 1e-2   # 1e-3 coupait des rubans sur quelques sommets limites


def unitaire(b, p):
    """La normale d'un sommet suppose a cet offset est-elle unitaire ?"""
    if p + 32 > len(b):
        return False
    x, y, z = struct.unpack_from("<3f", b, p + 12)
    if not all(math.isfinite(v) for v in (x, y, z)):
        return False
    if abs((x * x + y * y + z * z) ** 0.5 - 1.0) >= TOLERANCE:
        return False
    # la position et les coordonnees de texture doivent l'etre aussi : la
    # lecture tolerante laissait passer des NaN sans ce controle
    reste = struct.unpack_from("<3f", b, p) + struct.unpack_from("<2f", b, p + 24)
    return all(math.isfinite(v) for v in reste) and max(abs(v) for v in reste[:3]) < 1e5


def pas_du_ruban(b, p, n):
    """Mesure le pas : le plus petit qui rende les n normales unitaires."""
    for pas in PAS_CANDIDATS:
        if p + n * pas > len(b):
            continue
        if all(unitaire(b, p + i * pas) for i in range(n)):
            return pas
    return None


def parties(b):
    """Les offsets des parties : un couple (0x8xxxxxxx, 0x83xxxxxx)."""
    out = []
    for p in range(0, len(b) - 8, 4):
        a = struct.unpack_from("<I", b, p)[0]
        c = struct.unpack_from("<I", b, p + 4)[0]
        if (a >> 28) == 8 and (c >> 24) == 0x83:
            out.append(p)
    return out


def sommet_couleur(b, p):
    """Un sommet de la disposition SANS normale, reconnu a ses couleurs.

    Le mot de parametre TA de la partie decide de la disposition du sommet par
    ses bits 4-5, le ColType du PowerVR2 :

        ColType 2 ou 3 (PCW ...2C, ...3C) : position 3f, NORMALE 3f, u, v
        ColType 1      (PCW ...1C)        : position 3f, un mot compacte,
                                            deux mots de couleur, u, v

    Les deux font 32 octets. Mesure qui l'etablit : sur l'entree 75, les six
    parties qui ne rendaient aucun ruban sont exactement les six a PCW
    0x8000001C, et aucune autre.

    Le test de validite de cette seconde forme est ses deux mots de couleur :
    ils sont **egaux** et leur octet de poids fort vaut 0xFF (0xFF0F0F0F,
    0xFF000000, 0xFF6E7374...). C'est aussi serre que la normale unitaire.
    """
    if p + 32 > len(b):
        return False
    c1, c2 = struct.unpack_from("<II", b, p + 16)
    if c1 != c2 or (c1 >> 24) != 0xFF:
        return False
    pos = struct.unpack_from("<3f", b, p)
    uv = struct.unpack_from("<2f", b, p + 24)
    return (all(math.isfinite(v) for v in pos + uv)
            and max(abs(v) for v in pos) < 1e5)


def lit_ruban_couleur(b, p, n, fin, saut_max=64):
    """Comme lit_ruban, pour la disposition sans normale."""
    sommets = []
    coupures = set()
    q = p
    for k in range(n):
        saut = 0
        while q + 32 <= fin and not sommet_couleur(b, q) and saut < saut_max:
            q += 4
            saut += 4
        # Meme regle que lit_ruban : au-dela de 8 octets, le bloc intercale est
        # un changement d'etat et le ruban ne doit pas etre relie par-dessus.
        # Son absence ici dechirait le tapis du ring en longs triangles stries.
        if k and saut > 8:
            coupures.add(k)
        if q + 32 > fin or not sommet_couleur(b, q):
            return (sommets, q, coupures) if len(sommets) >= 3 else None
        pos = struct.unpack_from("<3f", b, q)
        uv = struct.unpack_from("<2f", b, q + 24)
        sommets.append(pos + (0.0, 0.0, 0.0) + uv)
        q += 32
    return sommets, q, coupures


def lit_ruban(b, p, n, fin, saut_max=64):
    """Lit n sommets a partir de p, en sautant ce qui s'intercale.

    Le pas n'est pas constant : les ecarts mesures entre sommets consecutifs
    d'un meme ruban valent 32, 40 ou 48 octets. 40 - 32 = 8 et 48 - 32 = 16,
    soit deux ou quatre mots -- ce sont des **mots d'etat intercales**, comme
    dans une liste d'affichage, et non un pas de sommet variable. Le compte de
    l'en-tete, lui, ne compte que les SOMMETS : le ruban (0xF2, 6) de la partie
    1 en donne bien six, aux ecarts 40, 40, 48, 32, 32.

    On lit donc n sommets en avancant de 32 octets, puis en balayant par mots
    de 4 jusqu'au suivant. Rend (sommets, offset de fin) ou None si le compte
    n'est pas atteint.
    """
    sommets = []
    coupures = set()
    q = p
    for k in range(n):
        saut = 0
        while q + 32 <= fin and not unitaire(b, q) and saut < saut_max:
            q += 4
            saut += 4
        # Un saut de 8 octets est la forme longue du sommet (deux mots de
        # couleur) : le ruban continue. Au-dela, le bloc intercale est un
        # changement d'etat, et relier par-dessus fabrique des raccordements
        # faux -- c'est ce qui desordonnait le sol.
        if k and saut > 8:
            coupures.add(k)
        if q + 32 > fin or not unitaire(b, q):
            # Le compte annonce depasse parfois ce qui tient dans la zone : la
            # partie 0x760 annonce 18 sommets dans 536 octets, et n'en porte
            # que 16, a pas 32 constant. On rend ce qu'on a plutot que rien.
            return (sommets, q, coupures) if len(sommets) >= 3 else None
        sommets.append(struct.unpack_from("<8f", b, q))
        q += 32
    return sommets, q, coupures


def ramasse_restes(b, debut, fin, pris, test, lus):
    """Troisieme passe : les sommets valides qu'aucune passe n'a pris.

    Apres la marche dirigee par les en-tetes et le repli par suites, il reste
    des sommets isoles ou en petits groupes -- 159 sur l'entree 75. Ils sont
    valides au meme test que les autres ; on les ramasse en suites de pas 32 et
    on les rend comme des rubans a part, pour ne rien laisser au sol.
    """
    out = []
    p = debut
    while p + 32 <= fin:
        if p in pris or not test(b, p):
            p += 4
            continue
        s = []
        q = p
        while q + 32 <= fin and q not in pris and test(b, q):
            s.append(struct.unpack_from("<8f", b, q))
            q += 32
        if len(s) >= 3:
            out.append((0, 32, s, "reste"))
            for r in range(p, q):
                pris.add(r)
        p = q if len(s) >= 3 else p + 4
    lus += len(out)
    return out


def rubans_par_les_normales(b, debut, fin, pcw=0):
    """Les rubans d'une partie, trouves par le test de la normale unitaire.

    La disposition exacte de l'en-tete de ruban n'est pas etablie : les
    compteurs annonces (+0x20, +0x4C, +0x50, +0x54) ne cadrent pas sur toutes
    les parties, et le pas varie d'un ruban a l'autre. On ne s'y fie donc pas.

    Ce qui ne ment pas, c'est la normale : trois flottants consecutifs dont la
    norme vaut 1 a 1e-3 pres. La probabilite qu'un triplet quelconque tombe
    dans cette fenetre est infime, donc une suite de sommets dont TOUS passent
    le test est une vraie suite de sommets. On balaye, on retient les suites
    d'au moins trois, et les deux mots d'en-tete se trouvent sautes d'eux-memes.
    """
    out = []
    pris = set()
    coltype1 = ((pcw >> 4) & 3) == 1
    test = sommet_couleur if coltype1 else unitaire
    p = debut
    while p + 32 <= fin:
        # 1. l'en-tete quand c'en est un : deux mots, le second un petit compte.
        #    Le balayage seul derape, parce qu'un faux positif decale de 4 octets
        #    suffit a desaligner toute la suite (mesure : 0x134 passe le test de
        #    la normale alors que le vrai sommet est en 0x138).
        code, n = struct.unpack_from("<II", b, p)
        if 0 < n < 2048 and code < 0x10000:
            lecteur = lit_ruban_couleur if ((pcw >> 4) & 3) == 1 else lit_ruban
            r = lecteur(b, p + 8, n, fin)
            if r:
                sommets, q, coupures = r
                out.append((code, 32, sommets, "entete", coupures))
                for r in range(p, q):
                    pris.add(r)
                p = q
                continue
            # en-tete plausible mais illisible : on ne saute pas en aveugle,
            # on laisse le repli ci-dessous tenter sa chance ici meme
        # 2. repli : la suite de sommets la plus longue a partir d'ici
        meilleur = None
        for pas in (32, 40):
            if not (unitaire(b, p) and unitaire(b, p + pas) and unitaire(b, p + 2 * pas)):
                continue
            # Pas de pontage : un ruban s'arrete au premier sommet qui ne passe
            # pas. Ponter faisait deborder les suites sur le ruban suivant,
            # dont le pas est different -- mesure sur la partie 1, ou un ruban
            # de 3 sommets a 40 octets precede un ruban de 12 a 32.
            n = 0
            while p + (n + 1) * pas <= fin and unitaire(b, p + n * pas):
                n += 1
            if meilleur is None or n * pas > meilleur[0] * meilleur[1]:
                meilleur = (n, pas)
        if meilleur:
            n, pas = meilleur
            code = struct.unpack_from("<I", b, p - 8)[0] if p - 8 >= 0 else 0
            sommets = [struct.unpack_from("<8f", b, p + i * pas) for i in range(n)]
            out.append((code, pas, sommets, "repli"))
            for r in range(p, p + n * pas):
                pris.add(r)
            p += n * pas
        else:
            p += 4
    out += ramasse_restes(b, debut, fin, pris, test, len(out))
    return out


def lit_partie(b, debut, fin):
    """Rend (en-tete, [rubans]). Un ruban : (code, pas, [sommets])."""
    ta = struct.unpack_from("<4I", b, debut)
    boite = struct.unpack_from("<4f", b, debut + 0x10)
    taille = struct.unpack_from("<I", b, debut + 0x4C)[0]
    p = debut + 0x50
    borne = min(fin, debut + 0x50 + taille) if taille else fin
    rubans = []
    while p + 8 <= borne:
        code, n = struct.unpack_from("<II", b, p)
        if not (0 < n < 4096):
            break
        pas = pas_du_ruban(b, p + 8, n)
        if pas is None:
            break
        sommets = []
        for i in range(n):
            f = struct.unpack_from("<8f", b, p + 8 + i * pas)
            sommets.append(f)
        rubans.append((code, pas, sommets))
        p += 8 + n * pas
    return {"ta": ta, "boite": boite, "taille": taille, "fin_lue": p,
            "texture": struct.unpack_from("<I", b, debut + 0x20)[0]}, rubans


def extrait(indice):
    mdl, me = T.afs("MDL_DAT.AFS")
    mo, ms = me[indice]
    b = mdl[mo:mo + ms]
    bornes = parties(b) + [len(b)]
    entete = struct.unpack_from("<4f", b, 8)
    tout = []
    for k in range(len(bornes) - 1):
        h, _ = lit_partie(b, bornes[k], bornes[k + 1])
        rubans = rubans_par_les_normales(b, bornes[k] + 0x50, bornes[k + 1],
                                         h["ta"][0])
        tout.append((bornes[k], h, rubans))
    return entete, tout


def rapport(indice, entete, tout):
    codes = {}
    ns = nr = 0
    reste = 0
    for debut, h, rubans in tout:
        for code, pas, sommets, *_ in rubans:
            codes.setdefault((code, pas), 0)
            codes[(code, pas)] += 1
            ns += len(sommets)
            nr += 1
        attendu = debut + 0x50 + h["taille"]
        reste += max(0, attendu - h["fin_lue"])
    print(f"MDL[{indice}] : boite de l'entree centre "
          f"({entete[0]:.3f}, {entete[1]:.3f}, {entete[2]:.3f}) rayon {entete[3]:.3f}")
    print(f"{len(tout)} parties, {nr} rubans, {ns} sommets")
    print(f"octets de rubans non lus : {reste}\n")
    print("codes de format rencontres :")
    for (code, pas), n in sorted(codes.items()):
        print(f"   code {code:#06x}  pas {pas} octets  x{n} rubans")


def ecris_textures(dossier, tex, k, liste, prefixe):
    """Sort les textures de l'entree a cote de l'OBJ.

    Rend une liste de (nom, transparente). La transparence n'est pas devinee
    d'apres le format : on compte les texels non opaques. Sur le decor
    d'entrainement, une seule des sept l'est -- la numero 1, **0 % opaque**,
    14 niveaux d'alpha, dominante (224, 0, 32) : le laser rouge. Les six autres
    sont opaques a 100 %.
    """
    noms = []
    to = T.afs("TEX_DAT.AFS")[1][k][0]
    for i, d in enumerate(liste):
        n = T.taille_stockee(d["w"], d["h"], d["stockage"])
        brut = tex[to + d["off"]: to + d["off"] + n]
        nom = f"{prefixe}_tex{i:02}.png"
        transparente = False
        if len(brut) == n:
            pix = T.decode(brut, d)
            T.png(pathlib.Path(dossier) / nom, d["w"], d["h"], pix)
            non_opaques = sum(1 for q in pix if q[3] < 255)
            transparente = non_opaques * 100 > len(pix)
        noms.append((nom, transparente))
    return noms


def retire_prototypes(tout, rayon=7.0):
    """Ne garde les emetteurs QUE dans la tour d'angle.

    Le decor n'a que quatre emetteurs empiles a chaque coin du ring, et rien
    d'autre. Dans l'entree, la tour est stockee une fois, au coin
    (-6,32 ; -6,32) : 27 pieces entre les rayons 8,47 et 9,35, soit quatre
    emetteurs d'environ sept pieces chacun. La replication au quart de tour les
    porte aux quatre coins.

    Tout le reste -- 28 petites pieces a texture 3 ou 4 posees entre les rayons
    0,04 et 5,83 -- sont des doublons que le jeu n'affiche pas. Le seuil est lu
    dans les donnees et non choisi : les rayons s'arretent a 5,83 puis
    reprennent a 8,47, un vide de 2,6 unites sans une seule piece.
    """
    garde, retires = [], 0
    for debut, h, rubans in tout:
        pts = [v for r in rubans for v in r[2]]
        if len(pts) >= 3 and h["texture"] in (3, 4):
            cx = sum(v[0] for v in pts) / len(pts)
            cz = sum(v[2] for v in pts) / len(pts)
            xs = [v[0] for v in pts]; ys = [v[1] for v in pts]; zs = [v[2] for v in pts]
            taille = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
            if taille < 1.5 and (cx * cx + cz * cz) ** 0.5 < rayon:
                retires += 1
                continue
        garde.append((debut, h, rubans))
    print(f"   {retires} pieces d'emetteur retirees (hors tour d'angle)")
    return garde


def complete_symetrie(tout, seuil=0.95):
    """Complete les faces des pieces centrales par leur symetrie d'ordre 4.

    Le ring est symetrique : ses SOMMETS se superposent a eux-memes apres une
    rotation de 90 degres a 100 % pour le tapis (0x12038) et le disque
    (0x174B8), 96,6 % pour la couronne (0x140F8). Ses FACES, elles, ne le sont
    qu'a 64 a 84 % : mon decoupage des rubans laisse des trous selon le
    quadrant, et c'est ce qui dechire la surface en longs triangles stries.

    On ajoute donc, pour toute piece dont les sommets sont symetriques au-dela
    du seuil, les trois rotations de ses rubans. Les faces qui existaient deja
    sont ecartees a l'ecriture (deduplication par centroide), celles qui
    manquaient dans un quadrant sont fournies par la rotation d'un autre. Les
    sommets etant deja symetriques, les faces ajoutees tombent sur des sommets
    existants : rien n'est invente, on ne fait que reboucher.
    """
    import math

    def cle(v, q=0.05):
        return (round(v[0] / q), round(v[1] / q), round(v[2] / q))

    out = []
    completees = 0
    for debut, h, rubans in tout:
        out.append((debut, h, rubans))
        pts = [v for r in rubans for v in r[2]]
        if len(pts) < 12:
            continue
        S = {cle(v) for v in pts}
        R = {cle((-v[2], v[1], v[0])) for v in pts}
        if len(S & R) < seuil * len(S):
            continue
        completees += 1
        for tour in (1, 2, 3):
            a = math.radians(90 * tour)
            ca, sa = math.cos(a), math.sin(a)
            neufs = []
            for r in rubans:
                # Decalage infime vers le bas, croissant avec le tour : les
                # copies recouvrent PARTIELLEMENT les faces d'origine, et
                # coplanaires elles se disputaient les memes pixels -- c'est le
                # moucheté du tapis. Les ecarter rouvrait les trous ; 2 millimes
                # d'unite suffisent a trancher le test de profondeur sans que
                # la surface bouge a l'oeil.
                dy = -0.002 * tour
                s = [(v[0] * ca - v[2] * sa, v[1] + dy, v[0] * sa + v[2] * ca,
                      v[3] * ca - v[5] * sa, v[4], v[3] * sa + v[5] * ca,
                      v[6], v[7]) for v in r[2]]
                neufs.append((r[0], r[1], s) + tuple(r[3:]))
            out.append((debut, h, neufs))
    print(f"   {completees} pieces symetriques completees par rotation")
    return out


def replique_quart(tout, rayon_mini=1.5):
    """Replique le quart de ring stocke, aux trois autres quarts.

    RECONSTRUCTION, pas extraction : l'entree ne stocke qu'un quart. Mesures
    qui l'etablissent -- les grands faisceaux sont a 0, 30, 45 et 60 degres,
    soit un eventail qui couvre exactement un quart de tour ; et 33 des
    71 petites parties sont massees autour de 225 degres au lieu d'etre
    reparties. Le jeu fait tourner le tout de 90 degres trois fois.

    **Une copie n'est posee que si la piece n'existe pas deja a cet endroit.**
    Rien n'est regle a la main : on compare la signature des sommets de la
    copie a celle de toutes les pieces de l'entree. Quatre pieces a texture 5
    (0x15740, 0x15E18, 0x165C8, 0x16CE8) sont deja les quatre rotations d'un
    meme morceau, et les repliquer en fabriquait douze de trop -- visibles au
    niveau du ring. Le meme test ecarte aussi les pieces deja symetriques
    d'ordre 4, dont la rotation retombe sur elles-memes.
    """
    import math

    def signature(pts, q=0.05):
        return frozenset((round(v[0] / q), round(v[1] / q), round(v[2] / q))
                         for v in pts)

    sommets_de = {}
    for debut, h, rubans in tout:
        pts = [v for r in rubans for v in r[2]]
        if len(pts) >= 3:
            sommets_de[debut] = (pts, signature(pts))
    deja = [s for _, s in sommets_de.values()]

    out = list(tout)
    poses = ignorees = 0
    for tour in (1, 2, 3):
        a = math.radians(90 * tour)
        ca, sa = math.cos(a), math.sin(a)
        for debut, h, rubans in tout:
            bb = h["boite"]
            if (bb[0] ** 2 + bb[2] ** 2) ** 0.5 < rayon_mini:
                continue
            if debut not in sommets_de:
                continue
            pts, _ = sommets_de[debut]
            sr = signature([(v[0] * ca - v[2] * sa, v[1], v[0] * sa + v[2] * ca)
                            for v in pts])
            if any(len(sr & s) > 0.8 * len(sr) for s in deja):
                ignorees += 1
                continue
            neufs = []
            for r in rubans:
                s = [(v[0] * ca - v[2] * sa, v[1], v[0] * sa + v[2] * ca,
                      v[3] * ca - v[5] * sa, v[4], v[3] * sa + v[5] * ca,
                      v[6], v[7]) for v in r[2]]
                neufs.append((r[0], r[1], s) + tuple(r[3:]))
            out.append((debut, h, neufs))
            poses += 1
    print(f"   {poses} copies posees, {ignorees} ignorees (la piece y est deja)")
    return out


def ecris_obj(chemin, tout, noms_textures=None, tout_trianguler=False):
    """Rubans -> triangles, groupes par TEXTURE.

    Chaque partie porte son index de texture en +0x20 de son en-tete : valeurs
    0 a 6 pour sept descripteurs, et le format que le descripteur annonce
    concorde avec celui du mot TA de la partie sur les 80 parties de l'entree
    75. Les faces sont donc groupees par `usemtl`, et un .mtl accompagne l'OBJ.

    **On ne triangule que les rubans venus d'un EN-TETE.** Les rubans trouves
    par balayage ("repli") ou ramasses a la fin ("reste") ont des sommets
    justes mais une topologie DEVINEE : les relier produit des raccordements
    faux, bien visibles au sol. Leurs sommets sont ecrits quand meme, sans
    faces, pour qu'on voie ce qui manque sans salir la surface.
    `tout_trianguler` force l'ancien comportement.
    """
    chemin = pathlib.Path(chemin)
    sommets, uv, normales = [], [], []
    groupes = {}
    vues = set()          # centroides deja emis : evite les faces coincidentes
    # Faces deja emises, rangees par hauteur et par case : une copie issue de la
    # symetrie peut RETRIANGULER la meme surface -- memes pixels, sommets
    # differents -- et donner du z-fighting. On teste donc le RECOUVREMENT :
    # une face dont le centroide tombe dans une face deja emise, a la meme
    # hauteur, est ecartee.
    posees = {}

    def dans_une_face(cx, cy, cz):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    case = (round(cy / 0.02) + dy, round(cx / 0.5) + dx,
                            round(cz / 0.5) + dz)
                    for q in posees.get(case, ()):
                        (x1, z1), (x2, z2), (x3, z3) = q
                        d = (z2 - z3) * (x1 - x3) + (x3 - x2) * (z1 - z3)
                        if abs(d) < 1e-12:
                            continue
                        a = ((z2 - z3) * (cx - x3) + (x3 - x2) * (cz - z3)) / d
                        b = ((z3 - z1) * (cx - x3) + (x1 - x3) * (cz - z3)) / d
                        if min(a, b, 1 - a - b) > 1e-6:
                            return True
        return False

    def couvert(p0, p1, p2):
        """Vrai si la face est ENTIEREMENT recouverte par des faces deja posees.

        On teste le centroide et les trois milieux d'arete. Tester le seul
        centroide rejetait des faces qui ne faisaient que mordre sur une
        voisine, et rouvrait des trous.
        """
        pts = [((p0[0] + p1[0] + p2[0]) / 3, (p0[1] + p1[1] + p2[1]) / 3,
                (p0[2] + p1[2] + p2[2]) / 3)]
        for a, b in ((p0, p1), (p1, p2), (p2, p0)):
            pts.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2))
        return all(dans_une_face(*q) for q in pts)

    def pose(p0, p1, p2):
        cx = (p0[0] + p1[0] + p2[0]) / 3
        cy = (p0[1] + p1[1] + p2[1]) / 3
        cz = (p0[2] + p1[2] + p2[2]) / 3
        case = (round(cy / 0.02), round(cx / 0.5), round(cz / 0.5))
        posees.setdefault(case, []).append(((p0[0], p0[2]), (p1[0], p1[2]),
                                            (p2[0], p2[2])))
    base = 1
    nsur = ndevine = 0
    for debut, h, rubans in tout:
        itex = h.get("texture", 0)
        for ruban in rubans:
            code, pas, s = ruban[0], ruban[1], ruban[2]
            source = ruban[3] if len(ruban) > 3 else "entete"
            for v in s:
                sommets.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
                normales.append(f"vn {v[3]:.6f} {v[4]:.6f} {v[5]:.6f}")
                uv.append(f"vt {v[6]:.6f} {v[7]:.6f}")
            coupures = set(ruban[4]) if len(ruban) > 4 else set()
            # Couper aussi sur un SAUT DE POSITION aberrant : un ruban ne
            # bondit pas de centaines d'unites entre deux sommets quand son pas
            # courant vaut une fraction d'unite. Le critere est relatif a la
            # mediane du ruban, pour laisser intacts le sol et les plans
            # lointains, dont tous les pas sont grands.
            if len(s) >= 3:
                d = [sum((s[i][k] - s[i + 1][k]) ** 2 for k in range(3)) ** 0.5
                     for i in range(len(s) - 1)]
                med = sorted(d)[len(d) // 2]
                # La texture 1 (lasers) a des quads de 1024 x 0,27 : on la
                # laisse tranquille. Pour le reste, un pas qui vaut plus de
                # quatre fois la mediane du ruban ET depasse une unite est un
                # pont d'une branche a l'autre, pas une surface -- mesure sur
                # le tapis 0x12038, ou de tels triangles relient la branche -Z
                # a la branche +X en traversant le centre.
                if itex == 1:
                    seuil = max(100.0, med * 50) if med > 1e-9 else 100.0
                else:
                    # Critere ABSOLU, pas relatif. Mesure sur le tapis 0x12038 :
                    # les quads ne depassent jamais 2,71 unites entre deux
                    # sommets, tandis que les sept rubans longs portent un pas
                    # de 5 a 7 -- ce sont eux qui relient une branche de la
                    # croix a une autre. Un seuil en multiples de la mediane
                    # echangeait un defaut contre l'autre : trop serre il
                    # fendait les branches, trop large il laissait les ponts.
                    seuil = max(4.0, med * 2.5) if med > 1e-9 else 4.0
                for i, dd in enumerate(d):
                    if dd > seuil:
                        coupures.add(i + 1)
            if source == "entete" or tout_trianguler:
                nsur += len(s)
                faces = groupes.setdefault(itex, [])
                for i in range(len(s) - 2):
                    # ne pas relier par-dessus un changement d'etat
                    if (i + 1) in coupures or (i + 2) in coupures:
                        continue
                    p0, p1, p2 = s[i], s[i + 1], s[i + 2]
                    # Rejet des fuseaux : un triangle dont la plus longue arete
                    # vaut plus de 25 fois la plus courte n'est pas une surface,
                    # c'est un mauvais raccord. La texture 1 (les lasers) est
                    # exemptee : ses quads font 1024 x 0,27 par construction.
                    if itex != 1:
                        ar = [((p0[j] - p1[j]) ** 2 + (p0[j] - p1[j]) ** 2) for j in (0,)]
                        e = [sum((a[j] - b[j]) ** 2 for j in (0, 1, 2)) ** 0.5
                             for a, b in ((p0, p1), (p1, p2), (p2, p0))]
                        if max(e) > 25 * max(min(e), 1e-6):
                            continue
                    # Dedoublonnage par les SOMMETS, pas par le centroide : une
                    # copie issue de la symetrie a exactement les memes sommets,
                    # mais son centroide peut tomber de l'autre cote d'une borne
                    # de quantification et echapper au test. Les faces en double
                    # qui passaient ainsi donnaient du z-fighting -- les zones
                    # mouchetees du tapis.
                    k = tuple(sorted(tuple(round(q[j], 3) for j in (0, 1, 2))
                                     for q in (p0, p1, p2)))
                    kc = tuple(round((p0[j] + p1[j] + p2[j]) / 3 / 0.02)
                               for j in (0, 1, 2))
                    if k in vues or kc in vues:
                        continue
                    vues.add(k)
                    vues.add(kc)
                    pose(p0, p1, p2)
                    a, bb, c = base + i, base + i + 1, base + i + 2
                    if i & 1:
                        bb, c = c, bb
                    faces.append(f"f {a}/{a}/{a} {bb}/{bb}/{bb} {c}/{c}/{c}")
            else:
                ndevine += len(s)
            base += len(s)
    lignes = ["# Fighting Vipers 2 Dreamcast, extrait par geometrie_dc.py"]
    if noms_textures:
        lignes.append(f"mtllib {chemin.stem}.mtl")
    lignes += sommets + uv + normales
    nf = 0
    for itex in sorted(groupes):
        lignes.append(f"usemtl texture_{itex:02}")
        lignes += groupes[itex]
        nf += len(groupes[itex])
    chemin.write_text(NL.join(lignes) + NL, encoding="ascii")
    if noms_textures:
        mtl = []
        for i, entree in enumerate(noms_textures):
            nom, transparente = entree if isinstance(entree, tuple) else (entree, False)
            mtl += [f"newmtl texture_{i:02}", "Ka 1.000 1.000 1.000",
                    "Kd 1.000 1.000 1.000"]
            if transparente:
                # map_d porte le canal alpha : l'importateur branche la
                # transparence au lieu d'un quad opaque
                mtl += ["illum 4", "d 1.000", f"map_Kd {nom}", f"map_d {nom}"]
            else:
                mtl += ["illum 1", f"map_Kd {nom}"]
            mtl += [""]
        chemin.with_suffix(".mtl").write_text(NL.join(mtl), encoding="ascii")
    return len(sommets), nf, sorted(groupes), nsur, ndevine


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    indice = int(args[0])
    entete, tout = extrait(indice)
    rapport(indice, entete, tout)
    if "--anneau" in sys.argv:
        tout = retire_prototypes(tout)
        tout = complete_symetrie(tout)
        tout = replique_quart(tout)
        print(NL + "quart de ring replique aux trois autres quarts (RECONSTRUCTION)")
    if "--rapport" not in sys.argv:
        dossier = ICI / "geometrie_dc"
        dossier.mkdir(exist_ok=True)
        s = dossier / f"mdl_{indice:03}.obj"
        # l'appariement MDL <-> TEX vit dans textures_dc : il est global,
        # et deux entrees de meme taille ne doivent pas tomber sur la meme
        tex, k, liste = T.textures_de_lentree(indice)
        noms = []
        if tex is not None:
            noms = ecris_textures(dossier, tex, k, liste, f"mdl_{indice:03}")
            print(f"\nTEX_DAT[{k}] : {len(noms)} textures ecrites a cote de l'OBJ")
        nv, nf, groupes, nsur, ndevine = ecris_obj(
            s, tout, noms, "--tout" in sys.argv)
        print(f"{nv} sommets, {nf} triangles, {len(groupes)} materiaux {groupes}")
        print(f"   {nsur} sommets tringules (topologie sure), "
              f"{ndevine} ecrits sans faces (topologie devinee)")
        print(f"   -> {s.relative_to(ICI)}")
