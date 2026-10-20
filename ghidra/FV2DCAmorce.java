// Amorce le desassemblage au point d'entree, puis relance l'analyse.
//
// Importe en binaire brut, Ghidra n'a aucun point d'entree et ne desassemble
// que ce qu'il devine : 2 311 fonctions pour 1,3 Mo, et toutes les occurrences
// des constantes cherchees tombaient « hors fonction ». Un 1ST_READ.BIN de
// Dreamcast s'execute a son adresse de chargement, 0x8C010000 -- c'est l'IP.BIN
// qui l'y amene. On part de la.
//
// @category FV2
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.MemoryBlock;

public class FV2DCAmorce extends GhidraScript {

    private void etat(String quand) {
        long octets = 0;
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        long n = 0;
        while (it.hasNext()) {
            Instruction ins = it.next();
            octets += ins.getLength();
            n++;
        }
        long taille = 0;
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            taille += b.getSize();
        }
        println(String.format("%s : %d fonctions, %d instructions, %d octets desassembles "
                + "sur %d (%.1f %%)", quand,
                currentProgram.getFunctionManager().getFunctionCount(), n, octets, taille,
                100.0 * octets / taille));
    }

    @Override
    public void run() throws Exception {
        etat("avant");
        Address entree = toAddr(0x8C010000L);
        disassemble(entree);
        if (getFunctionAt(entree) == null) {
            createFunction(entree, "entree_1ST_READ");
        }
        addEntryPoint(entree);
        etat("apres amorce");
        analyzeChanges(currentProgram);
        etat("apres analyse");
    }
}
