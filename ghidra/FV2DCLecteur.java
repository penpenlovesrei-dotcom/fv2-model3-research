// Deuxieme passe : qui lit les listes de ressources, et que fait le chargeur
// de textures.
//
// La premiere sonde a montre que FUN_8C02BE6E reference plusieurs tableaux de
// descripteurs de texture : c'est le chargeur de banques. On le decompile, en
// esperant y voir comment un identifiant de ressource (genre, index) devient
// une adresse -- la resolution qui manque encore.
//
// On sonde aussi la zone des listes de ressources par decor : 0x8C113308 a
// 0x8C1134B0, huit identifiants par decor. Le code qui les lit est le
// chargeur de decor.
//
// @category FV2
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class FV2DCLecteur extends GhidraScript {

    // Ghidra ne prefixe que la PREMIERE ligne d'un println multiligne, et
    // tout filtrage de la sortie avale donc le corps des decompilations.
    // On ecrit dans un fichier.
    private PrintWriter sortie;

    private Set<Function> sonde(String libelle, long base, int longueur, int pas) {
        println("");
        println("=== " + libelle);
        Set<Function> fonctions = new LinkedHashSet<>();
        for (int o = 0; o < longueur; o += pas) {
            Address a = toAddr(base + o);
            ReferenceIterator it = currentProgram.getReferenceManager().getReferencesTo(a);
            while (it.hasNext()) {
                Reference r = it.next();
                Function f = getFunctionContaining(r.getFromAddress());
                if (f != null && fonctions.add(f)) {
                    println(String.format("   +%-5X %s @ %s", o, f.getName(), f.getEntryPoint()));
                }
            }
        }
        if (fonctions.isEmpty()) {
            println("   aucune fonction referencante");
        }
        return fonctions;
    }

    private void decompile(String adresse) throws Exception {
        Address a = toAddr(adresse);
        Function f = getFunctionContaining(a);
        if (f == null) {
            println("");
            println("=== " + adresse + " : aucune fonction");
            return;
        }
        sortie.println("");
        println("");
        sortie.println("=== decompilation de " + f.getName() + " @ " + f.getEntryPoint());
        println("=== decompilation de " + f.getName() + " @ " + f.getEntryPoint()
                + "  (" + f.getBody().getNumAddresses() + " octets)");
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        DecompileResults res = d.decompileFunction(f, 120, monitor);
        if (res.decompileCompleted() && res.getDecompiledFunction() != null) {
            sortie.println(res.getDecompiledFunction().getC());
        } else {
            println("   echec : " + res.getErrorMessage());
        }
        d.dispose();
    }

    @Override
    public void run() throws Exception {
        sortie = new PrintWriter("C:\\Users\\frede\\Documents\\fv2-arcade-notes\\ghidra\\decomp.txt");
        sonde("listes de ressources par decor (0x8C113308)", 0x8C113308L, 0x1B0, 4);
        sonde("enumeration des creneaux (0x8C112420)", 0x8C112420L, 100, 4);

        decompile("8c02be6e");   // chargeur de banques de textures
        decompile("8c0532c4");   // reference les libelles DEBUG et PAUSE
        sortie.close();
    }
}
