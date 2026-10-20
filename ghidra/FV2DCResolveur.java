// Troisieme passe : trouver le resolveur d'identifiant de ressource.
//
// Les donnees ne sont referencees par aucune fonction -- table de decors,
// listes de ressources, enumeration des creneaux sont toutes atteintes par
// adresse calculee. On prend donc l'autre bout : les GENRES de ressource sont
// des constantes, et 0x03A9 et 0x04A9 sont assez rares pour servir d'ancre.
//
//   genre 0x00F0  geometrie de decor
//   genre 0x03A9  commun A      <- rare, bonne ancre
//   genre 0x04A9  commun B      <- rare, bonne ancre
//   genre 0x00FF  commun C
//
// On remonte aussi le graphe d'appels depuis FUN_8C02BE6E, le selecteur de
// banque de textures : son appelant charge un decor.
//
// @category FV2
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.OperandType;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.scalar.Scalar;
import java.io.PrintWriter;
import java.util.LinkedHashSet;
import java.util.Set;

public class FV2DCResolveur extends GhidraScript {

    private PrintWriter sortie;

    private void deux(String s) {
        sortie.println(s);
        println(s);
    }

    /** Les fonctions dont une instruction porte ce scalaire. */
    private Set<Function> parScalaire(long valeur) {
        Set<Function> out = new LinkedHashSet<>();
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            for (int i = 0; i < ins.getNumOperands(); i++) {
                if ((ins.getOperandType(i) & OperandType.SCALAR) == 0) {
                    continue;
                }
                Scalar s = ins.getScalar(i);
                if (s != null && s.getUnsignedValue() == valeur) {
                    Function f = getFunctionContaining(ins.getAddress());
                    if (f != null) {
                        out.add(f);
                    } else {
                        deux("      " + ins.getAddress() + " (hors fonction) : " + ins);
                    }
                }
            }
        }
        return out;
    }

    /** Les mots de 16 bits egaux a la valeur, dans les bassins litteraux. */
    private void parMemoire(long valeur) throws Exception {
        byte[] motif = new byte[] { (byte) (valeur & 0xFF), (byte) ((valeur >> 8) & 0xFF) };
        Address a = currentProgram.getMinAddress();
        int n = 0;
        while (a != null && n < 24) {
            a = find(a.add(1), motif);
            if (a == null) {
                break;
            }
            if (a.getOffset() % 2 != 0) {
                continue;
            }
            Function f = getFunctionContaining(a);
            deux(String.format("      %s  %s", a,
                    f == null ? "(hors fonction)" : f.getName() + " @ " + f.getEntryPoint()));
            n++;
        }
        if (n == 0) {
            deux("      aucune occurrence");
        }
    }

    private void appelants(String adresse, int profondeur) {
        Function f = getFunctionContaining(toAddr(adresse));
        if (f == null) {
            deux("   " + adresse + " : aucune fonction");
            return;
        }
        Set<Function> courant = new LinkedHashSet<>();
        courant.add(f);
        for (int niveau = 1; niveau <= profondeur; niveau++) {
            Set<Function> suivant = new LinkedHashSet<>();
            for (Function g : courant) {
                for (Function h : g.getCallingFunctions(monitor)) {
                    suivant.add(h);
                }
            }
            if (suivant.isEmpty()) {
                deux("   niveau " + niveau + " : aucun appelant");
                break;
            }
            StringBuilder sb = new StringBuilder("   niveau " + niveau + " ("
                    + suivant.size() + ") :");
            for (Function h : suivant) {
                sb.append(" ").append(h.getEntryPoint());
            }
            deux(sb.toString());
            courant = suivant;
        }
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
        sortie = new PrintWriter("C:\\Users\\frede\\Documents\\fv2-arcade-notes\\ghidra\\resolveur.txt");

        deux("=== appelants du selecteur de banques FUN_8C02BE6E");
        appelants("8c02be6e", 3);

        Set<Function> candidats = new LinkedHashSet<>();
        for (long genre : new long[] { 0x3A9L, 0x4A9L }) {
            deux("");
            deux("=== scalaire " + String.format("0x%03X", genre) + " dans les instructions");
            Set<Function> fs = parScalaire(genre);
            for (Function f : fs) {
                deux("      " + f.getName() + " @ " + f.getEntryPoint());
            }
            if (fs.isEmpty()) {
                deux("      aucune instruction");
            }
            candidats.addAll(fs);
            deux("=== mot 16 bits " + String.format("0x%03X", genre) + " en memoire");
            parMemoire(genre);
        }

        deux("");
        deux(candidats.size() + " fonction(s) candidate(s), decompilees dans resolveur.txt");
        for (Function f : candidats) {
            decompile(f);
        }
        sortie.close();
    }
}
