import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/**
 * Real Kahlua/Java-userdata boundary regression. Product ships no Java helper.
 * Arguments: absolute mod 42 directory, private audit home.
 * The selection provider is a fixture; its results are real native ClickObject
 * and IsoObject instances. No live screen picker, world, renderer or UI is run.
 */
public final class PortalPickerInteropAudit {
    private static int checks;
    private static Class<?> tableType;
    private static Object env, thread;
    private static Method compiler, pcall;

    public static final class FixturePicker {
        public Object click;
        public Object selected;
        public int contextCalls;
        public int thumpableCalls;
        public Object ContextPick(Object x, Object y) {
            ++contextCalls;
            return click;
        }
        public Object PickThumpable(Object x, Object y) {
            ++thumpableCalls;
            return selected;
        }
    }

    private static void check(boolean value,String label) {
        ++checks;
        if (!value) throw new AssertionError(label);
    }
    private static Object invoke(Object target,String name,Class<?>[] types,Object... args) throws Exception {
        return target.getClass().getMethod(name,types).invoke(target,args);
    }
    private static Object[] eval(String source,String name) throws Exception {
        Object closure=compiler.invoke(null,source,name,env);
        Object[] result=(Object[])pcall.invoke(thread,closure,new Object[0]);
        if (!Boolean.TRUE.equals(result[0])) throw new AssertionError(name+": "+Arrays.toString(result));
        ++checks;
        return result;
    }
    private static void load(Path source) throws Exception {
        eval(new String(Files.readAllBytes(source),StandardCharsets.UTF_8),source.toString());
    }
    private static void put(String key,Object value) throws Exception {
        tableType.getMethod("rawset",Object.class,Object.class).invoke(env,key,value);
    }

    public static void main(String[] args) throws Exception {
        if (args.length!=2) throw new IllegalArgumentException("Usage: PortalPickerInteropAudit mod42 auditHome");
        Path mod=Paths.get(args[0]).toAbsolutePath().normalize();
        Path home=Paths.get(args[1]).toAbsolutePath().normalize();
        System.setProperty("user.home",home.toString());
        Class<?> fs=Class.forName("zombie.ZomboidFileSystem");
        fs.getMethod("setCacheDir",String.class).invoke(fs.getField("instance").get(null),home.resolve("cache").toString());
        check(!System.getProperty("java.class.path").toLowerCase(Locale.ENGLISH).contains("suqingportals.jar"),"no product helper jar in classpath");
        check(PortalPickerInteropAudit.class.getClassLoader().getResource("suqing/portals/PortalBatteryCodec.class")==null,"no old product codec/bridge available");

        Class<?> platformType=Class.forName("se.krka.kahlua.j2se.J2SEPlatform");
        Object platform=platformType.getConstructor().newInstance();
        env=platformType.getMethod("newEnvironment").invoke(platform);
        tableType=Class.forName("se.krka.kahlua.vm.KahluaTable");
        Class<?> platformInterface=Class.forName("se.krka.kahlua.vm.Platform");
        Class<?> converters=Class.forName("se.krka.kahlua.converter.KahluaConverterManager");
        Object manager=converters.getConstructor().newInstance();
        Class<?> exposerType=Class.forName("se.krka.kahlua.integration.expose.LuaJavaClassExposer");
        Object exposer=exposerType.getConstructor(converters,platformInterface,tableType).newInstance(manager,platform,env);
        // This fork's base exposer defaults to an empty allowlist. Whitelist
        // only these three fixture/result classes instead of exposeAll or
        // recursively exposing the full game's type graph.
        Class<?> objectType=Class.forName("zombie.iso.IsoObject");
        Class<?> spriteType=Class.forName("zombie.iso.sprite.IsoSprite");
        Field allowedField=exposerType.getDeclaredField("shouldExposeCache"); allowedField.setAccessible(true);
        @SuppressWarnings("unchecked") Map<Class<?>,Boolean> allowed=(Map<Class<?>,Boolean>)allowedField.get(exposer);
        allowed.put(FixturePicker.class,Boolean.TRUE);
        allowed.put(objectType,Boolean.TRUE);
        allowed.put(spriteType,Boolean.TRUE);
        Method expose=exposerType.getMethod("exposeLikeJava",Class.class,tableType);
        expose.invoke(exposer,FixturePicker.class,env);
        expose.invoke(exposer,objectType,env);
        expose.invoke(exposer,spriteType,env);

        Class<?> threadType=Class.forName("se.krka.kahlua.vm.KahluaThread");
        thread=threadType.getConstructor(platformInterface,tableType).newInstance(platform,env);
        threadType.getField("debugOwnerThread").set(thread,Thread.currentThread());
        compiler=Class.forName("se.krka.kahlua.luaj.compiler.LuaCompiler").getMethod("loadstring",String.class,String.class,tableType);
        pcall=threadType.getMethod("pcall",Object.class,Object[].class);

        // Inspect the actual public API without creating the live picker.
        ClassLoader loader=PortalPickerInteropAudit.class.getClassLoader();
        Class<?> pickerType=Class.forName("zombie.iso.IsoObjectPicker",false,loader);
        Class<?> clickType=Class.forName("zombie.iso.IsoObjectPicker$ClickObject");
        check(pickerType.getMethod("ContextPick",int.class,int.class).getReturnType()==clickType,"native ContextPick returns ClickObject");
        check(pickerType.getMethod("PickThumpable",int.class,int.class).getReturnType()==objectType,"native PickThumpable publicly returns IsoObject");
        boolean getter=false;
        for (Method method:clickType.getMethods()) {
            if (method.getName().equals("getTile") || method.getName().equals("getObject")) getter=true;
        }
        check(!getter,"ClickObject has no invented tile/object getter");

        Class<?> sprites=Class.forName("zombie.iso.sprite.IsoSpriteManager");
        Object spriteManager=sprites.getField("instance").get(null);
        Method addSprite=sprites.getMethod("AddSprite",String.class,int.class);
        Object portalSprite=addSprite.invoke(spriteManager,"suqing_portal_01_60",61031);
        Object otherSprite=addSprite.invoke(spriteManager,"native_interop_other_0",61032);
        spriteType.getField("name").set(portalSprite,"suqing_portal_01_60");
        spriteType.getField("name").set(otherSprite,"native_interop_other_0");
        Object portal=objectType.getConstructor().newInstance();
        Object other=objectType.getConstructor().newInstance();
        invoke(portal,"setSprite",new Class<?>[]{spriteType},portalSprite);
        invoke(other,"setSprite",new Class<?>[]{spriteType},otherSprite);
        Object click=clickType.getConstructor().newInstance();
        clickType.getField("tile").set(click,portal);
        check(clickType.getField("tile").get(click)==portal,"actual public Java tile field contains native IsoObject");

        FixturePicker fixture=new FixturePicker();
        fixture.click=click;fixture.selected=portal;
        put("fixturePicker",fixture);put("nativeClick",click);put("nativePortal",portal);put("nativeOther",other);
        eval("assert(type(nativeClick)=='userdata' and type(fixturePicker)=='userdata', 'real Java userdata required');\n"
                +"require=function() end; SuQingPortals={Core={},World={},UI={},Transfer={},Actions={}};\n"
                +"Events={OnFillWorldObjectContextMenu={Add=function() end}};\n"
                +"IsoObjectPicker={Instance=fixturePicker}; Viewpoint=nil;\n"
                +"isClient=function() return false end; isServer=function() return false end;\n",
                "interop bootstrap");

        Object[] legacy=eval("local picked=fixturePicker:ContextPick(17,22); assert(picked==nativeClick);\n"
                +"local ok,err=pcall(function() return picked.tile end);\n"
                +"assert(not ok and err~=nil, 'unexposed native ClickObject field must reproduce failure');\n"
                +"return tostring(err)","legacy Java userdata field regression");
        String legacyError=String.valueOf(legacy[1]);
        check(fixture.contextCalls==1,"legacy failure came through a real exposed Java method return");
        fixture.contextCalls=0;fixture.thumpableCalls=0;
        load(mod.resolve("media/lua/client/SuQingPortals/Build.lua"));
        load(mod.resolve("media/lua/client/SuQingPortals/Client.lua"));
        eval("assert(SuQingPortals.Build.isPortal(nativePortal), 'real native sprite/name classifies portal'); assert(not SuQingPortals.Build.isPortal(nativeOther), 'real native other sprite rejected');\n"
                +"local found=SuQingPortals.Client.findPortals(0,{},17,22);\n"
                +"assert(#found==1 and found[1]==nativePortal, 'fixed direct Java IsoObject method path');",
                "fixed product picker direct object");
        check(fixture.contextCalls==0 && fixture.thumpableCalls==1,"fixed product bypasses ClickObject entirely");
        fixture.selected=null;
        eval("local found=SuQingPortals.Client.findPortals(0,{nativePortal,nativeOther},17,22);\n"
                +"assert(#found==1 and found[1]==nativePortal, 'native worldObjects fallback remains available');",
                "fixed native worldObjects fallback");
        fixture.selected=other;
        eval("local found=SuQingPortals.Client.findPortals(0,{},17,22);\n"
                +"assert(#found==0, 'nonportal native object does not gain portal menu');",
                "nonportal Java object regression");
        fixture.selected=portal;
        eval("Viewpoint={View={next=function() return 'third' end}};\n"
                +"local found=SuQingPortals.Client.findPortals(0,{},17,22);\n"
                +"assert(#found==1 and found[1]==nativePortal, '3D mode still accepts native object selection');",
                "3D native object selection interop");
        check(fixture.contextCalls==0,"no repaired path reintroduced opaque ClickObject field access");
        System.out.println("PICKER_INTEROP checks="+checks+" failures=0 old_error_reproduced=true");
        System.out.println("EXPECTED_OLD_ERROR "+legacyError.replace('\n',' ').replace('\r',' '));
        System.out.println("PASS product Build/Client uses public Java methods on real native IsoObject; no ClickObject field/getter reconstruction.");
        System.out.println("Scope: real native ClickObject/IsoObject userdata, current LuaJavaClassExposer and standalone Kahlua. Selection provider is a fixture; screen picking, camera projection, world, GL, renderer, UI, GameWindow.init and gameplay are not executed.");
    }
}
