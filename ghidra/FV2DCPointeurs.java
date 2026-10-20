// Cinquieme passe : qui lit les bassins litteraux qui portent les adresses.
//
// La table de decors 0x8C11763C n'est pointee par AUCUN litteral du binaire --
// son adresse est donc calculee, ou elle est atteinte depuis une structure
// qu'on n'a pas encore. En revanche l'enumeration des creneaux 0x8C112420 est
// pointee depuis 0x8C0509F4, et cette adresse-la tombe dans la zone de CODE :
// c'est un bassin litteral, et l'instruction qui le charge est dans une
// fonction. Meme chose pour le tableau de pointeurs des descripteurs de
// texture, a 0x8C0E4C64.
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

public class FV2DCPointeurs extends GhidraScript {

    private PrintWriter sortie;

    private void deux(String s) {
        sortie.println(s);
        println(s);
    }

    private Set<Function> lecteurs(String libelle, long adresse, int longueur) {
        deux("");
        deux("=== " + libelle + "  " + String.format("0x%08X", adresse));
        Set<Function> out = new LinkedHashSet<>();
        for (int o = 0; o < longueur; o += 4) {
            Address a = toAddr(adresse + o);
            ReferenceIterator it = currentProgram.getReferenceManager().getReferencesTo(a);
            while (it.hasNext()) {
                Reference r = it.next();
                Function f = getFunctionContaining(r.getFromAddress());
                deux(String.format("   +%-4X depuis %s  %-12s  %s", o, r.getFromAddress(),
                        r.getReferenceType().getName(),
                        f == null ? "(hors fonction)" : f.getName() + " @ " + f.getEntryPoint()));
                if (f != null) {
                    out.add(f);
                }
            }
        }
        if (out.isEmpty()) {
            deux("   aucune fonction lectrice");
        }
        return out;
    }

    private void decompile(Function f) throws Exception {
        sortie.println("");
        sortie.println("=== " + f.getName() + " @ " + f.getEntryPoint()
                + "  (" + f.getBody().getNumAddresses() + " octets)");
        DecompInterface d = new DecompInterface();
        d.openProgram(currentProgram);
        DecompileResults res = d.decompileFunction(f, 120, monitor);
        if (res.decompileCompleted() && res.getDecompiledFunction() != null) {
            sortie.println(res.getDecompiledFunction().getC());
        } else {
            sortie.println("   echec : " + res.getErrorMessage());
        }
        d.dispose();
    }

    @Override
    public void run() throws Exception {
        sortie = new PrintWriter(
                "C:\\Users\\frede\\Documents\\fv2-arcade-notes\\ghidra\\pointeurs.txt");
        Set<Function> cands = new LinkedHashSet<>();
        cands.addAll(lecteurs("litteral vers l'enumeration des creneaux", 0x8C0509F4L, 4));
        cands.addAll(lecteurs("tableau de pointeurs des descripteurs de texture",
                0x8C0E4C64L, 0x60));
        cands.addAll(lecteurs("zone autour du litteral", 0x8C0509E0L, 0x40));
        deux("");
        deux(cands.size() + " fonction(s), decompilees dans pointeurs.txt");
        for (Function f : cands) {
            decompile(f);
        }
        sortie.close();
    }
}
