// Pose dans le projet Ghidra ce que le balayage d'octets a etabli.
//
// Pourquoi un script et pas la main : Ghidra ne desassemble que 32,4 % de
// 1ST_READ.BIN, et presque rien de ce qui suit n'a de reference dans son
// graphe -- ces fonctions sont atteintes par adresse calculee, ou par un
// `bsr` dont le deplacement de 12 bits ne laisse aucune adresse en memoire.
// Le script force donc le desassemblage et cree la fonction si elle manque.
//
// Chaque nom ci-dessous a ete etabli en LISANT le code, pas en le devinant,
// et le commentaire porte la mesure qui le justifie. Les trois points
// d'entree des chargeurs ont ete corriges apres coup : la detection de
// prologue se fait avoir par les bassins de litteraux, qui suivent le `rts`
// de la fonction precedente et se decodent comme du code plausible.
//
// @category FV2
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.CodeUnit;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;

public class FV2DCNommer extends GhidraScript {

    /** adresse, nom, commentaire (la mesure qui etablit le nom) */
    private static final String[][] FONCTIONS = {
        {"8C047C9E", "fv2_ressource_charger",
         "Repartiteur de ressource. Un argument : l'identifiant.\n"
         + "Disposition : index en bits 31-16, sous-genre en 15-8, GENRE en 7-0.\n"
         + "`extu.b r11,r0` puis cmp/eq contre 0xA9, 0xFF et 0xF0 -- trois genres,\n"
         + "et trois seulement. Le decoupage 16/16 que suggere l'enumeration des\n"
         + "musiques est faux : il tombe sur 0x000803A9 et 0x000604A9, qui sont le\n"
         + "meme genre 0xA9 avec les sous-genres 3 et 4."},
        {"8C0479E8", "fv2_bgm_demarrer",
         "Genre 0xF0 : la musique. Reserve 284 868 octets (0x458C4), remet un\n"
         + "flottant de volume a zero, et lit la partition 4 (adx_dat.afs) via\n"
         + "ADXT_StartAfs. Mesure : les 13 indices employes par la table de decors\n"
         + "sont tous des flux CRI ADX valides, 44 100 Hz stereo, marque (c)CRI."},
        {"8C0C1D20", "fv2_aica_commande_empiler",
         "Genre 0xA9 : les effets sonores. Ecrit l'identifiant dans un anneau de\n"
         + "0xA0800400 a 0xA0800500 et reboucle au debut -- la RAM de l'AICA, par\n"
         + "le bus G2. C'est une file de commandes vers le processeur sonore."},
        {"8C028988", "fv2_adxf_partitions_enregistrer",
         "Recopie deux tableaux de cinq mots vers la pile -- les noms (0x8C0CD278)\n"
         + "et le nombre d'entrees utiles (0x8C0CD28C) -- puis appelle\n"
         + "ADXF_LoadPartition cinq fois, ptid 0 a 4, en donnant a chacune sa\n"
         + "tranche du tampon 0x8C1B0DB8. L'accumulateur est le retour de\n"
         + "adxf_partition_taille_memoire."},
        {"8C029ADA", "fv2_mot_dat_charger",
         "Partition 0, mot_dat.afs. Le ptid est `mov #0,r4` dans le CRENEAU DE\n"
         + "DELAI du jsr en 0x8C029B32."},
        {"8C02A5A8", "fv2_modele_et_textures_charger",
         "Partitions 1 ET 2 : une seule fonction charge le modele et ses textures.\n"
         + "Les ptid sont `mov #1,r4` en 0x8C02A756 et `mov #2,r4` en 0x8C02B6C0,\n"
         + "tous deux dans le creneau de delai de leur jsr. Le corps va au-dela de\n"
         + "0x8C02B706 (bra depuis 0x8C02A860), et le bassin qui precede le\n"
         + "prologue (0x8C02A586 : 0434 0438 043C 041C 0420) est sa table de saut\n"
         + "interne. Prend un index sur un octet : extu.b puis mulu.w #100, +100.\n"
         + "QUEL index pour un decor donne reste inconnu."},
        {"8C0474C8", "fv2_snd_dat_charger",
         "Partition 3, snd_dat.afs. Le ptid est `mov #3,r4` dans le creneau de\n"
         + "delai du jsr en 0x8C0474FE. Attention : 0x8C0474A8 n'est PAS le debut\n"
         + "de cette fonction, c'est le bassin de litteraux de la precedente."},
        {"8C12BA6A", "ADXF_LoadPartition",
         "Nomme par ses propres messages d'erreur : E9040803 a E9040810,\n"
         + "\"(ADXF_LoadPartition)\". Arguments (ptid, nom, memoire, nb_fichiers).\n"
         + "C'est la bibliotheque de CRI : AFS veut dire ADX File System."},
        {"8C12BE4E", "ADXF_Open",
         "Nomme par E9040901 a E9040903, \"(ADXF_Open)\"."},
        {"8C12C5E0", "ADXF_GetFileRange",
         "Nomme par E9040828, \"(ADXF_GetFileRange)\", porte par son verificateur.\n"
         + "Arguments (ptid, flid, &fad, &nsct)."},
        {"8C12C5A6", "adxf_ChkPrmPtFlid",
         "Verificateur de plage appele par ADXF_GetFileRange. ptid < 0x100 ;\n"
         + "ptinfo = [0x8C3DE0B8 + ptid*4] ; flid < ptinfo[+0x0C]."},
        {"8C12BF4C", "adxf_ouvrir_ptid_flid",
         "(poignee, ptid, flid) -> ADXF_GetFileRange, puis lecture."},
        {"8C12BF90", "adxf_ouvrir",
         "Ouverture generique. Huit appelants dans le code du jeu, dont les\n"
         + "quatre chargeurs de partition."},
        {"8C12BDEC", "adxf_partition_taille_memoire",
         "Feuille de quatre instructions, sans prologue parce qu'elle n'en a pas\n"
         + "besoin : ptinfo = [0x8C3DE0B8 + ptid*4], puis rts avec\n"
         + "r0 = ptinfo[+0x04] pose dans le creneau de delai. Son retour est\n"
         + "l'empreinte memoire d'une partition -- la boucle d'enregistrement\n"
         + "l'accumule pour decaler la tranche suivante."},
        {"8C12AA38", "ADXT_StartAfs",
         "Nomme par E8101202, \"(ADXT_StartAfs)\", charge en 0x8C12AA7A.\n"
         + "(objet, ptid, flid) -> ADXF_GetFileRange puis lecture dans l'objet."},
        {"8C02A2A0", "fv2_scene_creneau_installer",
         "(creneau, descripteur, pointeur). Le creneau indexe plusieurs tableaux\n"
         + "paralleles (0x8C188850, 0x8C188878, 0x8C0E4A88, 0x8C18897C, 0x8C188990)\n"
         + "et un enregistrement de 0x34 octets, ou le descripteur est recopie.\n"
         + "Vingt-cinq appelants, TOUS en COMPUTED_CALL -- c'est ce qui rendait\n"
         + "cette chaine invisible avant que les litteraux soient types."},
        {"8C02A39E", "fv2_scene_creneau_charger",
         "Pose le drapeau [0x8C18897C + creneau*4] = 1, appelle 0x8C02985E avec\n"
         + "creneau+5, puis fv2_modele_et_textures_charger. Le +5 est le meme\n"
         + "decalage que les `add #-5` du repartiteur de ressource."},
    };

    /** adresse, nom, type ou "" , commentaire */
    private static final String[][] DONNEES = {
        {"8C0CD278", "adxf_noms_de_partition", "",
         "Cinq pointeurs : mot_dat, mdl_dat, tex_dat, snd_dat, adx_dat.afs.\n"
         + "L'ordre donne le ptid, 0 a 4."},
        {"8C0CD28C", "adxf_entrees_utiles", "",
         "Cinq mots, paralleles aux noms : 1, 77, 114, 35, 25.\n"
         + "Ce sont les entrees UTILES, pas le compte de l'archive : la derniere\n"
         + "entree de chaque AFS est un terminateur de taille nulle. Mesure :\n"
         + "mdl_dat 78 entrees, tex_dat 115, adx_dat 26 -- toujours une de plus.\n"
         + "mdl_dat porte donc les indices 0 a 76, et l'entree 75 du decor\n"
         + "d'entrainement est dedans."},
        {"8C0CD544", "fv2_format_vidage_ressources", "string",
         "\"%2d:%d %08X %08X %4d [%s]\\n\" -- le vidage de debug de la table de\n"
         + "ressources, laisse dans le binaire. Charge par l'instruction en\n"
         + "0x8C02BA9A. \"File Open Error\" est juste au-dessus."},
        {"8C112420", "fv2_table_bgm", "",
         "25 identifiants (index << 16) | 0x00F0 : les 25 pistes BGM, pas une\n"
         + "enumeration de genres de geometrie. L'arcade en enumere 20 a\n"
         + "0x000EC048 ; la Dreamcast en a ajoute cinq, et TEST pointe sur le\n"
         + "dernier des cinq. L'index se boucle sur 24 (mov #24 en 0x8C050924)."},
        {"8C11763C", "fv2_table_decors", "",
         "27 enregistrements de 0x70 octets. Pointee par AUCUN litteral du\n"
         + "binaire : atteinte par adresse calculee. Le champ +0x08 pointe une\n"
         + "liste de 8 identifiants ENTIEREMENT audio -- trois banques d'effets\n"
         + "communes aux 27, la musique, une paire d'effets propre au decor, et un\n"
         + "identifiant de genre 0xFF."},
        {"8C3DE0B8", "adxf_table_des_partitions", "",
         "256 pointeurs de descripteur, indexes par ptid. Le descripteur porte\n"
         + "son empreinte memoire en +0x04 et son nombre de fichiers en +0x0C."},
        {"8C34F278", "fv2_bgm_index_courant", "",
         "L'index lu puis indexe dans fv2_table_bgm en 0x8C050904."},
        {"8C118294", "fv2_table_ressources_de_scene", "",
         "LA TABLE QUI MANQUAIT. 35 enregistrements de 0x34 octets.\n"
         + "\n"
         + "  +0x00 u32  indice d'entree dans mdl_dat.afs\n"
         + "  +0x04 u32  indice d'entree dans tex_dat.afs\n"
         + "  +0x08 u32  une taille\n"
         + "  +0x0C      pointeur (zone 0x8C112xxx)\n"
         + "  +0x10      pointeur (zone 0x8C112xxx)\n"
         + "  +0x30 u32  0xFFFFFFFF, ou 0xFFFF00xx pour les 13 premiers\n"
         + "\n"
         + "Le rang est l'index de la table de decors (0x8C11763C) :\n"
         + "  0-12   les 13 decors reels\n"
         + "  13-18  FINISH00 a FINISH05, soit MDL 28 a 33, consecutifs\n"
         + "  19-26  les sept ADV_* et SELECT\n"
         + "  27-34  huit scenes au-dela de la table de decors\n"
         + "\n"
         + "Atteinte uniquement par adresse calculee, et l'index arrive dans une\n"
         + "variable en RAM (0x8C1F56CF pour le chemin de 0x8C034D1C).\n"
         + "\n"
         + "RECOUPEMENT. Neuf decors avaient ete apparies independamment, par\n"
         + "signature de texture dumpee d'emulateur (decor_vers_entree.py). Sept\n"
         + "tombent sur la diagonale rang = index du decor. Et sur les 26 paires\n"
         + "MDL<->TEX que l'appariement par pavage exact couvrait, la table n'en\n"
         + "contredit AUCUNE.\n"
         + "\n"
         + "Seul desaccord : une image du releve « The Great B.M » tombe a l'ecart\n"
         + "0,0 sur MDL 33, que la table place en FINISH05. GREAT_BM est le rang 4,\n"
         + "donc MDL 35. L'image vient probablement de la scene de fin -- une seule\n"
         + "ne tranche pas."},
        {"8C047D1E", "fv2_genre_A9_effets", "word",
         "0x00A9. Compare au bas octet de l'identifiant par le repartiteur."},
        {"8C047D20", "fv2_genre_FF", "word",
         "0x00FF. Branche a cas ecrits a la main, un par index."},
        {"8C047D22", "fv2_genre_F0_musique", "word",
         "0x00F0. Partition 4, adx_dat.afs."},
    };

    private int poses = 0;
    private int rates = 0;

    private void fonction(String hex, String nom, String note) throws Exception {
        Address a = toAddr(hex);
        if (getInstructionAt(a) == null) {
            disassemble(a);
        }
        Function f = getFunctionAt(a);
        if (f == null) {
            f = createFunction(a, nom);
        }
        if (f == null) {
            println("  ECHEC " + hex + " : ni fonction existante ni creation");
            rates++;
            return;
        }
        String avant = f.getName();
        f.setName(nom, SourceType.USER_DEFINED);
        f.setComment(note);
        println(String.format("  %s  %-34s (etait %s)", hex, nom, avant));
        poses++;
    }

    private void donnee(String hex, String nom, String type, String note) throws Exception {
        Address a = toAddr(hex);
        createLabel(a, nom, true, SourceType.USER_DEFINED);
        setPlateComment(a, note);
        if (!type.isEmpty() && getDataAt(a) == null) {
            try {
                if (type.equals("string")) {
                    createAsciiString(a);
                } else if (type.equals("word")) {
                    createWord(a);
                } else if (type.equals("dword")) {
                    createDWord(a);
                }
            } catch (Exception e) {
                println("  (type non pose en " + hex + " : " + e.getMessage() + ")");
            }
        }
        println(String.format("  %s  %s", hex, nom));
        poses++;
    }

    @Override
    public void run() throws Exception {
        println("FV2DCNommer sur " + currentProgram.getName()
                + "  base " + currentProgram.getImageBase());
        println("");
        println("Fonctions :");
        for (String[] e : FONCTIONS) {
            try {
                fonction(e[0], e[1], e[2]);
            } catch (Exception ex) {
                println("  ECHEC " + e[0] + " : " + ex.getMessage());
                rates++;
            }
        }
        println("");
        println("Donnees :");
        for (String[] e : DONNEES) {
            try {
                donnee(e[0], e[1], e[2], e[3]);
            } catch (Exception ex) {
                println("  ECHEC " + e[0] + " : " + ex.getMessage());
                rates++;
            }
        }
        println("");
        println(poses + " pose(s), " + rates + " echec(s).");
        println("Les commentaires de type 'plate' sont en tete de chaque entree ;");
        println("ceux des fonctions sont rendus par le decompilateur.");
    }
}
