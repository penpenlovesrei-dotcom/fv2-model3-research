// Quatrieme passe : qui LIT les constantes de genre de ressource.
//
// 32,4 % du binaire est du code, le reste des donnees -- l'amorcage au point
// d'entree n'y change rien, c'est la proportion reelle. Les occurrences de
// 0x03A9 et 0x04A9 tombent donc soit dans des tables de donnees, soit dans des
// bassins litteraux entre deux fonctions. Dans les deux cas elles sont « hors
// fonction », et la bonne question n'est pas qui les CONTIENT mais qui les
// REFERENCE : en SH-4 une constante de 16 bits se charge par
// `mov.w @(disp,PC),Rn`, ce qui cree une reference depuis le code.
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

public class FV2DCLitteraux extends GhidraScript {

    private PrintWriter sortie;

    private void deux(String s) {
        sortie.println(s);
        println(s);
    }

    private Set<Function> qui_lit(long valeur, int largeur) throws Exception {
        deux("");
        deux(String.format("=== qui lit la constante 0x%03X (%d bits)", valeur, largeur * 8));
        byte[] motif = new byte[largeur];
        for (int i = 0; i < largeur; i++) {
            motif[i] = (byte) ((valeur >> (8 * i)) & 0xFF);
        }
        Set<Function> out = new LinkedHashSet<>();
        Address a = currentProgram.getMinAddress();
        int vus = 0;
        while (a != null && vus < 400) {
            a = find(a.add(1), motif);
            if (a == null) {
                break;
            }
            vus++;
            ReferenceIterator it = currentProgram.getReferenceManager().getReferencesTo(a);
            while (it.hasNext()) {
                Reference r = it.next();
                Function f = getFunctionContaining(r.getFromAddress());
                if (f != null && out.add(f)) {
                    deux(String.format("   %s lu depuis %s dans %s @ %s", a,
                            r.getFromAddress(), f.getName(), f.getEntryPoint()));
                }
            }
        }
        deux("   " + vus + " occurrence(s) balayee(s), " + out.size() + " fonction(s) lectrice(s)");
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
                "C:\\Users\\frede\\Documents\\fv2-arcade-notes\\ghidra\\litteraux.txt");
        Set<Function> candidats = new LinkedHashSet<>();
        candidats.addAll(qui_lit(0x3A9L, 2));
        candidats.addAll(qui_lit(0x4A9L, 2));
        // l'identifiant complet d'une ressource de geometrie, sur 32 bits :
        // (index << 16) | 0x00F0 -- on essaie l'index 0x18, celui de TEST
        candidats.addAll(qui_lit(0x001800F0L, 4));
        deux("");
        deux(candidats.size() + " fonction(s) candidate(s), decompilees dans litteraux.txt");
        for (Function f : candidats) {
            decompile(f);
        }
        sortie.close();
    }
}
