// Export every real discovered function and literal-mediated string references.
// @category SmallTV.Reconstruction
import ghidra.app.util.headless.HeadlessScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

public class ExportEsp32Analysis extends HeadlessScript {
    Gson gson = new GsonBuilder().disableHtmlEscaping().create();
    Path out;
    long fileOffset(Address a) {
        var source = currentProgram.getMemory().getAddressSourceInfo(a);
        return source == null ? -1 : source.getFileOffset();
    }
    void line(BufferedWriter w, Object row) throws IOException {w.write(gson.toJson(row));w.newLine();}
    long u32(byte[] b, int o) {return ((long)b[o]&255)|(((long)b[o+1]&255)<<8)|(((long)b[o+2]&255)<<16)|(((long)b[o+3]&255)<<24);}
    Map<String,Object> codeRef(Reference ref, String kind, Address literal) {
        Address from=ref.getFromAddress();
        Instruction instr=currentProgram.getListing().getInstructionContaining(from);
        if (instr==null) return null;
        Function f=currentProgram.getFunctionManager().getFunctionContaining(from);
        Map<String,Object> row=new LinkedHashMap<>();
        row.put("from",from.toString());row.put("to",ref.getToAddress().toString());
        row.put("type",ref.getReferenceType().toString());row.put("kind",kind);
        row.put("function",f==null?null:f.getEntryPoint().toString());
        row.put("function_name",f==null?null:f.getName());
        row.put("instruction",instr.toString());row.put("source_file_offset",fileOffset(from));
        row.put("literal_address",literal==null?null:literal.toString());
        return row;
    }
    int exportStrings() throws Exception {
        Memory mem=currentProgram.getMemory();
        TreeMap<Long,Map<String,Object>> strings=new TreeMap<>();
        Map<Long,Integer> lengths=new HashMap<>();
        for (MemoryBlock block:mem.getBlocks()) {
            if (!block.isInitialized()) continue;
            byte[] bytes=new byte[(int)block.getSize()];mem.getBytes(block.getStart(),bytes);
            for (int i=0;i<bytes.length;) {
                int start=i;
                while (i<bytes.length && ((bytes[i]&255)>=32 && (bytes[i]&255)<=126 || bytes[i]==9 || bytes[i]==10 || bytes[i]==13)) i++;
                int size=i-start;
                if (size>=4 && i<bytes.length && bytes[i]==0) {
                    long addr=block.getStart().getOffset()+start;
                    Map<String,Object> row=new LinkedHashMap<>();
                    row.put("address",toAddr(addr).toString());row.put("length",size);row.put("source_file_offset",fileOffset(toAddr(addr)));
                    row.put("text",new String(bytes,start,size,java.nio.charset.StandardCharsets.US_ASCII));
                    row.put("block",block.getName());
                    row.put("pointer_references",new ArrayList<Map<String,Object>>());
                    row.put("code_references",new ArrayList<Map<String,Object>>());
                    ReferenceIterator refs=currentProgram.getReferenceManager().getReferencesTo(toAddr(addr));
                    while (refs.hasNext()) {
                        Map<String,Object> r=codeRef(refs.next(),"direct_reference",null);
                        if(r!=null)((List<Map<String,Object>>)row.get("code_references")).add(r);
                    }
                    strings.put(addr,row);lengths.put(addr,size);
                }
                if (i==start) i++; else if(i<bytes.length) i++;
            }
        }
        for (MemoryBlock block:mem.getBlocks()) {
            if (!block.isInitialized()) continue;
            byte[] bytes=new byte[(int)block.getSize()];mem.getBytes(block.getStart(),bytes);
            for (int j=0;j+3<bytes.length;j++) {
                long pos=block.getStart().getOffset()+j;
                if ((pos&3)!=0) continue;
                long pointer=u32(bytes,j);
                var match=strings.floorEntry(pointer);
                if (match==null || pointer>=match.getKey()+lengths.get(match.getKey())) continue;
                // Numeric pointers found in original bytes are evidence, not automatically a Ghidra data type.
                Map<String,Object> row=match.getValue();Address literal=toAddr(pos);
                List<Map<String,Object>> loadedFrom=new ArrayList<>();
                ReferenceIterator refs=currentProgram.getReferenceManager().getReferencesTo(literal);
                while(refs.hasNext()) {
                    Map<String,Object> r=codeRef(refs.next(),"literal_pointer_indirection",literal);
                    if(r!=null) {
                        r.put("pointer_value",toAddr(pointer).toString());
                        r.put("string_interior_offset",pointer-match.getKey());
                        loadedFrom.add(r);
                        ((List<Map<String,Object>>)row.get("code_references")).add(r);
                    }
                }
                Map<String,Object> p=new LinkedHashMap<>();p.put("address",literal.toString());p.put("value",toAddr(pointer).toString());
                p.put("source_file_offset",fileOffset(literal));p.put("string_interior_offset",pointer-match.getKey());p.put("code_reference_count",loadedFrom.size());
                ((List<Map<String,Object>>)row.get("pointer_references")).add(p);
            }
        }
        try(BufferedWriter w=Files.newBufferedWriter(out.resolve("string_xrefs.jsonl"))) {
            for(Map<String,Object> row:strings.values()) line(w,row);
        }
        println("STRINGS exported="+strings.size());return strings.size();
    }
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();if(args.length!=1)throw new IllegalArgumentException("export directory required");
        out=Paths.get(args[0]);Files.createDirectories(out.resolve("functions"));
        if(!Files.isRegularFile(out.resolve("mapped_image.json")) || !currentProgram.getLanguageID().toString().equals("Xtensa:LE:32:default") || currentProgram.getMemory().getBlock("DROM")==null || currentProgram.getFunctionManager().getFunctionAt(toAddr(0x40083200L))==null) throw new IOException("Fail closed: authenticated ESP32 mapping/entry not present");
        List<Function> functions=new ArrayList<>();
        FunctionIterator fit=currentProgram.getFunctionManager().getFunctions(true);
        while(fit.hasNext())functions.add(fit.next());
        println("FUNCTION INVENTORY discovered="+functions.size());
        AddressSet exec=new AddressSet();long initializedExec=0;
        List<Map<String,Object>> blocks=new ArrayList<>();
        for(MemoryBlock b:currentProgram.getMemory().getBlocks()) {
            Map<String,Object> row=new LinkedHashMap<>();row.put("name",b.getName());row.put("start",b.getStart().toString());row.put("end_inclusive",b.getEnd().toString());row.put("size",b.getSize());row.put("initialized",b.isInitialized());row.put("executable",b.isExecute());blocks.add(row);
            if(b.isInitialized()&&b.isExecute()){exec.add(b.getStart(),b.getEnd());initializedExec+=b.getSize();}
        }
        DecompInterface decompiler=new DecompInterface();DecompileOptions options=new DecompileOptions();options.grabFromProgram(currentProgram);decompiler.setOptions(options);
        decompiler.toggleCCode(true);decompiler.toggleSyntaxTree(false);decompiler.setSimplificationStyle("decompile");
        if(!decompiler.openProgram(currentProgram))throw new IOException("decompiler open failed: "+decompiler.getLastMessage());
        int success=0,fail=0,assembly=0,warningCount=0;long functionInstructionBytes=0;AddressSet covered=new AddressSet();
        try(BufferedWriter inventory=Files.newBufferedWriter(out.resolve("functions.jsonl"));BufferedWriter calls=Files.newBufferedWriter(out.resolve("calls.jsonl"))) {
            for(Function f:functions) {
                monitor.checkCancelled();String entry=f.getEntryPoint().toString();
                Map<String,Object> row=new LinkedHashMap<>();row.put("entry",entry);row.put("name",f.getName());row.put("external",f.isExternal());
                row.put("source_file_offset",fileOffset(f.getEntryPoint()));row.put("body_bytes",f.getBody().getNumAddresses());
                List<List<String>> ranges=new ArrayList<>();AddressRangeIterator rit=f.getBody().getAddressRanges();
                while(rit.hasNext()){AddressRange r=rit.next();ranges.add(Arrays.asList(r.getMinAddress().toString(),r.getMaxAddress().toString()));}
                row.put("body_ranges_inclusive",ranges);
                String asmPath="functions/"+entry+".asm";row.put("assembly_path",asmPath);int instructionCount=0;
                try(BufferedWriter asm=Files.newBufferedWriter(out.resolve(asmPath))) {
                    asm.write("; REAL Ghidra Xtensa disassembly; vendor app, not recovered source\n; function="+f.getName()+" entry="+entry+" source_file_offset=0x"+Long.toHexString(fileOffset(f.getEntryPoint()))+"\n");
                    InstructionIterator it=currentProgram.getListing().getInstructions(f.getBody(),true);
                    while(it.hasNext()) {
                        Instruction ins=it.next();instructionCount++;covered.add(ins.getAddress(),ins.getMaxAddress());functionInstructionBytes+=ins.getLength();
                        StringBuilder text=new StringBuilder();text.append(ins.getAddress()).append("  ").append(HexFormat.of().formatHex(ins.getBytes())).append("  ").append(ins.toString());
                        text.append(" ; source_file_offset=0x").append(Long.toHexString(fileOffset(ins.getAddress())));
                        for(Reference ref:ins.getReferencesFrom()) {
                            text.append(" ; ref=").append(ref.getToAddress()).append(":").append(ref.getReferenceType());
                            if(ref.getReferenceType().isCall()) {
                                Function target=currentProgram.getFunctionManager().getFunctionAt(ref.getToAddress());
                                Map<String,Object> call=new LinkedHashMap<>();call.put("caller",entry);call.put("instruction",ins.getAddress().toString());call.put("callee",ref.getToAddress().toString());call.put("callee_name",target==null?null:target.getName());call.put("type",ref.getReferenceType().toString());call.put("source_file_offset",fileOffset(ins.getAddress()));line(calls,call);
                            }
                        }
                        asm.write(text.toString());asm.newLine();
                    }
                }
                assembly++;row.put("instruction_count",instructionCount);
                long start=System.nanoTime();String error="";String code=null;
                try {
                    DecompileResults res=decompiler.decompileFunction(f,20,monitor);
                    error=res.getErrorMessage();if(error==null)error="";
                    if(res.decompileCompleted() && res.getDecompiledFunction()!=null)code=res.getDecompiledFunction().getC();
                    else if(error.isBlank())error="decompileCompleted=false; "+decompiler.getLastMessage();
                } catch(Exception e) {error=e.toString();decompiler.resetDecompiler();}
                row.put("decompile_ms",(System.nanoTime()-start)/1000000);
                boolean ok=code!=null&&!code.isBlank();row.put("decompile_ok",ok);row.put("decompile_error",error);
                if(ok) {
                    String cpath="functions/"+entry+".c";row.put("pseudocode_path",cpath);
                    Files.writeString(out.resolve(cpath),"/* REAL Ghidra pseudocode; inferred types and names; NOT recompilable original source.\n   Vendor SHA256 1aa9a0408e8a3bee568a45376eb2583fe35ba4daafc14880a8cf1531540066be\n   Entry "+entry+", source file offset 0x"+Long.toHexString(fileOffset(f.getEntryPoint()))+". */\n"+code);
                    boolean warning=!error.isBlank()||code.contains("WARNING:");row.put("warnings_present",warning);if(warning)warningCount++;success++;
                } else {
                    row.put("pseudocode_path",null);row.put("warnings_present",true);fail++;
                    Files.writeString(out.resolve("functions/"+entry+".error.txt"),error+"\n");
                }
                line(inventory,row);
                if((success+fail)%100==0){inventory.flush();calls.flush();println("EXPORT progress="+(success+fail)+"/"+functions.size()+" C="+success+" failures="+fail);}
            }
        } finally {decompiler.dispose();}
        int stringCount=exportStrings();
        long allInstructions=0,allInstructionBytes=0;
        InstructionIterator all=currentProgram.getListing().getInstructions(exec,true);
        while(all.hasNext()){Instruction ins=all.next();allInstructions++;allInstructionBytes+=ins.getLength();}
        Map<String,Object> summary=new LinkedHashMap<>();summary.put("ghidra_version",ghidra.framework.Application.getApplicationVersion());
        summary.put("program",currentProgram.getName());summary.put("language",currentProgram.getLanguageID().toString());
        summary.put("analysis_timed_out",analysisTimeoutOccurred());summary.put("discovered_functions",functions.size());summary.put("assembly_exported",assembly);summary.put("pseudocode_exported",success);summary.put("decompile_failures",fail);summary.put("successful_functions_with_warnings",warningCount);summary.put("decompile_timeout_seconds_per_function",20);
        summary.put("string_count",stringCount);summary.put("initialized_executable_segment_bytes",initializedExec);summary.put("all_disassembled_instruction_count",allInstructions);summary.put("all_disassembled_instruction_bytes",allInstructionBytes);summary.put("unique_function_instruction_bytes",covered.getNumAddresses());summary.put("summed_function_instruction_bytes_may_overlap",functionInstructionBytes);summary.put("memory_blocks",blocks);
        summary.put("coverage_warning","100% inventory export is NOT complete binary/source coverage; executable segments include literal pools. ENTRY seeds are heuristics; indirect callbacks, ROM and uninitialized RAM are incomplete. Decompiler types and parameter counts are inferred.");
        Files.writeString(out.resolve("summary.json"),new GsonBuilder().setPrettyPrinting().create().toJson(summary)+"\n");
        println("EXPORT COMPLETE "+gson.toJson(summary));
    }
}
