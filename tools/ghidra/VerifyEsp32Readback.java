// Independently reopen the saved project and attest its final function set and bytes.
// @category SmallTV.Reconstruction
import ghidra.app.util.headless.HeadlessScript;
import ghidra.program.model.mem.*;
import ghidra.program.model.listing.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.google.gson.*;

public class VerifyEsp32Readback extends HeadlessScript {
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();if(args.length!=1)throw new IllegalArgumentException("export directory required");
        Path out=Paths.get(args[0]);
        JsonObject manifest=JsonParser.parseString(Files.readString(out.resolve("mapped_image.json"))).getAsJsonObject();
        Set<String> exported=new TreeSet<>(), saved=new TreeSet<>();
        for(String line:Files.readAllLines(out.resolve("functions.jsonl"))) exported.add(JsonParser.parseString(line).getAsJsonObject().get("entry").getAsString());
        FunctionIterator fit=currentProgram.getFunctionManager().getFunctions(true);
        while(fit.hasNext())saved.add(fit.next().getEntryPoint().toString());
        boolean same=saved.equals(exported);
        if(!same)throw new IllegalStateException("Saved project function set differs from exported inventory");
        for(JsonElement value:manifest.getAsJsonArray("segments")) {
            JsonObject seg=value.getAsJsonObject();
            byte[] bytes=new byte[seg.get("length").getAsInt()];
            var address=toAddr(Long.parseUnsignedLong(seg.get("address").getAsString(),16));
            int n=currentProgram.getMemory().getBytes(address,bytes);
            String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
            if(n!=bytes.length||!hash.equals(seg.get("mapped_sha256").getAsString())||currentProgram.getMemory().getAddressSourceInfo(address).getFileOffset()!=seg.get("data_offset").getAsLong())throw new IllegalStateException("Saved mapping differs from authenticated segment "+address);
        }
        boolean entry=currentProgram.getSymbolTable().isExternalEntryPoint(toAddr(0x40083200L));
        if(!entry)throw new IllegalStateException("Missing ESP32 image entry point");
        Map<String,Object> result=new LinkedHashMap<>();result.put("mapping_verified",true);result.put("same_entry_set",same);result.put("project_discovered_functions",saved.size());result.put("export_inventory_entries",exported.size());result.put("entry_point_registered",entry);result.put("language",currentProgram.getLanguageID().toString());result.put("program",currentProgram.getName());
        Files.writeString(out.resolve("project_readback.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result)+"\n");
        println("PROJECT READBACK "+new Gson().toJson(result));
    }
}
