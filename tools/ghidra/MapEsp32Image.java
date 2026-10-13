// Map an authenticated ESP32 application, retaining original-file offsets.
// @category SmallTV.Reconstruction
import ghidra.app.script.GhidraScript;
import ghidra.app.util.headless.HeadlessScript;
import ghidra.program.model.mem.*;
import ghidra.program.database.mem.FileBytes;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.SourceType;
import java.nio.file.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import com.google.gson.GsonBuilder;

public class MapEsp32Image extends HeadlessScript {
    private long u32(byte[] b, int o) {
        return ((long)b[o]&255) | (((long)b[o+1]&255)<<8) | (((long)b[o+2]&255)<<16) | (((long)b[o+3]&255)<<24);
    }
    private String sha(byte[] b) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));
    }
    @Override public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) throw new IllegalArgumentException("image path and export directory required");
        Path image = Paths.get(args[0]); Path out = Paths.get(args[1]); Files.createDirectories(out);
        byte[] b = Files.readAllBytes(image);
        String expected = "1aa9a0408e8a3bee568a45376eb2583fe35ba4daafc14880a8cf1531540066be";
        if (!sha(b).equals(expected)) throw new IOException("vendor image SHA256 mismatch");
        if ((b[0]&255) != 0xe9 || (b[1]&255) != 5 || b[12] != 0 || b[13] != 0) throw new IOException("not the exact ESP32 image");
        if (!currentProgram.getLanguageID().toString().equals("Xtensa:LE:32:default")) throw new IOException("wrong language");
        Memory mem = currentProgram.getMemory();
        for (MemoryBlock old : mem.getBlocks()) mem.removeBlock(old, monitor);
        List<FileBytes> existing = mem.getAllFileBytes();
        FileBytes original = existing.isEmpty() ? mem.createFileBytes(image.getFileName().toString(), 0, b.length, new ByteArrayInputStream(b), monitor) : existing.get(0);
        String[] names = {"DROM", "DRAM", "IRAM_0", "IROM", "IRAM_1"};
        int cursor = 24; List<Map<String,Object>> segments = new ArrayList<>();
        List<Address> candidates = new ArrayList<>();
        for (int i=0; i<(b[1]&255); i++) {
            long address=u32(b,cursor), length=u32(b,cursor+4); int dataOffset=cursor+8;
            if (length > Integer.MAX_VALUE || dataOffset+length > b.length) throw new IOException("truncated segment");
            MemoryBlock block=mem.createInitializedBlock(names[i], toAddr(address), original, dataOffset, length, false);
            block.setRead(true); block.setWrite(address >= 0x3ff00000 && address < 0x40000000);
            block.setExecute(address >= 0x40000000);
            block.setComment("Vendor app segment " + i + ", header offset 0x"+Integer.toHexString(cursor)+", data offset 0x"+Integer.toHexString(dataOffset)+"; no flash partition base assumed");
            byte[] loaded = new byte[(int)length]; mem.getBytes(block.getStart(),loaded);
            Map<String,Object> seg=new LinkedHashMap<>();
            seg.put("index",i);seg.put("name",names[i]);seg.put("address",block.getStart().toString());
            seg.put("length",length);seg.put("header_offset",cursor);seg.put("data_offset",dataOffset);
            seg.put("executable",block.isExecute());seg.put("mapped_sha256",sha(loaded));
            seg.put("ghidra_source_file_offset",mem.getAddressSourceInfo(block.getStart()).getFileOffset());
            segments.add(seg);
            if (block.isExecute()) {
                for (int j=0;j+2<loaded.length;j++) {
                    long a=address+j;
                    int v1=loaded[j+1]&255,v2=loaded[j+2]&255;
                    int stack=(((v2<<4)|(v1>>4))<<3);
                    if ((a&3)==0 && (loaded[j]&255)==0x36 && (v1&15)==1 && stack>=16 && stack<=8192) candidates.add(toAddr(a));
                }
            }
            cursor = dataOffset+(int)length;
            println("MAPPED "+names[i]+" "+block.getStart()+" length="+length+" file=0x"+Integer.toHexString(dataOffset));
        }
        // Plausible DRAM gaps are uninitialized, NOT copied or invented bytes.
        MemoryBlock low=mem.createUninitializedBlock("DRAM_unsupplied_low",toAddr(0x3ffae000L),0xfb60,false);
        low.setRead(true);low.setWrite(true);low.setExecute(false);low.setComment("Uninitialized ESP32 DRAM; no BSS boundary inferred");
        MemoryBlock high=mem.createUninitializedBlock("DRAM_unsupplied_high",toAddr(0x3ffc4180L),0x1be80,false);
        high.setRead(true);high.setWrite(true);high.setExecute(false);high.setComment("Uninitialized ESP32 DRAM; no contents recovered");
        long entry = u32(b,4); Address ep=toAddr(entry);
        currentProgram.getSymbolTable().addExternalEntryPoint(ep);
        disassemble(ep);
        Function ef=createFunction(ep,"image_entry_40083200");
        if (ef==null) throw new IOException("image entry function creation failed");
        int created=0,skipped=0,failed=0;
        try (BufferedWriter seeds=Files.newBufferedWriter(out.resolve("function_seeds.jsonl"))) {
            for (Address a:candidates) {
                monitor.checkCancelled();
                Map<String,Object> row=new LinkedHashMap<>(); row.put("address",a.toString());row.put("reason","4-byte-aligned ENTRY a1 with 16..8192 byte frame; heuristic, not source symbol");
                Function old=currentProgram.getFunctionManager().getFunctionContaining(a);
                if (old!=null) {skipped++;row.put("status","already_contained");}
                else {
                    disassemble(a);
                    Instruction instr=currentProgram.getListing().getInstructionAt(a);
                    if (instr!=null && instr.getMnemonicString().equals("entry")) {
                        Function f=createFunction(a,null);
                        if (f!=null) {created++;row.put("status","created");}
                        else {failed++;row.put("status","creation_failed");}
                    } else {failed++;row.put("status","decode_failed");}
                }
                seeds.write(new GsonBuilder().create().toJson(row));seeds.newLine();
                if ((created+skipped+failed)%500==0) {seeds.flush();println("SEEDS processed="+(created+skipped+failed)+" created="+created);}
            }
        }
        byte[] entryBytes=new byte[32];mem.getBytes(ep,entryBytes);
        Map<String,Object> manifest=new LinkedHashMap<>();
        manifest.put("provenance","Exact vendor release application image; NOT a device flash dump or full 8MB flash");
        manifest.put("vendor_path",image.toAbsolutePath().toString());manifest.put("vendor_sha256",sha(b));
        manifest.put("language",currentProgram.getLanguageID().toString());manifest.put("compiler_spec",currentProgram.getCompilerSpec().getCompilerSpecID().toString());
        manifest.put("entry_address",ep.toString());manifest.put("entry_bytes_hex",HexFormat.of().formatHex(entryBytes));manifest.put("segments",segments);
        manifest.put("seed_candidates",candidates.size());manifest.put("seed_created",created);manifest.put("seed_skipped",skipped);manifest.put("seed_failures",failed);
        manifest.put("unsupplied_memory","Two uninitialized DRAM gaps; ROM, MMIO, partition table and filesystem image not supplied");
        Files.writeString(out.resolve("mapped_image.json"),new GsonBuilder().setPrettyPrinting().create().toJson(manifest)+"\n");
        println("SEEDS COMPLETE candidates="+candidates.size()+" created="+created+" skipped="+skipped+" failures="+failed);
    }
}
