# Fighting Vipers 2 (Sega Model 3) — notes de rétro-ingénierie

Documentation de découvertes sur la version **arcade** de *Fighting Vipers 2*
(Sega Model 3, Step 2.0, 1998), obtenues sous l'émulateur
[Supermodel](https://github.com/trzy/Supermodel), avec les outils qui ont
servi à les établir.

L'essentiel de ce qui suit ne figure ni sur The Cutting Room Floor, ni dans
les bases de codes de triche, ni dans les guides de la version Dreamcast.

---

## Sommaire

- [Le point de départ : un programme compressé](#le-point-de-départ--un-programme-compressé)
- [Découverte principale : le déblocage prévu par Sega](#découverte-principale--le-déblocage-prévu-par-sega)
- [Le roster réel](#le-roster-réel)
- [Débloquer tout le roster](#débloquer-tout-le-roster-un-octet-et-demi)
- [Jouer en anglais](#jouer-en-anglais)
- [Mode Survival](#mode-survival)
- [La table de décors et le décor d'entraînement](#la-table-de-décors-et-le-décor-dentraînement)
- [La résolution des identifiants de ressource](#la-résolution-des-identifiants-de-ressource)
- [Les ressources 2D de la Dreamcast](#les-ressources-2d-de-la-dreamcast-et-lécran-titre-du-19980605)
- [Les outils](#les-outils)
- [Questions ouvertes](#questions-ouvertes)
- [Portée et limites](#portée-et-limites)

---

## Le point de départ : un programme compressé

La première tentative naturelle — déinterleaver les ROM et chercher du code
PowerPC — ne donne rien. La CROM de *Fighting Vipers 2* ne contient aucune
chaîne lisible et aucun code exploitable, en dehors d'un court amorçage à
l'adresse de boot.

**Le programme est compressé et décompressé en RAM au démarrage** — et il
s'agit de **gzip**, pas de LZSS.

> **Correction du 2026-08-22.** Ces notes ont longtemps dit « LZSS », sur la
> foi de l'entrée `LZSS_INFO` du menu de test interne. L'étiquette de Sega ne
> décrit pas l'algorithme. La CROM commence, à l'offset 0, par un **fichier
> gzip complet** : magie `1f 8b`, méthode 8 (deflate), nom d'origine
> `foo.bin`, compressé le **26 mars 1998 à 16:01:08 UTC** sur un système Unix.
> 897 285 octets qui en donnent 2 701 982.
>
> Trois vérifications concordantes : les tables canoniques de DEFLATE sont
> dans l'amorçage en 16 bits big-endian (`cplens` `0xFFF03604`, `cplext`
> `0xFFF03642`, `cpdist` `0xFFF03680`) et le décompresseur est le
> `huft_build` de zlib ; `zlib.decompressobj(-15)` déroule le flux entier et
> **le CRC32 du pied gzip concorde** ; le contenu obtenu se pose en **RAM à
> l'adresse 0**, identique à 99,9 % à un relevé de RAM en cours de partie.

Deux conséquences pratiques, qui orientent toute la suite :

1. L'objet à analyser est l'**image décompressée**, pas la ROM brute. Chargée
   dans un désassembleur en PowerPC big-endian, base 0, elle donne du code
   lisible — et les adresses documentées par The Cutting Room Floor y tombent
   juste. On l'obtient soit d'un relevé de RAM, soit directement du zip.
2. **Le patch permanent de la ROM est possible.** Il n'y a rien à reverser :
   on décompresse, on modifie, on recompresse avec la bibliothèque standard.
   Le gzip d'origine fait 897 285 octets, celui que produit Python en niveau 9
   pour le même contenu en fait 882 022 — **15 263 octets de marge**, donc un
   patch tient à la même place. Reste une seule marche, ré-entrelacer la CROM
   sur les quatre EPROM pour reconstruire un zip jouable.

### Obtenir l'image RAM

Deux voies, l'une hors ligne, l'autre en direct. Dans les deux cas la RAM est
stockée **mots de 32 bits inversés** : un byte-swap 32 est nécessaire pour
relire du PowerPC big-endian.

**Depuis une sauvegarde d'état Supermodel** (format CBlockFile) : chaque bloc
commence par trois entiers 32 bits little-endian — offset du bloc suivant,
longueur du nom, longueur du commentaire — suivis du nom, du commentaire,
puis des données. Le bloc utile est `"Model 3"`, et **la RAM commence à
l'offset `0x10` du bloc**, pas à son début. Avec ce décalage, l'offset dans
le fichier est directement l'adresse PowerPC.

**Depuis le processus en cours** : la build `0.3a-20251120` x64 conserve un
pointeur vers la base RAM à `Supermodel.exe + 0x65D098`. Attention, Supermodel
**réalloue son pool mémoire après le chargement des ROM** — un outil qui lit
ce pointeur une seule fois au démarrage obtient une base périmée et écrit
dans le vide, sans qu'aucune erreur ne le signale.

---

## Découverte principale : le déblocage prévu par Sega

*Fighting Vipers 2* contient un mécanisme complet de déblocage progressif des
personnages cachés, jamais documenté pour la version arcade.

### La manipulation

Sur l'écran de sélection, curseur du joueur 1 sur **Emi** (la première case) :

> **pousser vers le haut, maintenir, puis basculer en diagonale haut-gauche**

Un second point d'entrée équivalent existe depuis la **case 10** — le slot
sans personnage, en fin de rangée — avec un mouvement haut puis haut-droite.

La manipulation n'est valide que **tôt dans le décompte** de l'écran de
sélection : le code exige que le compteur soit encore au-dessus d'un seuil.

Le « bouton » du code est en réalité une **direction**. C'est ce qui explique
qu'il soit resté invisible : sur un clavier, maintenir haut et presser gauche
comme deux touches séparées ne vient pas à l'esprit, et le mouvement n'a de
sens qu'au stick. C'est aussi pourquoi il ne valide aucun personnage au
passage.

### La progression, en trois étapes

Le code de déplacement du curseur comporte trois branches, choisies par deux
drapeaux de progression :

| État | Rangée accessible | La manipulation donne |
|---|---|---|
| initial | 0–10 | **Del Sol** |
| premier drapeau posé | 0–11 | rien — Del Sol est acquis |
| les deux drapeaux posés | 0–11 | **Kuhn** |

Une fois débloqué, **Del Sol devient une case permanente**, atteinte en
rebouclant à gauche depuis Emi. **Kuhn ne le devient jamais** : la borne de
rebouclage passe de 10 à 11 mais ne va jamais à 12. Kuhn occupe donc
momentanément la case d'Emi et disparaît dès que le curseur bouge — il est
transitoire par conception, à redéclencher à chaque fois.

Un **verrou à usage unique** neutralise le bloc dès qu'une manipulation a
réussi, ce qui interdit un second déblocage dans la même session.

### Le déblocage de Kuhn est orphelin sur arcade

Le drapeau qui ouvre la troisième étape **n'est écrit nulle part dans la
ROM** : l'analyse ne trouve qu'une seule référence, en lecture, par le code
du curseur. La branche existe, aucun chemin de jeu ne l'active.

C'est très probablement la raison pour laquelle aucun code Kuhn n'a jamais
été documenté sur borne : il n'y en a pas. Le premier drapeau, lui, est bien
écrit, sous condition de seuil sur un compteur.

Sur **Dreamcast**, le déblocage est complet et documenté : battre Mahler au
stage 7 sous un temps donné avec assez de vie ou par Super K.O. ouvre un
stage bonus, où battre Kuhn le débloque. L'hypothèse la plus simple est que
Sega a terminé ce système pour le portage console en laissant la version
arcade à mi-chemin.

### Adresses

| Rôle | Adresse |
|---|---|
| Curseur de sélection, joueur 1 | `0x00279668` |
| Curseur de sélection, joueur 2 | `0x00279669` |
| Verrou du code secret | `0x00279691` |
| Drapeau « Del Sol acquis » | `0x0011F061` |
| Drapeau « Kuhn disponible » | `0x0011F06F` |
| Drapeau désactivant le bloc secret | `0x0011F060` |
| Compteur de l'écran de sélection | `0x00581408` |
| Gestionnaire de déplacement du curseur | `0x0005F340` |

Le compteur affiché à l'écran se déduit du demi-mot en `0x0058140A` décalé de
6 bits vers la droite. Le recharger à une valeur inférieure à 99 une fois
affichée permet de travailler sans être éjecté — **sans jamais le figer** :
le jeu le décrémente lui-même, et l'immobiliser bloque les transitions
d'écran.

---

## Le roster réel

Le jeu manipule **deux numérotations distinctes**, ce qui est une source de
confusion tenace.

**La position du curseur** sur l'écran de sélection : Emi 0, Bahn 1, Picky 2,
Jane 3, etc. La case 10 est un slot aléatoire sans personnage. Del Sol, Kuhn
et BM occupent 11, 12 et 13.

**L'identifiant du personnage en combat**, lisible en `0x007005B8` pour le
joueur 1 et `0x007075B8` pour le joueur 2, qui suit une liste de chaînes
interne :

| | | | |
|---|---|---|---|
| 0 Grace | 1 Bahn | 2 Raxel | 3 Tokio |
| 4 Sanman | 5 Jane | 6 Honey | 7 Picky |
| 8 Mahler | 9 BM | 10 Charlie | 11 Techno |
| 12 Dural | 13 Kuhn | 14 Del Sol | **15 Kuma** |

La conversion entre les deux se fait par une table de 15 octets en
`0x000B16B8`.

Deux enseignements :

**L'identifiant 15 est Kuma**, l'ours du stage bonus — jouable en forçant
l'identifiant, bien que manifestement jamais prévu pour. L'identifiant 16
fige le jeu : la liste des combattants s'arrête là, les entrées suivantes
étant des noms d'animations.

**Dural est l'ancien nom de Kuhn.** Les identifiants 12 et 13 chargent le
même personnage. Kuhn étant l'androïde copieur de la série, il a
vraisemblablement porté le nom du boss de *Virtua Fighter* pendant le
développement, avant d'être renommé — les deux entrées ont subsisté.

**BM n'a pas de nom affichable** : son entrée dans la table d'identifiants de
texte est nulle. Sega ne lui en a jamais attribué, ce qui est cohérent avec
un personnage jamais destiné à être sélectionnable.

---

## Débloquer tout le roster : un octet et demi

Le gestionnaire de curseur possède un mode « roster étendu », où le curseur
reboucle sur 14 au lieu de 10 — rendant Del Sol, Kuhn, BM et Kuma tous
accessibles à la flèche, et **permanents**.

Ce mode est conditionné par la pression simultanée des **deux boutons
opérateur** (Service et Test). Inexploitable à la main, puisque Test ouvre le
menu de service. La variable testée n'est pas un drapeau de progression mais
l'**état brut du port d'entrée matériel**, rafraîchi à chaque image : y
écrire ne sert à rien.

En revanche, la comparaison elle-même se patche :

```
0x0005F3BC :  2C 80 00 C0   (cmpwi r0,192)
           →  2C 80 00 00   (cmpwi r0,0)
```

La condition devient vraie quand aucun bouton opérateur n'est pressé, donc en
permanence.

**Deux précautions indispensables.** Le jeu recharge cette portion de code, il
faut donc réappliquer le patch — mais **uniquement après avoir relu
l'instruction d'origine à l'adresse visée**. Écrire à l'aveugle pendant le
démarrage corrompt une zone pas encore décompressée et fait diverger le
processeur émulé.

Limite connue : au-delà de l'indice 10, les noms et portraits sont faux ou
absents. La routine d'affichage refuse de dessiner au-delà, et sa table de
positions ne compte que 11 entrées.

---

## Jouer en anglais

La ROM disponible est la révision japonaise. Le menu de test affiche bien un
réglage `COUNTRY`, mais **en lecture seule** — contrairement aux autres
réglages de la même page, qui s'éditent normalement.

Le verrou est dans l'interface du menu, pas dans la logique du jeu. La région
est un simple octet :

```
0x00120557 :  0 = Japan   1 = U.S.A.   2 = Export   3 = Asia
```

L'écrire fonctionne, le jeu ne le réécrit pas, et les textes passent en
anglais. Un écran d'avertissement absent de la version japonaise apparaît
alors — preuve d'un vrai changement de région, et pas d'un simple changement
d'étiquette.

La sauvegarde NVRAM ne contient pas ce réglage sous une forme directement
reconnaissable ; le rendre permanent hors émulateur demanderait de décoder
l'encodage de la mémoire de sauvegarde.

---

## Mode Survival

Écrire 1 en **`0x0058145F`** (avec le réglage correspondant à 1 en
`0x00120550`) bascule le jeu en mode Survival — la mention s'affiche en haut
à gauche de l'écran.

Le mode **Versus** n'existe pas comme mode distinct : dans *Fighting Vipers
2*, c'est le mode arcade avec un second joueur qui s'incruste. Il n'y a pas
de mode **Training**.

### Le menu de debug, une mine

Le jeu conserve les tables du menu de test interne de Sega, où chaque entrée
associe un libellé à l'adresse de sa variable. C'est la **documentation
interne des développeurs**, restée dans la ROM : on y récupère leurs propres
noms sans rien deviner — énergie, temps de round, drapeaux de stage bonus,
identifiants de personnages, réglages d'affichage.

Structure d'une entrée, longue de `0x20` octets : pointeur vers le libellé en
tête, adresse de la variable à l'offset `0x0C`, type à l'offset `0x1C`. Quand
l'octet de poids fort du type vaut `0x10`, le champ `0x0C` est un index et non
une adresse.

Le fichier `symbols.csv` fourni ici recense 84 symboles, dont 56 issus de ces
tables.

---

## La table de décors et le décor d'entraînement

Mesuré le 2026-10-20 sur l'image du programme arcade et sur le `1ST_READ.BIN`
de la version Dreamcast, en cherchant les références aux pointeurs de noms de
décors. Cette table n'est documentée nulle part ailleurs.

**27 enregistrements de `0x70` octets**, dans l'ordre de la liste de noms, et
les deux versions la rangent au même endroit logique :

| | arcade | Dreamcast |
|---|---|---|
| table | RAM `0x00075170` | fichier `0x0010763C` |
| noms | `0x000887D9` | `0x000CD1D4` |
| base de chargement | 0 | `0x8C010000` |

Les noms sont les mêmes des deux côtés, dans le même ordre : `TEST`, `WESTERN`,
`AC_CARRIER`, `ROOM_00`, `GREAT_BM`, `FURNACE`, `STORE`, `HANGAR`, `CAPSULE`,
`DAM`, `TOWER`, `BUILDING`, `MUSEUM`, puis `FINISH00` à `FINISH05`, les sept
`ADV_*` de l'attract mode, et `SELECT`.

### Les champs

```
+0x00  pointeur vers le nom
+0x04  pointeur vers une liste d'octets, partagée entre plusieurs décors
+0x08  pointeur vers la liste de ressources — 8 identifiants, voir plus bas
+0x0C ) jusqu'à trois pointeurs de code (arcade : 0x00018424-0x00018CC4).
+0x10 ) TEST n'en a aucun, WESTERN deux, TOWER et BUILDING utilisent +0x0C.
+0x18 ) Candidats pour les objets interactifs et destructibles.
+0x1C  pointeur vers des listes d'octets (arcade 0x001154B0-0x001155CE)
+0x20  pointeur vers un bloc de 0x1F8 octets, un par décor, dans l'ordre
+0x24  identique pour les 27 : un bloc commun
+0x28  identique pour les 27 : le même
+0x2C  5.0f, identique pour les 27
+0x30..+0x48  flottants de caméra (distances et limites)
+0x4C..+0x54  petits flottants, souvent nuls
+0x58  0.0040833f, identique pour les 27
+0x5C  paires de couleurs, très variables
+0x60  un index (0x27-0x3A) en poids fort, 0xFF en poids faible — rôle non établi
+0x64  ARGB : brouillard ou ambiance (TEST : 0xFFAA0000, unique)
+0x68  0x000001FF, ou 0x010001FF pour TOWER et BUILDING
+0x6C  3, identique pour les 27
```

Le bloc de `0x1F8` octets pointé par `+0x20` contient une famille de triplets
de plans normalisés (±0.05, ±1.083, ±0.05) : collision ou cage, **non prouvé**.

### Le champ qui tranche : `+0x08`

La liste de 8 identifiants qu'il pointe est **entièrement audio**. Son
quatrième créneau porte la **musique** du décor, et c'est là, et seulement là,
que les deux versions divergent :

| décor | arcade | Dreamcast |
|---|---|---|
| **TEST** | **`0x00000000` — vide** | **`0x001800F0` — index 24** |
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

Les douze décors de combat portent le même index des deux côtés. L'énumération
complète du genre se lit en clair dans les deux images :

- arcade `0x000EC048` : `00A01000` … `00A01013`, **20 créneaux (0–19)**
- Dreamcast `0x00102420` : `000000F0` … `001800F0`, **25 créneaux (0–24)**

La Dreamcast a donc **ajouté cinq morceaux**, et `TEST` pointe sur le dernier
des cinq. Les trois premiers créneaux de la liste sont identiques dans les 27
enregistrements — des banques d'effets communes — et les créneaux 4 et 5 sont
une paire d'effets propre au décor, nulle pour `TEST`.

**`TEST` est le décor d'entraînement, et il n'existe que sur Dreamcast.**
Cohérent avec le reste de ce qui n'existe que sur console : `EMI` à l'indice 11
à la place de `TECHNO` et `DURAL`, le déblocage de Kuhn complété.

L'arcade porte **tout le reste** du décor : son nom, son enregistrement entier,
ses paramètres de caméra, sa couleur de brouillard, son bloc de `0x1F8`.

---

## La résolution des identifiants de ressource

Le point dur du chantier. Ghidra ne voyait rien : le binaire n'est désassemblé
qu'à 32,4 %, aucune fonction ne référençait ces tables, et la table de décors
n'est pointée par **aucun littéral**. La réponse est venue d'un balayage
d'octets, qui ne cherche pas à prouver que c'est du code — il le lit.

### La disposition, et l'erreur qu'elle a coûtée

Un identifiant de ressource se lit sur **trois champs**, pas deux :

```
 31                    16 15         8 7         0
+------------------------+------------+-----------+
|         index          | sous-genre |   genre   |
+------------------------+------------+-----------+
```

L'énumération des musiques est parfaitement régulière — `000000F0`,
`000100F0`, … `001800F0` — ce qui donne un découpage 16/16 très convaincant et
**faux**. Il tient tant que le sous-genre vaut 0, et il tombe dès `0x000803A9`
et `0x000604A9` : ce ne sont pas deux genres voisins mais **un seul**, `0xA9`,
avec les sous-genres 3 et 4.

Ce qui tranche n'est pas la régularité de la table, c'est le répartiteur.

### Le répartiteur : `0x8C047C9E`

Un argument, l'identifiant. Il extrait le bas octet et compare :

```
extu.b r11,r0        ; r0 = id & 0xFF
cmp/eq #0xA9   ->  0x8C047CCA
cmp/eq #0xFF   ->  0x8C047D44
cmp/eq #0xF0   ->  0x8C047E54
sinon              0x8C047E68   (rien)
```

Trois genres, et trois seulement.

**Genre `0xF0` — musique.** La branche fait `shlr16` puis `extu.b` : l'index
est bien en haut. Elle aboutit à `0x8C0479E8`, qui réserve 284 868 octets,
remet un flottant de volume à zéro, et lit la partition **4** —
`adx_dat.afs`. Les 13 indices employés par la table de décors sont tous des
flux **CRI ADX** valides, 44 100 Hz stéréo, marque `(c)CRI` en place. Celui du
décor d'entraînement, l'index 24, est le plus long de l'archive : 11,97 Mo.

**Genre `0xA9` — effets sonores.** Masque `0x0000FF00` puis `shlr8` : c'est le
sous-genre qui sert. La branche aboutit à `0x8C0C1D20`, qui écrit
l'identifiant dans un anneau de `0xA0800400` à `0xA0800500` et reboucle au
début. C'est la RAM de l'**AICA**, par le bus G2 — une file de commandes vers
le processeur sonore.

**Genre `0xFF`.** Une chaîne de `cmp/eq` sur `id & 0x00FF00FF`, écrite à la
main, un cas par index.

### Le système de fichiers est celui de CRI

Les cinq archives sont des **partitions ADXF**, le système de fichiers de CRI —
« AFS » veut dire *ADX File System*. La bibliothèque laisse ses noms de
fonctions dans ses messages d'erreur, ce qui nomme toute la couche d'un coup :

| | |
|---|---|
| `ADXF_LoadPartition` | `0x8C12BA6A` |
| `ADXF_Open` | `0x8C12BE4E` |
| `ADXF_GetFileRange` | `0x8C12C5E0` |
| table des partitions | `0x8C3DE0B8`, 256 pointeurs indexés par `ptid` |
| nombre de fichiers | `+0x0C` du descripteur de partition |

Versions présentes : `ADXF Ver.5.55 Build:Sep 08 1999` et
`ADXT Ver.5.76 Build:Jan 28 2000`.

L'enregistrement se fait en une boucle, à `0x8C028988`, qui recopie deux
tableaux de cinq mots vers la pile puis appelle `ADXF_LoadPartition` cinq fois.
Les deux tableaux :

| `ptid` | nom, `0x8C0CD278` | entrées utiles, `0x8C0CD28C` | mesuré dans l'archive |
|---|---|---|---|
| 0 | `mot_dat.afs` | 1 | — |
| 1 | `mdl_dat.afs` | 77 | 78 entrées |
| 2 | `tex_dat.afs` | 114 | 115 entrées |
| 3 | `snd_dat.afs` | 35 | — |
| 4 | `adx_dat.afs` | 25 | 26 entrées |

L'écart d'une unité n'est pas une erreur : **la dernière entrée de chaque
archive est un terminateur de taille nulle.** Vérifié sur les trois archives
lisibles. `mdl_dat` porte donc 77 entrées utiles, 0 à 76, et l'entrée 75 du
décor d'entraînement est bien dedans.

Quatre fonctions quasi identiques lisent une partition chacune, et l'immédiat
chargé dans `r4` les nomme :

| site d'appel | `ptid` | archive |
|---|---|---|
| `0x8C029B2E` | 0 | `mot_dat` |
| `0x8C02A750` | **1** | **`mdl_dat`** (fonction `0x8C02A5A8`) |
| `0x8C02B6BA` | **2** | **`tex_dat`** |
| `0x8C0474FA` | 3 | `snd_dat` |

Sega a aussi laissé le vidage de debug de la table : la chaîne de format
`"%2d:%d %08X %08X %4d [%s]\n"` à `0x8C0CD544`, chargée par l'instruction à
`0x8C02BA9A`, avec `"File Open Error"` juste au-dessus.

### Quelle entrée porte quel décor, mesuré avant de le lire

Le code ne le dit pas, alors on l'a mesure. `retrouver.py` retrouve une texture
dumpee d'emulateur parmi les 3 709 du disque par signature ; une seule texture
ne tranche pas, parce qu'un ciel ou un sol sert a plusieurs decors et tombe a
l'ecart 0,0 dans deux entrees. `decor_vers_entree.py` fait donc **voter tout un
dossier de dump** : chaque image vote pour chaque source ou elle se retrouve a
l'ecart minimal, et l'entree qui porte le decor rafle les voix.

| relevé | entrée MDL | entrée TEX | voix | nom interne probable |
|---|---|---|---|---|
| Great Museum | **55** | 78 | 50 / 50 | `MUSEUM` |
| Serpent's Cage | **68** | 100 | 19 / 19 | `CAPSULE` |
| Hanger of the Dark Royal | **39** | 62 | 17 / 17 | `HANGAR` |
| Training Zone | **75** | 112 | 7 / 7 | `TEST` |
| Deck of the Dark Royal | **0** | 0 | 7 / 7 | `AC_CARRIER` |
| Terror Furnace | **34** | 56 | 3 / 3 | `FURNACE` |
| Cross River Damsite | **26** | 33 | 2 contre 1 | `DAM` |
| The Great B.M | **33** | 55 | 1 | `GREAT_BM` |
| Old Armstone Town | **76** | 113 | 1 | `WESTERN` |

Les cinq premieres lignes sont unanimes et sans concurrente. Le decor
d'entrainement ressort a MDL 75 / TEX 112 **independamment** de la premiere
mesure, qui avait pris un autre chemin : c'est ce qui valide la methode. Les
trois dernieres lignes tiennent a une ou deux images -- plausibles, pas
etablies.

La colonne « nom interne » est une lecture, pas une mesure : le binaire ne
porte que les noms internes (`0x8C0DD1D4`, douze octets par creneau, dans
l'ordre de la table de decors), et les noms d'affichage sont des textures.

**Les decors ne sont donc pas les entrees 0 a 15**, comme je l'avais suppose.
Ils sont disperses : 0, 26, 33, 34, 39, 55, 68, 75, 76.

Recoupement independant : l'en-tete d'une entree MDL porte en `+0x00` sa classe,
`1` pour un decor et `-1` pour un personnage. Sur les 77 entrees utiles, 43 sont
de classe decor et 34 de classe personnage -- et **les neuf entrees retrouvees
ci-dessus sont toutes de classe decor**, sans exception.

Quatre decors manquent -- `ROOM_00`, `STORE`, `TOWER`, `BUILDING` -- et il reste
exactement quatre releves sans correspondance : Marble Arena, Neo Armstone City
Tower, Secret Chemical Plant, The Skies of Armstone. Les trois premiers n'ont
pas de texture Dreamcast dans le relevé, le quatrieme en a treize qui ne sont
pas sur ce disque : ce sont des textures de la version arcade.

### La table qui manquait : `0x8C118294`

Elle est dans le code, et elle donne la reponse en clair. **35 enregistrements
de `0x34` octets**, juste apres la table de decors :

| champ | contenu |
|---|---|
| `+0x00` u32 | indice d'entrée dans `mdl_dat.afs` |
| `+0x04` u32 | indice d'entrée dans `tex_dat.afs` |
| `+0x08` u32 | une taille |
| `+0x0C`, `+0x10` | deux pointeurs, zone `0x8C112xxx` |
| `+0x30` u32 | `0xFFFFFFFF`, ou `0xFFFF00xx` pour les treize premiers |

Le rang est l'index de la table de décors, et les blocs se lisent :

- **0 à 12** : les treize décors réels
- **13 à 18** : `FINISH00` à `FINISH05`, soit MDL 28 à 33, consécutifs
- **19 à 26** : les sept `ADV_*` et `SELECT` — les paires `_2` tombent bien par deux
- **27 à 34** : huit scènes au-delà de la table de décors

| rang | nom interne | MDL | TEX |
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

### Pourquoi elle etait invisible, et ce qui l'a rendue visible

La table n'est atteinte que par adresse calculée, et l'index arrive dans une
variable en RAM. Les vingt-cinq références à l'installateur de créneau
(`0x8C02A2A0`) sont **toutes** des `COMPUTED_CALL`. Ghidra ne pouvait donc pas
les montrer tant que les littéraux n'étaient pas typés : c'est en posant les
noms établis par le balayage d'octets que le graphe s'est refermé et que les
appels ont apparu.

L'enchaînement se lit alors d'un coup. Le chargeur de créneau
(`0x8C02A39E`) fait trois choses et rien d'autre : il pose un drapeau dans un
tableau de mots indexé par le créneau, appelle `0x8C02985E` avec le créneau
**plus cinq** — le même décalage que les `add #-5` du répartiteur de ressource
— puis passe la main au chargeur de modèle. Et son appelant lui donne
`base + index * 0x34`, où `base` est cette table.

### Les deux mesures se recoupent

Les neuf décors avaient été appariés **avant**, par signature de texture, sans
toucher au code. Sept tombent exactement sur la diagonale rang = index du
décor : `TEST` 75/112, `WESTERN` 76/113, `AC_CARRIER` 0/0, `FURNACE` 34/56,
`HANGAR` 39/62, `DAM` 26/33, `MUSEUM` 55/78.

Et sur les **26 paires MDL ↔ TEX** que l'appariement par pavage exact couvrait,
la table du jeu n'en contredit **aucune**. L'heuristique de pavage est donc
validée sur tout son domaine.

Deux corrections, toutes les deux de mon côté :

- Serpent's Cage est `STORE`, pas `CAPSULE` — c'était une lecture de nom, pas
  une mesure, et elle était fausse.
- Mon résultat le plus faible, une seule image pour The Great B.M, donnait
  MDL 33. La table place MDL 33 en `FINISH05` et `GREAT_BM` au rang 4, donc
  MDL 35. L'image tombe pourtant à l'écart 0,0 sur MDL 33, la suivante à 205 :
  ce n'est pas une égalité mal tranchée, la texture vit vraiment là. Elle vient
  donc probablement de la scène de fin et pas du décor — mais avec une seule
  image, ça ne se tranche pas.

**La leçon.** La mesure a trouvé la réponse la première, et le code l'a
confirmée puis corrigée là où la mesure était la plus mince. Aucune des deux
n'aurait suffi : neuf voix de texture ne donnent pas la structure de la table,
et la table seule ne dit pas lequel de ses rangs est quel décor visible.

### Ce qui reste inconnu

**Ce que porte le champ `+0x08` de la table de ressources de scène**, et à quoi
servent ses deux pointeurs vers la zone `0x8C112xxx`. La taille ne correspond
ni à celle de l'entrée MDL ni à celle de l'entrée TEX.

**Qui écrit l'index de scène** en RAM (`0x8C1F56CF` sur le chemin de
`0x8C034D1C`). L'appariement décor → entrée est établi, mais le pas d'avant —
ce qui décide du rang — ne l'est pas.

### Trois leçons de méthode

**Une table de noms ne dit rien du contenu.** Les listes de noms des deux
versions sont identiques nom pour nom, ce qui a d'abord fait conclure qu'aucun
décor n'était exclusif. C'est faux : une liste de noms énumère les créneaux
*prévus*, pleins ou vides. Il faut suivre chaque enregistrement jusqu'à sa
charge utile.

**Les identifiants de ressource ne sont pas des adresses.** Les `0x00A0xxxx`
déroulés comme des modèles Real3D avec `model3d.py` échouent dès le premier
polygone, sur la norme de la normale de face.

**Une régularité n'est pas un format.** L'énumération des musiques se découpe
en 16/16 sans la moindre fausse note, et ce découpage est faux. Le champ ne
s'est montré que dans le `extu.b` du répartiteur. Une table qui confirme une
hypothèse sur tous ses éléments peut n'en confirmer qu'un cas particulier :
c'est le code qui dit le format, pas les données.

---

## Les ressources 2D de la Dreamcast, et l'écran-titre du 1998.06.05

Le port Dreamcast dessine tout son habillage — logos, menus, bannières,
police, staff roll — par un seul couple de fonctions et deux niveaux de
tables. Le mécanisme se lit entièrement dans `1ST_READ.BIN`, et il livre au
passage l'appariement MDL ↔ TEX que l'on obtenait jusqu'ici par la taille.

### L'enregistrement de ressource : 16 octets, et l'indice en clair

À la suite de chaque tableau de descripteurs de texture, dans la zone
`0x8C0E4000`–`0x8C0E9000`, se trouvent des enregistrements de 16 octets :

```
+0x00  u32  indice de l'entrée dans TEX_DAT.AFS
+0x04  u32  pointeur vers le tableau de descripteurs de texture
+0x08  u32  pointeur vers la liste de motifs
+0x0C  u32  mot de fin
```

**36 enregistrements**, et le premier champ est l'indice TEX écrit en clair.
Il remplace l'appariement par pavage de tailles : plus besoin de parcourir les
entrées MDL dans l'ordre en prenant la première entrée TEX encore libre, ni de
craindre le piège des deux costumes de même taille. La vérification est
immédiate — les six enregistrements de la banque `0x8C0E4A9C` portent 24, 25,
26, 28, 27, 29 ; les cinq de `0x8C0E4CC0` portent 101, 103, 102, 105, 104.

Il nomme aussi les banques que l'heuristique de taille laissait sans entrée :

| banque | entrées TEX |
|---|---|
| `0x8C0E64FC` | 81, 82, 83, 84, 85 |
| `0x8C0E6B14` | 57 |
| `0x8C0E7900` | 49 |
| `0x8C0E7C2C` | 93 |

### La liste de motifs : des enregistrements de 10 octets

Le pointeur `+0x08` mène à une liste de **motifs**, chacun un rectangle
découpé dans une des textures de la banque :

```
+0x00  u16  rang du descripteur dans le tableau de la banque
+0x02  u16  x
+0x04  u16  y
+0x06  u16  largeur
+0x08  u16  hauteur
```

Un motif se désigne par son **rang dans la liste**, pas par son adresse.

Ce qui établit le pas de 10 — et non 8 ou 16 — n'est pas la régularité
apparente mais le pavage : pour l'entrée TEX 16, la liste va de `0x8C0E5808`
à `0x8C0E5BC8`, soit 960 octets, **exactement 96 enregistrements**, et les
96 rectangles tombent dans les bornes du descripteur qu'ils citent, sans une
seule exception. Pour l'entrée TEX 97 : 1 220 octets, 122 enregistrements,
zéro hors bornes.

L'entrée TEX 16 est tout l'habillage de la façade :

| rangs | descripteur | contenu |
|---|---|---|
| 0–2, 9 | 2 | `Presented by SEGA`, AM2, ADX, `Copyright © 1996,1998 CRI` |
| **3–8** | **6–11** | **le logo de l'écran-titre, mosaïque 3×2 de tuiles 256×256** |
| 10–18 | 18 | `ARCADE`, `V.S.`, `INTERNET`, `RANDOM NETWORK`, `SURVIVAL`, `TRAINING VS`, `OPTIONS` |
| **19–25** | **12–17** | **un second logo, inerte — voir plus bas** |
| 26–29 | 1 | bannières `RANKING`, `VICTORY STREAK`, `SURVIVAL MODE`, `BEST TIME` |
| 30–95 | 0, 3, 4, 5 | la police, les noms du roster, le staff roll |

### Les deux fonctions

| adresse | rôle |
|---|---|
| `0x8C02A23A` | `charge_ressource(enregistrement)` — pose la ressource **courante** |
| `0x8C029598` | `dessine(rang, x, y)` — le rang est dans **R4**, x dans R5, y dans R6 |

`dessine` ne reçoit pas la ressource : elle travaille sur celle que le dernier
`charge_ressource` a posée. Toute lecture de ces appels doit donc suivre
l'**ordre d'exécution**, pas seulement le graphe.

L'établissement tient en une fonction, `0x8C019CBC` :

```
mov.l #0x8C0E5BC8,R4 ; jsr @Rn      charge la ressource de l'écran-titre
mov #3,R4 ; jsr @Rn   (x=0,   y=0)
mov #4,R4 ; jsr @Rn   (x=256, y=0)
mov #5,R4 ; jsr @Rn   (x=512, y=0)
mov #6,R4 ; jsr @Rn   (x=0,   y=256)
mov #7,R4 ; jsr @Rn   (x=256, y=256)
mov #8,R4 ; jsr @Rn   (x=512, y=256)
```

Six rangs, six positions : la mosaïque 3×2 de 768×512 du logo. Les positions
recoupent le découpage des tuiles, obtenu séparément par le décodage des
textures.

### Le logo « 1998.06.05 SPECIAL VERSION »

Les descripteurs **12 à 17** de la banque `0x8C0E56C8` décrivent six tuiles de
256×256 en ARGB1555 non compressé, à `0x615800`–`0x6B5800` de `TEX_DAT.AFS`,
786 432 octets en tout. Assemblées, elles donnent un second écran-titre :
le même logo `FV2 / FIGHTING VIPERS 2` sur fond rouge au lieu de noir, sans le
`™`, et portant deux lignes supplémentaires — **`1998.06.05  SPECIAL VERSION`**.

C'est l'écran-titre de la version événementielle de juin 1998 de la borne
Model 3, resté entier sur le disque Dreamcast de 2001.

Ce n'est pas du rebut collé après le tableau. Les six descripteurs sont dans
l'unique tableau de l'entrée 16, qui pave l'entrée à l'octet près
(2 566 144 = 2 566 144), donc les tuiles sont téléversées en VRAM avec les
autres à chaque affichage de la façade. Et elles ont leurs **motifs déclarés**,
rangs 19 à 25, au même format et avec le même découpage plein cadre que les
six du logo retail.

**Rien ne les dessine.** Le relevé est complet, et il est fermé par trois
mesures qui ne laissent pas d'angle mort :

*Les sites qui touchent la ressource.* Le littéral `0x8C0E5BC8` apparaît
**exactement 11 fois** dans le fichier, et Ghidra les voit toutes : il n'existe
aucun pool caché dans la partie non désassemblée. Treize sites s'en servent,
tous lus. Sept ne font qu'un `f(1, ressource)` d'enregistrement. Les six
autres dessinent, et voici tous les rangs qu'elles demandent :

| fonction | rangs |
|---|---|
| `0x8C019CBC`, `0x8C01CBC8` | 3, 4, 5, 6, 7, 8 |
| `0x8C019D18` | 17, 18 |
| `0x8C01CC28` | 0, 1, 83, puis une table (ci-dessous) |
| `0x8C0A6874` | 26, 27, 28, 29, 31, 33 |

*L'aiguillage de l'écran-titre.* `0x8C020C24` est une machine à états : une
chaîne de `cmp/eq` sur un état lu en RAM, cases 0 à 7 et 11 à 15. Quatre
états — **0, 3, 5 et 7** — entrent dans le bloc du logo, et les quatre
chargent la **même adresse constante** depuis le pool, `0x8C019CBC`, suivie
d'un `jsr`. Le dessineur n'est pas choisi par un index dans une table de
variantes, ni par un drapeau : il n'existe aucun créneau où une version
spéciale pourrait se brancher. Le trou des états 8, 9 et 10 n'est pas une
amputation — ils sont traités par un aiguillage voisin de la même famille.

*Le seul rang calculé.* Dans `0x8C01CC28`, la branche `param ≥ 16` lit son
rang par `mov.w @(R0,R10),R4`, ce que le décompilateur rend relatif au cadre
de pile. La base n'est pas en RAM : le prologue recopie **trois tables
statiques de 20 octets** sur la pile, par trois appels au `memcpy` du jeu.

| source | rôle | contenu |
|---|---|---|
| `0x8C0CCC74` | rang | 79, 80, 81, 82, 84, 85, 86, 87, 88, 89 |
| `0x8C0CCC4C` | x | 185, 170, 170, 170, 172, 172, 172, 173, 172, 129 |
| `0x8C0CCC60` | y | 212, 187, 158, 137, 152, 152, 152, 168, 57, 212 |

Les rangs 79 à 89 pointent les descripteurs 3, 4 et 5 : les planches du
**staff roll**. Aucune valeur entre 19 et 25.

Enfin, aucune chaîne : `1998.06.05`, `19980605`, `SPECIAL`, `EVENT`,
`LIMITED`, `GABBA`, et leurs équivalents japonais `特別版`, `スペシャル`,
`イベント`, balayés en latin-1, UTF-16LE et Shift-JIS sur les
**721 012 628 octets** de l'image `.cdi` entière, bourrage compris — zéro
occurrence. Ce n'était pas une piste sérieuse : les archives AFS n'ont aucun
bloc de noms (le mot qui suit la table vaut `(0, 0)`), aucune texture du
disque ne porte de nom, et tout le texte à l'écran est en image.

**Conclusion.** L'image, ses six descripteurs et ses sept motifs sont sur le
disque, complets et conformes. L'ordre de les dessiner a été retiré, et il
n'en reste aucune trace exécutable. Douze octets séparent les deux
écrans-titres : les six immédiats `mov #3..8,R4` de `0x8C019CBC` et les six de
`0x8C01CBC8`.

---

## Les outils

Scripts Python, sans dépendance, pour Windows.

| Fichier | Rôle |
|---|---|
| `mem.py` | lire et écrire la RAM Model 3 du processus en cours |
| `play.py` | lance le jeu en forçant personnage et/ou région |
| `roster.py` | applique et maintient le déblocage du roster complet |
| `extract_ram.py` | extrait l'image RAM d'une sauvegarde d'état |
| `dump_state.py` | énumère et extrait les blocs d'une sauvegarde d'état |
| `symbols.py` | reconstruit la carte de symboles depuis l'image RAM |
| `gzip_crom.py` | extrait et réinjecte le programme, qui est un fichier gzip |
| `displaylist.py` | décode la liste d'affichage : quels éléments sont dessinés |
| `dl_watch.py` | surveille des éléments graphiques en continu |
| `build_crom.py` | ré-entrelace les ROM du zip en CROM et en VROM, et redécoupe une CROM patchée en EPROM |
| `decors.py` | la table de décors des deux versions, et ce qui les sépare |
| `model3d.py` | déroule un modèle Real3D depuis le VROM, et dit si une adresse en est un |
| `cdi.py` | ouvre l'image Dreamcast et en sort les fichiers |
| `afs.py` | lit les archives AFS de la version Dreamcast |
| `nuage.py` | rend un nuage de points des modèles Dreamcast, sans décodeur |
| `textures_dc.py` | décode les textures Dreamcast — VQ, twiddle, trois formats de pixel — et apparie les entrées MDL et TEX |
| `geometrie_dc.py` | sort la géométrie d'une entrée MDL en OBJ, avec ses deux formes de sommet |
| `retrouver.py` | retrouve une texture extraite parmi les 3 700 du disque, par signature |
| `fermer_trous.py` | referme les boucles d'arêtes de bord d'un OBJ, et répète aux quatre quadrants |
| `rendu_dessus.py` | rastérise un OBJ vu de dessus — juger une extraction sans ouvrir Blender |
| `rendu_face.py` | le même, vu de face |
| `planche_dc.py` | planche contact de toutes les textures d'une entrée |
| `desas_sh4.py` | désassembleur SH-4 : lit une adresse sans demander que ce soit du code |
| `tables_sh4.py` | quatre découvreurs — qui charge un littéral, qui saute ici, les tables de `BRAF`, et le graphe d'appels remonté |
| `decor_vers_entree.py` | fait voter un dossier de dump pour trouver l'entrée MDL d'un décor |
| `gdb_flycast.py` | client GDB distant pour Flycast, en bibliothèque standard |

Cinq lanceurs `.cmd` enchaînent ce qu'il faut, sans ligne à recopier :
**Reconstruire les ROM arcade**, **Ouvrir le disque Dreamcast**,
**Table des décors**, **Profil des modèles Dreamcast**,
**Sonder le binaire Dreamcast**. Les chemins par défaut
du zip MAME et de l'image Dreamcast se surchargent par les variables
d'environnement `FV2_ZIP` et `FV2_CDI`.

`symbols.csv` est réinjectable dans un projet Ghidra pour retrouver les noms
d'origine plutôt que des étiquettes automatiques.

---

## Questions ouvertes

**Ce qui pose le premier drapeau de progression en jeu normal.** Le code le
conditionne à un seuil sur un compteur, sans que la sémantique de ce compteur
soit établie. Les conditions Dreamcast — temps au stage 7, vie restante,
Super K.O. — donnent une piste plausible mais non vérifiée.

**L'aiguillage des écrans.** Trois pistes ont été explorées sans succès :
aucune table de pointeurs de fonctions d'écran n'existe ; les fonctions
d'écran n'ont aucun appelant direct, donc elles sont atteintes par adresse
calculée ; et une recherche de variable d'état par comparaison de quatre
sauvegardes prises sur quatre écrans différents n'a rien donné de
convaincant. La suite demande d'**observer le flot d'exécution**, ce que la
build publique de Supermodel ne permet pas — son débogueur est une option de
compilation absente des binaires distribués.

**Comment un décor désigne sa géométrie.** Le répartiteur de ressources est
trouvé et lu — voir [La résolution des identifiants de
ressource](#la-résolution-des-identifiants-de-ressource) — mais il ne traite
que de l'audio : musique, effets, et un troisième genre à cas écrits à la main.
La liste de `+0x08` d'un décor est audio de bout en bout. La géométrie se
charge donc par un autre chemin, et le chargeur de `mdl_dat` est identifié
(`0x8C02A5A8`, partition 1) sans que l'on sache quel index il reçoit pour un
décor donné. Le seul appariement connu, MDL 75 ↔ TEX 112 pour le décor
d'entraînement, a été obtenu par la mesure des textures.

**Le bit 5 du code de ruban.** L'en-tête d'un ruban est deux mots,
`(code, nombre de sommets)`, et le compte est juste à 96,8 % sur les
52 944 rubans de l'archive. Les échecs tiennent à un seul bit : sans le bit 5,
25 026 rubans se lisent à 100,0 % ; avec, 27 918 se lisent à 93,9 %. Dans ces
échecs l'écart le plus fréquent est exactement 2 — signature d'un ruban
continué, dont les deux premiers sommets seraient repris du précédent et non
stockés. Lecture plausible, non prouvée. Écarté par la mesure : une fenêtre
d'intercalation trop courte, une normale rangée ailleurs, un autre pas
uniforme.

**Le rôle de la troisième entrée réduite** de chaque personnage — 42 pour
Honey, 47 pour Jane : armure brisée ou niveau de détail, non tranché. Et
**comment le jeu choisit le second costume de Honey** (MDL 43 et 44), qu'il ne
nomme nulle part : `NURSE`, `COSTUME`, `SECRET`, `MAID`, `APRON`, `OUTFIT`,
balayés en ASCII et en Shift-JIS dans tout le binaire — zéro occurrence.

**Le rôle des champs `+0x60` et `+0x68` de la table de décors**, et la preuve
que le bloc de `0x1F8` octets porte bien la collision.

**L'ajout d'éléments à l'écran.** L'API de dessin est comprise : une routine
empile des paquets dans une liste d'affichage, en piochant dans une table
d'éléments, et chaque identifiant est une constante immédiate juste avant
l'appel — donc substituable. Mais substituer n'est pas ajouter : un menu
demanderait d'injecter du code.

---

## Portée et limites

Ces notes portent sur la révision japonaise `fvipers2` telle que reconnue par
Supermodel. Les adresses citées sont des adresses **RAM**, valides une fois le
programme décompressé. Elles se retrouvent telles quelles dans l'image tirée
du gzip de la CROM, ce qui rend le patch permanent possible.

Le dépôt ne contient **aucune sortie de décompilateur** : les mécanismes sont
décrits, pas retranscrits. Les adresses, valeurs et comportements relèvent de
la documentation, dans l'esprit des projets de préservation.

Aucune donnée de jeu n'est distribuée ici. Les outils supposent que vous
disposez déjà de votre propre copie et d'une installation de Supermodel.
