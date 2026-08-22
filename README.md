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
