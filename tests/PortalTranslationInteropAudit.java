import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.function.Function;
import java.util.regex.*;

/** Actual JSON format preprocessing + actual Lua-global getText binding.
 * Args: mod42 privateAuditHome [--legacy-only]. No product Java/JAR dependency.
 * No game/world/UI/renderer or LuaManager.init/full script loading is invoked.
 */
public final class PortalTranslationInteropAudit {
    private static int checks;
    private static Object env,thread;
    private static Class<?> tableType,translator,languageType;
    private static Method compile,pcall,nativeFormat,fill,rawset;
    private static Constructor<?> languageConstructor;
    private static final Pattern SOURCE_PRINTF=Pattern.compile("%[1-9]\\$[sdf]");
    private static final Pattern NATIVE_ARGUMENT=Pattern.compile("%([1-9])\\$s");

    private static void check(boolean condition,String label) {
        ++checks;
        if (!condition) throw new AssertionError(label);
    }
    private static Field field(Class<?> type,String name) throws Exception {
        for (Class<?> c=type;c!=null;c=c.getSuperclass()) {
            try { Field f=c.getDeclaredField(name);f.setAccessible(true);return f; }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    private static String quote(String value) {
        return "\""+value.replace("\\","\\\\").replace("\"","\\\"")
                .replace("\r","\\r").replace("\n","\\n").replace("\t","\\t")+"\"";
    }
    private static String fromLua(String key,String... values) throws Exception {
        // LuaCompiler.loadstring's character reader is not a UTF-8 text
        // transport. Game UI passes names as runtime strings, so inject them
        // into the standalone environment rather than embedding Unicode in
        // source code. The actual native getText binding remains under test.
        rawset.invoke(env,"_SQP_translationKey",key);
        StringBuilder source=new StringBuilder("return getText(_SQP_translationKey");
        for (int i=0;i<values.length;i++) {
            String variable="_SQP_translationArg"+i;
            rawset.invoke(env,variable,values[i]);
            source.append(',').append(variable);
        }
        source.append(')');
        Object closure=compile.invoke(null,source.toString(),"actual global getText interop",env);
        Object[] result=(Object[])pcall.invoke(thread,closure,new Object[0]);
        check(Boolean.TRUE.equals(result[0]),"native global getText completes: "+key+" "+Arrays.toString(result));
        check(result.length>1 && result[1] instanceof String,"native global getText returns text: "+key);
        return (String)result[1];
    }
    @SuppressWarnings("unchecked")
    private static Map<String,String> load(Path root,String language,final boolean requireNativeSourceSyntax) throws Exception {
        Object lang=languageConstructor.newInstance(language,language,"EN",false);
        translator.getField("language").set(null,lang);
        final List<String> badSource=new ArrayList<String>();
        Function<String,String> realFixer=new Function<String,String>() {
            public String apply(String value) {
                if (SOURCE_PRINTF.matcher(value).find()) badSource.add(value);
                try { return (String)nativeFormat.invoke(null,value); }
                catch (Exception error) { throw new RuntimeException("native Translator.formatFixer",error); }
            }
        };
        Map<String,String> loaded=new HashMap<String,String>();
        fill.invoke(null,root.toString(),"IG_UI",loaded,lang,realFixer);
        check(!loaded.isEmpty(),"real JSON translation reader loaded "+language);
        if (requireNativeSourceSyntax) check(badSource.isEmpty(),"source must use %1..%4 before native formatFixer, not Java %1$s: "+badSource);
        Map<String,String> active=(Map<String,String>)field(translator,"igui").get(null);
        active.clear();active.putAll(loaded);
        return loaded;
    }
    private static void exact(String key,String expected,String... values) throws Exception {
        String actual=fromLua(key,values);
        check(expected.equals(actual),"exact localized output "+key+" expected=["+expected+"] actual=["+actual+"]");
    }

    public static void main(String[] args) throws Exception {
        if (args.length<2 || args.length>3) throw new IllegalArgumentException("Usage: PortalTranslationInteropAudit mod42 privateAuditHome [--legacy-only]");
        Path mod=Paths.get(args[0]).toAbsolutePath().normalize();
        Path home=Paths.get(args[1]).toAbsolutePath().normalize();
        boolean legacyOnly=args.length==3 && args[2].equals("--legacy-only");
        System.setProperty("user.home",home.toString());
        Class<?> fs=Class.forName("zombie.ZomboidFileSystem");
        fs.getMethod("setCacheDir",String.class).invoke(fs.getField("instance").get(null),home.resolve("cache").toString());
        check(!System.getProperty("java.class.path").toLowerCase(Locale.ENGLISH).contains("suqingportals.jar"),"no product helper jar in classpath");
        check(PortalTranslationInteropAudit.class.getClassLoader().getResource("suqing/portals/PortalBatteryCodec.class")==null,"old Portal codec is unavailable");

        Class<?> platformType=Class.forName("se.krka.kahlua.j2se.J2SEPlatform");
        Object platform=platformType.getConstructor().newInstance();
        env=platformType.getMethod("newEnvironment").invoke(platform);
        tableType=Class.forName("se.krka.kahlua.vm.KahluaTable");
        rawset=tableType.getMethod("rawset",Object.class,Object.class);
        Class<?> platformInterface=Class.forName("se.krka.kahlua.vm.Platform");
        Class<?> converters=Class.forName("se.krka.kahlua.converter.KahluaConverterManager");
        Object manager=converters.getConstructor().newInstance();
        Class<?> exposerType=Class.forName("se.krka.kahlua.integration.expose.LuaJavaClassExposer");
        Object exposer=exposerType.getConstructor(converters,platformInterface,tableType).newInstance(manager,platform,env);
        Class<?> globals=Class.forName("zombie.Lua.LuaManager$GlobalObject");
        Method expose=exposerType.getMethod("exposeGlobalClassFunction",tableType,Class.class,Method.class,String.class);
        int bindings=0;
        for (Method method:globals.getMethods()) {
            if (method.getName().equals("getText") && Modifier.isStatic(method.getModifiers())) {
                expose.invoke(exposer,env,globals,method,"getText");
                ++bindings;
            }
        }
        check(bindings>0,"actual GlobalObject.getText methods bound through LuaJavaClassExposer");
        Class<?> threadType=Class.forName("se.krka.kahlua.vm.KahluaThread");
        thread=threadType.getConstructor(platformInterface,tableType).newInstance(platform,env);
        threadType.getField("debugOwnerThread").set(thread,Thread.currentThread());
        compile=Class.forName("se.krka.kahlua.luaj.compiler.LuaCompiler").getMethod("loadstring",String.class,String.class,tableType);
        pcall=threadType.getMethod("pcall",Object.class,Object[].class);
        translator=Class.forName("zombie.core.Translator");languageType=Class.forName("zombie.core.Language");
        nativeFormat=translator.getDeclaredMethod("formatFixer",String.class);nativeFormat.setAccessible(true);
        fill=translator.getDeclaredMethod("tryFillMapFromFile",String.class,String.class,Map.class,languageType,Function.class);fill.setAccessible(true);
        languageConstructor=languageType.getDeclaredConstructor(String.class,String.class,String.class,boolean.class);languageConstructor.setAccessible(true);

        Path legacyRoot=home.resolve("legacy-json-fixture");
        String[] names={"SQP-5","中文基地","100% $s 门","基地 %1/%2 $1 $$ 中文","门 \\\"quote\\\" $ %"};
        String oldChinese=null;
        for (String language:Arrays.asList("CN","EN")) {
            boolean cn=language.equals("CN");
            Path json=legacyRoot.resolve("media/lua/shared/Translate/"+language+"/IG_UI.json");
            Files.createDirectories(json.getParent());
            String oldOpen=cn?"打开 %1$s 的传送门管理":"Manage portal: %1$s";
            String goodOpen=cn?"打开 %1 的传送门管理":"Manage portal: %1";
            String oldPercent=cn?"槽位 %1$s：电量 %2$s%%":"Slot %1$s: %2$s%% charge";
            String goodPercent=cn?"槽位 %1：电量 %2%%":"Slot %1: %2%% charge";
            String body="{\n\"IGUI_INTEROP_OldOpen\":"+quote(oldOpen)+",\n"
                    +"\"IGUI_INTEROP_GoodOpen\":"+quote(goodOpen)+",\n"
                    +"\"IGUI_INTEROP_OldPercent\":"+quote(oldPercent)+",\n"
                    +"\"IGUI_INTEROP_GoodPercent\":"+quote(goodPercent)+"\n}\n";
            Files.write(json,body.getBytes(StandardCharsets.UTF_8));
            Map<String,String> legacy=load(legacyRoot,language,false);
            check(legacy.get("IGUI_INTEROP_OldOpen").contains("%1$s$s"),"actual JSON formatFixer doubles legacy Java suffix "+language);
            String old=fromLua("IGUI_INTEROP_OldOpen","SQP-5");
            check(old.equals(cn?"打开 SQP-5$s 的传送门管理":"Manage portal: SQP-5$s"),"real Lua getText reproduces reported trailing $s "+language);
            if (cn) oldChinese=old;
            String oldP=fromLua("IGUI_INTEROP_OldPercent","4","50");
            check(oldP.contains("4$s") && oldP.contains("50$s%"),"legacy percent line reproduces suffix while %% renders one percent "+language);
            for (String name:names) exact("IGUI_INTEROP_GoodOpen",cn?"打开 "+name+" 的传送门管理":"Manage portal: "+name,name);
            for (String percent:Arrays.asList("0","50","100")) exact("IGUI_INTEROP_GoodPercent",cn?"槽位 4：电量 "+percent+"%":"Slot 4: "+percent+"% charge","4",percent);
        }

        int productKeys=0;
        if (!legacyOnly) for (String language:Arrays.asList("CN","EN")) {
            boolean cn=language.equals("CN");
            Map<String,String> loaded=load(mod,language,true);
            for (String name:names) {
                exact("IGUI_SQP_OpenNamed",cn?"打开 "+name+" 的传送门管理":"Manage portal: "+name,name);
                exact("IGUI_SQP_PortalIdentity",cn?name+"  |  编号 SQP-5":name+"  |  ID SQP-5",name,"SQP-5");
                exact("IGUI_SQP_Destination",cn?"目的地："+name:"Destination: "+name,name);
            }
            for (String percent:Arrays.asList("0","50","100")) {
                exact("IGUI_SQP_SlotInstalled",cn?"槽位 4：已安装 · 电量 "+percent+"%":"Slot 4: installed - "+percent+"% charge","4",percent);
                exact("IGUI_SQP_BatteryStats",cn?"电量 "+percent+"% · 耐久 80%":"Charge "+percent+"% - condition 80%",percent,"80");
                String name="电池 100% $s / %1";
                exact("IGUI_SQP_BatteryMenu",cn?" "+name+" · 电量 "+percent+"%":name+" - "+percent+"% charge",name,percent);
            }
            // Include newly added dynamic-cost keys without hardcoding their
            // wording. The oracle uses the actually preprocessed JSON format;
            // the call under test still crosses the real Lua global binding.
            for (String key:new TreeSet<String>(loaded.keySet())) {
                String template=loaded.get(key);
                Matcher matcher=NATIVE_ARGUMENT.matcher(template);
                int count=0;
                while (matcher.find()) count=Math.max(count,Integer.parseInt(matcher.group(1)));
                check(count<=9,"supported native positional parameter count "+key);
                String[] values=new String[count];
                for (int i=0;i<count;i++) values[i]=i==0?"Name 100%/$s/中文":Integer.toString(50+i);
                String expected=String.format(Locale.ROOT,template,(Object[])values);
                exact(key,expected,values);
                ++productKeys;
            }
        }
        System.out.println("TRANSLATION_INTEROP checks="+checks+" failures=0 old_error_reproduced=true productKeys="+productKeys+" legacy_only="+legacyOnly);
        System.out.println("EXPECTED_OLD_OUTPUT "+oldChinese);
        System.out.println("PASS real Translator JSON formatFixer, original LuaJavaClassExposer global getText, CN/EN native placeholders, %% and literal %/$/Chinese names.");
        System.out.println("Scope: native JSON preprocessing and real standalone Kahlua global binding only. No product JAR, game startup, LuaManager.init, world, renderer, UI or gameplay execution.");
    }
}
