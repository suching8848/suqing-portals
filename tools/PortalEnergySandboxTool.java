import java.lang.reflect.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

/** Native config/string parsers only. Never instantiates SandboxOptions, GameTime or IsoWorld. */
public final class PortalEnergySandboxTool {
    static Object codec;
    static Method loadString, saveString;
    static final class Sand {
        byte[] bytes;
        Map<String,String> values = new LinkedHashMap<String,String>();
        int start, end, count;
        String preset;
    }
    static String readString(ByteBuffer input) throws Exception {
        return (String)loadString.invoke(codec, input);
    }
    static Sand read(Path file) throws Exception {
        Sand s = new Sand(); s.bytes=Files.readAllBytes(file);
        ByteBuffer b=ByteBuffer.wrap(s.bytes);
        if(b.getInt()!=0x53414e44 || b.getInt()!=249 || b.getInt()!=6) throw new Exception("Unsupported SAND header; inspect current native format first");
        s.count=b.getInt();
        if(s.count<1 || s.count>10000) throw new Exception("Invalid sandbox option count");
        for(int i=0;i<s.count;i++) {
            String key=readString(b); int start=b.position(); String value=readString(b);
            if(s.values.put(key,value)!=null) throw new Exception("Duplicate sandbox key: "+key);
            if("ElecShutModifier".equals(key)) {s.start=start;s.end=b.position();}
        }
        s.preset=readString(b);
        if(b.hasRemaining() || s.start==0) throw new Exception("Unexpected sandbox tail or missing shutdown modifier");
        return s;
    }
    static String quoted(String text) {return "\""+text.replace("\\","\\\\").replace("\"","\\\"").replace("\r","\\r").replace("\n","\\n")+"\"";}
    public static void main(String[] args) throws Exception {
        if(args.length<4 || (!"inspect".equals(args[0]) && !"rewrite".equals(args[0]))) throw new Exception("Usage: inspect|rewrite map_sand.bin map_t.bin mods.txt [output-map_sand.bin]");
        Class<?> c=Class.forName("zombie.GameWindow$StringUTF");
        Constructor<?> ctor=c.getDeclaredConstructor();ctor.setAccessible(true);codec=ctor.newInstance();
        loadString=c.getDeclaredMethod("load",ByteBuffer.class);loadString.setAccessible(true);
        saveString=c.getDeclaredMethod("save",ByteBuffer.class,String.class);saveString.setAccessible(true);
        Sand before=read(Paths.get(args[1]));
        Class<?> integer=Class.forName("zombie.config.IntegerConfigOption");
        Object option=integer.getConstructor(String.class,int.class,int.class,int.class).newInstance("ElecShutModifier",-1,Integer.MAX_VALUE,14);
        Method parse=integer.getMethod("parse",String.class), value=integer.getMethod("getValueAsString");
        parse.invoke(option,before.values.get("ElecShutModifier"));
        if(!before.values.get("ElecShutModifier").equals(value.invoke(option))) throw new Exception("Existing shutdown option fails native integer readback");
        parse.invoke(option,"-1");
        if(!"-1".equals(value.invoke(option))) throw new Exception("Native integer option rejects immediate shutdown -1");
        ByteBuffer time=ByteBuffer.wrap(Files.readAllBytes(Paths.get(args[2])));
        if(time.getInt()!=0x474d544d || time.getInt()!=249) throw new Exception("Unsupported GMTM header");
        float multiplier=time.getFloat();int nights=time.getInt();time.getInt();time.getFloat();float tod=time.getFloat();
        int apo=Integer.parseInt(before.values.get("TimeSinceApo"));
        if(nights<0 || !Float.isFinite(tod) || tod<0 || tod>=24 || apo<1) throw new Exception("Cannot prove non-negative saved world age");
        float worldHours=nights*24.0f+(tod>=7.0f?tod-7.0f:tod+17.0f);
        float worldAge=(float)(worldHours/24.0+(apo-1)*30);
        if(!Float.isFinite(worldAge) || worldAge<0) throw new Exception("Invalid saved world age");
        Class<?> active=Class.forName("zombie.modding.ActiveMods");
        Object mods=active.getConstructor(String.class).newInstance("SuQingEnergyTemplateOffline");
        Class<?> modsFile=Class.forName("zombie.modding.ActiveModsFile");
        if(!Boolean.TRUE.equals(modsFile.getMethod("read",String.class,active).invoke(modsFile.getConstructor().newInstance(),args[3],mods))) throw new Exception("Native enabled-mod parser failed");
        List<?> order=(List<?>)active.getMethod("getMods").invoke(mods);
        StringBuilder ids=new StringBuilder("[");for(Object id:order){if(ids.length()>1)ids.append(',');ids.append(quoted(String.valueOf(id)));}ids.append(']');
        boolean wrote=false;
        if("rewrite".equals(args[0])) {
            if(args.length!=5) throw new Exception("Rewrite requires an explicit output path");
            ByteBuffer encoded=ByteBuffer.allocate(64);saveString.invoke(codec,encoded,"-1");
            byte[] replacement=Arrays.copyOf(encoded.array(),encoded.position());
            byte[] changed=new byte[before.bytes.length-(before.end-before.start)+replacement.length];
            System.arraycopy(before.bytes,0,changed,0,before.start);
            System.arraycopy(replacement,0,changed,before.start,replacement.length);
            System.arraycopy(before.bytes,before.end,changed,before.start+replacement.length,before.bytes.length-before.end);
            Path output=Paths.get(args[4]);Files.write(output,changed);
            Sand after=read(output);Map<String,String> expected=new LinkedHashMap<String,String>(before.values);expected.put("ElecShutModifier","-1");
            if(!expected.equals(after.values) || !before.preset.equals(after.preset) || before.count!=after.count) throw new Exception("Unexpected sandbox option or preset change");
            wrote=true;
        }
        System.out.println("ENERGY_SANDBOX_JSON:"+"{\"result\":\"PASS\",\"sandbox_world_version\":249,\"options_version\":6,\"options\":"+before.count+
            ",\"previous_modifier\":"+quoted(before.values.get("ElecShutModifier"))+",\"new_modifier\":-1,\"native_integer_parser\":true,\"native_string_codec\":true,\"unknown_options_preserved\":true,"+
            "\"preset\":"+quoted(before.preset)+",\"nights_survived\":"+nights+",\"time_of_day\":"+tod+",\"world_age_days\":"+worldAge+
            ",\"does_power_grid_exist_after\":false,\"native_mod_order\":"+ids+",\"wrote_sandbox\":"+wrote+",\"world_instantiated\":false}");
    }
}
