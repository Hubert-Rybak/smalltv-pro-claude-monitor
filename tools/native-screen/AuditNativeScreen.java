// Read-only extension feasibility audit of the saved exact vendor application.
// @category SmallTV.Reconstruction
import ghidra.app.util.headless.HeadlessScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;
import com.google.gson.*;
import java.nio.file.*;
import java.io.*;
import java.util.*;
import java.security.MessageDigest;

public class AuditNativeScreen extends HeadlessScript {
    Gson gson=new GsonBuilder().serializeNulls().disableHtmlEscaping().create();
    long source(Address a) {var info=currentProgram.getMemory().getAddressSourceInfo(a);return info==null?-1:info.getFileOffset();}
    String sha(byte[] raw) throws Exception {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw));}
    Map<String,Object> ref(Reference r) {
        Map<String,Object> x=new LinkedHashMap<>();x.put("from",r.getFromAddress().toString());x.put("to",r.getToAddress().toString());x.put("type",r.getReferenceType().toString());x.put("source_file_offset",source(r.getFromAddress()));
        Function f=currentProgram.getFunctionManager().getFunctionContaining(r.getFromAddress());x.put("function",f==null?null:f.getEntryPoint().toString());return x;
    }
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();if(args.length!=2)throw new IllegalArgumentException("original evidence root and follow-up exports required");
        Path original=Paths.get(args[0]),out=Paths.get(args[1]);Files.createDirectories(out);
        JsonObject map=JsonParser.parseString(Files.readString(original.resolve("exports/mapped_image.json"))).getAsJsonObject();
        byte[] vendor=Files.readAllBytes(Paths.get(map.get("vendor_path").getAsString()));String hash=sha(vendor);
        if(!hash.equals(map.get("vendor_sha256").getAsString()))throw new IOException("vendor hash differs");
        AddressSet exec=new AddressSet(),functionBodies=new AddressSet();
        for(JsonElement value:map.getAsJsonArray("segments")) {
            JsonObject seg=value.getAsJsonObject();Address a=toAddr(Long.parseUnsignedLong(seg.get("address").getAsString(),16));byte[] raw=new byte[seg.get("length").getAsInt()];
            currentProgram.getMemory().getBytes(a,raw);if(!sha(raw).equals(seg.get("mapped_sha256").getAsString()))throw new IOException("saved segment differs "+a);
            if(seg.get("executable").getAsBoolean())exec.add(a,a.add(raw.length-1));
        }
        Set<String> expected=new TreeSet<>(),saved=new TreeSet<>();
        for(String line:Files.readAllLines(original.resolve("exports/functions.jsonl")))expected.add(JsonParser.parseString(line).getAsJsonObject().get("entry").getAsString());
        FunctionIterator functions=currentProgram.getFunctionManager().getFunctions(true);
        while(functions.hasNext()){Function f=functions.next();saved.add(f.getEntryPoint().toString());functionBodies.add(f.getBody());}
        if(!saved.equals(expected))throw new IOException("saved/exported function set differs");
        long orphanBytes=0;int orphanCount=0;
        try(BufferedWriter w=Files.newBufferedWriter(out.resolve("orphan_instructions.jsonl"));BufferedWriter asm=Files.newBufferedWriter(out.resolve("orphan_instructions.asm"))) {
            asm.write("; Real saved-project instructions outside all discovered functions; not assigned invented functions.\n");
            InstructionIterator instructions=currentProgram.getListing().getInstructions(exec,true);
            while(instructions.hasNext()) {
                Instruction ins=instructions.next();if(currentProgram.getFunctionManager().getFunctionContaining(ins.getAddress())!=null)continue;
                Map<String,Object> row=new LinkedHashMap<>();row.put("address",ins.getAddress().toString());row.put("bytes_hex",HexFormat.of().formatHex(ins.getBytes()));row.put("assembly",ins.toString());row.put("function",null);row.put("source_file_offset",source(ins.getAddress()));
                List<Map<String,Object>> refs=new ArrayList<>();for(Reference r:ins.getReferencesFrom())refs.add(ref(r));row.put("references",refs);
                w.write(gson.toJson(row));w.newLine();asm.write(ins.getAddress()+"  "+row.get("bytes_hex")+"  "+ins.toString()+" ; source_file_offset=0x"+Long.toHexString(source(ins.getAddress()))+"\n");orphanCount++;orphanBytes+=ins.getLength();
            }
        }
        List<Map<String,Object>> runs=new ArrayList<>();
        for(MemoryBlock block:currentProgram.getMemory().getBlocks()) {
            if(!block.isInitialized()||!block.isExecute())continue;
            byte[] raw=new byte[(int)block.getSize()];currentProgram.getMemory().getBytes(block.getStart(),raw);
            for(int i=0;i<raw.length;) {
                int begin=i,value=raw[i]&255;if(value!=0&&value!=255){i++;continue;}
                while(i<raw.length&&(raw[i]&255)==value)i++;
                if(i-begin<16)continue;
                Address start=block.getStart().add(begin),end=start.add(i-begin-1);AddressSet range=new AddressSet(start,end);
                Map<String,Object> row=new LinkedHashMap<>();row.put("start",start.toString());row.put("end_inclusive",end.toString());row.put("block",block.getName());row.put("length",i-begin);row.put("value",value);row.put("source_file_offset",source(start));row.put("function_body_overlap_bytes",functionBodies.intersect(range).getNumAddresses());
                List<Map<String,Object>> refs=new ArrayList<>();AddressIterator destinations=currentProgram.getReferenceManager().getReferenceDestinationIterator(range,true);
                while(destinations.hasNext()){ReferenceIterator refsTo=currentProgram.getReferenceManager().getReferencesTo(destinations.next());while(refsTo.hasNext())refs.add(ref(refsTo.next()));}
                row.put("reference_count",refs.size());row.put("references",refs);
                List<Map<String,Object>> data=new ArrayList<>();Data head=currentProgram.getListing().getDataContaining(start);
                if(head!=null&&head.isDefined()){Map<String,Object> d=new LinkedHashMap<>();d.put("start",head.getAddress().toString());d.put("end_inclusive",head.getMaxAddress().toString());d.put("type",head.getDataType().getName());data.add(d);}
                DataIterator defined=currentProgram.getListing().getDefinedData(range,true);
                while(defined.hasNext()) {Data d=defined.next();if(head!=null&&head.getAddress().equals(d.getAddress()))continue;Map<String,Object> x=new LinkedHashMap<>();x.put("start",d.getAddress().toString());x.put("end_inclusive",d.getMaxAddress().toString());x.put("type",d.getDataType().getName());data.add(x);}
                row.put("defined_data_overlaps",data);row.put("safe_extension_point_established",false);row.put("warning","Byte fill and absence of Ghidra xrefs do not establish hardware-vector/padding ownership or safe reuse");runs.add(row);
            }
        }
        Files.writeString(out.resolve("fill_runs.json"),new GsonBuilder().setPrettyPrinting().create().toJson(runs)+"\n");
        JsonObject descriptors=JsonParser.parseString(Files.readString(original.resolve("exports/app_descriptors.json"))).getAsJsonObject();List<Map<String,Object>> audited=new ArrayList<>();
        for(JsonElement element:descriptors.getAsJsonArray("descriptors")) {
            JsonObject d=element.getAsJsonObject();Address address=toAddr(Long.parseUnsignedLong(d.get("descriptor_address").getAsString(),16));byte[] bytes=new byte[32];currentProgram.getMemory().getBytes(address,bytes);
            boolean equal=HexFormat.of().formatHex(bytes).equals(d.get("raw_32_bytes_hex").getAsString());if(!equal)throw new IOException("descriptor changed");
            Map<String,Object> row=new LinkedHashMap<>();row.put("name",d.get("name").getAsString());row.put("address",address.toString());row.put("source_file_offset",source(address));row.put("descriptor_bytes_match_original",true);
            List<Map<String,Object>> callbacks=new ArrayList<>();
            for(int i=3;i<8;i++) {
                JsonObject word=d.getAsJsonArray("words").get(i).getAsJsonObject();Address target=toAddr(Long.parseUnsignedLong(word.get("value").getAsString(),16));Function f=currentProgram.getFunctionManager().getFunctionAt(target);
                Map<String,Object> c=new LinkedHashMap<>();c.put("offset",i*4);c.put("target",target.toString());c.put("function_discovered",f!=null);c.put("source_file_offset",source(target));
                Instruction first=currentProgram.getListing().getInstructionAt(target);c.put("first_instruction",first==null?null:first.toString());callbacks.add(c);
            }
            row.put("callbacks",callbacks);audited.add(row);
        }
        Files.writeString(out.resolve("descriptor_audit.json"),new GsonBuilder().setPrettyPrinting().create().toJson(audited)+"\n");
        Map<String,Object> summary=new LinkedHashMap<>();summary.put("vendor_sha256",hash);summary.put("discovered_functions",saved.size());summary.put("orphan_instruction_count",orphanCount);summary.put("orphan_instruction_bytes",orphanBytes);summary.put("fill_run_count",runs.size());summary.put("stock_descriptors",audited.size());summary.put("callback_slots_audited",audited.size()*5);summary.put("read_only_audit",true);summary.put("modified_firmware_generated",false);
        Files.writeString(out.resolve("audit_summary.json"),new GsonBuilder().setPrettyPrinting().create().toJson(summary)+"\n");println("AUDIT COMPLETE "+gson.toJson(summary));
    }
}
