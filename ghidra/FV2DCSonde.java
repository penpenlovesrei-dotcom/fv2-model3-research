// Sonde le binaire Dreamcast de Fighting Vipers 2 dans Ghidra.
//
// On connait trois zones de DONNEES, cartographiees a la main hors de Ghidra :
//
//   0x8C112420  l'enumeration des 25 creneaux de geometrie de decor
//   0x8C11763C  la table de decors, 27 enregistrements de 0x70 octets
//   0x8C0E4A9C  les tableaux de descripteurs de texture des banques partagees
//   0x8C0DD1D4  les noms de decors (TEST, WESTERN, AC_CARRIER, ...)
//
// Le but est de remonter de ces donnees vers le CODE qui les lit, pour trouver
// le champ de l'en-tete de partie qui dit comment derouler un ruban -- celui
// que l'extraction remplace aujourd'hui par des seuils mesures.
//
// @category FV2
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class FV2DCSonde extends GhidraScript {

    private void references(String libelle, long base, int longueur, int pas) throws Exception {
        println("");
        println("=== " + libelle + "  (" + String.format("0x%08X", base)
                + ", " + longueur + " octets)");
        int total = 0;
        for (int o = 0; o < longueur; o += pas) {
            Address a = toAddr(base + o);
            ReferenceIterator it = currentProgram.getReferenceManager().getReferencesTo(a);
            while (it.hasNext()) {
                Reference r = it.next();
                Address depuis = r.getFromAddress();
                Function f = getFunctionContaining(depuis);
                println(String.format("   +%-6X  depuis %s  %-14s  %s", o, depuis,
                        r.getReferenceType().getName(),
                        f == null ? "(hors fonction)" : f.getName() + " @ " + f.getEntryPoint()));
                total++;
                if (total > 60) {
                    println("   ... (tronque)");
                    return;
                }
            }
        }
        if (total == 0) {
            println("   aucune reference trouvee");
        }
    }

    @Override
    public void run() throws Exception {
        println("programme : " + currentProgram.getName());
        println("langage   : " + currentProgram.getLanguageID());
        println("base      : " + currentProgram.getImageBase());
        println("fonctions : " + currentProgram.getFunctionManager().getFunctionCount());
        println("symboles  : " + currentProgram.getSymbolTable().getNumSymbols());
        println("blocs memoire :");
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            println("   " + b.getName() + "  " + b.getStart() + " - " + b.getEnd()
                    + "  (" + b.getSize() + " octets)");
        }

        // L'enumeration : 25 mots consecutifs, on sonde chacun
        references("enumeration des creneaux de geometrie", 0x8C112420L, 25 * 4, 4);
        // La table de decors : on sonde le debut de chaque enregistrement
        references("table de decors, debut des enregistrements", 0x8C11763CL, 27 * 0x70, 0x70);
        // Les tableaux de descripteurs de texture
        references("tableaux de descripteurs de texture", 0x8C0E4A9CL, 0x4000, 4);
        // Les noms de decors
        references("noms de decors", 0x8C0DD1D4L, 0x120, 4);
    }
}
