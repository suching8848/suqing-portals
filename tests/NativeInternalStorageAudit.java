import java.lang.reflect.*;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;

/**
 * Standalone native persistence fixtures. No Portal jar, bridge, Lua mod code,
 * ScriptManager.Load, GameWindow.init, world, renderer, or UI startup.
 * Compile this reflection-only source with Java 8 and run with the installed
 * game Java 25; classpath must contain only its own classes and game.jar.
 */
public final class NativeInternalStorageAudit {
    private static final String TYPE = "suqingportal_internal";
    private static final int WORLD_VERSION = 249;
    private static int checks;
    private static Class<?> itemType, containerType, objectType;
    private static final Map<Integer,String> originalDisplayNames=new HashMap<Integer,String>();

    private static void check(boolean value, String reason) {
        ++checks;
        if (!value) throw new AssertionError(reason);
    }
    private static Field field(Class<?> type, String name) throws Exception {
        for (Class<?> c=type; c!=null; c=c.getSuperclass()) {
            try { Field f=c.getDeclaredField(name); f.setAccessible(true); return f; }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    private static Object call(Object target, String name, Class<?>[] types, Object... args) throws Exception {
        return target.getClass().getMethod(name, types).invoke(target, args);
    }
    private static void set(Object table, Object key, Object value) throws Exception {
        table.getClass().getMethod("rawset", Object.class, Object.class).invoke(table, key, value);
    }
    private static Object get(Object table, Object key) throws Exception {
        return table.getClass().getMethod("rawget", Object.class).invoke(table, key);
    }
    private static Object table() throws Exception {
        Object platform=field(Class.forName("zombie.Lua.LuaManager"),"platform").get(null);
        return platform.getClass().getMethod("newTable").invoke(platform);
    }

    @SuppressWarnings("unchecked")
    private static void fixtures() throws Exception {
        Class<?> random=Class.forName("zombie.core.random.RandStandard");
        random.getMethod("init").invoke(random.getField("INSTANCE").get(null));
        Class<?> moduleType=Class.forName("zombie.scripting.objects.ScriptModule");
        Object module=moduleType.getConstructor().newInstance();
        field(moduleType,"name").set(module,"Base");
        Class<?> managerType=Class.forName("zombie.scripting.ScriptManager");
        Object manager=managerType.getField("instance").get(null);
        ((Map<String,Object>)field(managerType,"moduleMap").get(manager)).put("Base",module);
        Object collection=field(managerType,"items").get(manager);
        Map<String,Object> all=(Map<String,Object>)call(collection,"getFullTypeToScriptMap",new Class<?>[]{});
        Object bucket=field(moduleType,"items").get(module);
        Map<String,Object> items=(Map<String,Object>)call(bucket,"getScriptMap",new Class<?>[]{});
        Class<?> scriptType=Class.forName("zombie.scripting.objects.Item");
        Class<?> kind=Class.forName("zombie.scripting.objects.ItemType");
        Class<?> infoType=Class.forName("zombie.world.ItemInfo");
        Class<?> dictionary=Class.forName("zombie.world.WorldDictionary");
        Object data=field(dictionary,"data").get(null);
        if (data==null) {
            Constructor<?> ctor=Class.forName("zombie.world.DictionaryData").getDeclaredConstructor();
            ctor.setAccessible(true); data=ctor.newInstance(); field(dictionary,"data").set(null,data);
        }
        for (int n=1;n<=3;n++) {
            String name="CarBattery"+n, full="Base."+name;
            short registry=(short)(122+n);
            Object script=scriptType.getConstructor().newInstance();
            field(scriptType,"module").set(script,module);
            field(scriptType,"name").set(script,name);
            field(scriptType,"moduleDotType").set(script,full);
            field(scriptType,"scriptObjectName").set(script,name);
            call(script,"setItemType",new Class<?>[]{kind},kind.getField("DRAINABLE").get(null));
            call(script,"setRegistry_id",new Class<?>[]{short.class},registry);
            call(script,"setUseDelta",new Class<?>[]{float.class},0.00001f);
            call(script,"setConditionMax",new Class<?>[]{int.class},100);
            call(script,"setDisplayName",new Class<?>[]{String.class},"Native internal battery "+n);
            items.put(name,script); all.put(full,script);
            Object info=infoType.getConstructor().newInstance();
            field(infoType,"scriptItem").set(info,script);
            field(infoType,"entityScript").set(info,script);
            field(infoType,"name").set(info,name);
            field(infoType,"moduleName").set(info,"Base");
            field(infoType,"fullType").set(info,full);
            field(infoType,"registryId").set(info,registry);
            field(infoType,"isLoaded").set(info,true);
            ((Map<Short,Object>)field(data.getClass(),"itemIdToInfoMap").get(data)).put(registry,info);
            ((Map<String,Object>)field(data.getClass(),"itemTypeToInfoMap").get(data)).put(full,info);
        }
        itemType=Class.forName("zombie.inventory.InventoryItem");
        containerType=Class.forName("zombie.inventory.ItemContainer");
        objectType=Class.forName("zombie.iso.IsoObject");
    }

    private static Object item(int slot) throws Exception {
        String full="Base.CarBattery"+(slot%3+1);
        Object item=Class.forName("zombie.inventory.InventoryItemFactory")
                .getMethod("CreateItem",String.class).invoke(null,full);
        check(item!=null,"native factory creates battery slot "+slot);
        call(item,"setID",new Class<?>[]{int.class},8421000+slot);
        call(item,"setCondition",new Class<?>[]{int.class},new int[]{100,37,82,9}[slot]);
        call(item,"setUsedDelta",new Class<?>[]{float.class},new float[]{1f,.71345f,.25125f,.001f}[slot]);
        call(item,"setName",new Class<?>[]{String.class},"原件电池 / slot "+(slot+1));
        call(item,"setCustomName",new Class<?>[]{boolean.class},true);
        originalDisplayNames.put(8421000+slot,(String)call(item,"getName",new Class<?>[]{}));
        Object md=call(item,"getModData",new Class<?>[]{}), nested=table();
        set(md,"auditOriginalSlot",Double.valueOf(slot+1));
        set(md,"auditBoolean",Boolean.valueOf(slot%2==0));
        set(nested,"note","nested original state "+slot);
        set(md,"auditNested",nested);
        return item;
    }

    private static Object container(Object parent) throws Exception {
        Object c=containerType.getConstructor(String.class,Class.forName("zombie.iso.IsoGridSquare"),objectType)
                .newInstance(TYPE,null,parent);
        call(c,"setCapacity",new Class<?>[]{int.class},40);
        call(c,"setExplored",new Class<?>[]{boolean.class},true);
        call(parent,"setContainer",new Class<?>[]{containerType},c);
        return c;
    }

    private static void verifyItems(Object container, Object slots, String scope) throws Exception {
        check(TYPE.equals(call(container,"getType",new Class<?>[]{})),scope+" native container type retained");
        List<?> items=(List<?>)call(container,"getItems",new Class<?>[]{});
        check(items.size()==4,scope+" four battery instances retained");
        Map<Integer,Object> byId=new HashMap<Integer,Object>();
        for (Object item:items) {
            int id=((Number)call(item,"getID",new Class<?>[]{})).intValue();
            check(byId.put(id,item)==null,scope+" distinct original item IDs");
            check(call(item,"getContainer",new Class<?>[]{})==container,scope+" restored battery has correct native owner");
        }
        for (int slot=0;slot<4;slot++) {
            int id=8421000+slot;
            Object battery=byId.get(id);
            check(battery!=null,scope+" original item ID "+id);
            check(("Base.CarBattery"+(slot%3+1)).equals(call(battery,"getFullType",new Class<?>[]{})),scope+" full type "+slot);
            check(((Number)call(battery,"getCondition",new Class<?>[]{})).intValue()==new int[]{100,37,82,9}[slot],scope+" condition "+slot);
            double actual=((Number)call(battery,"getCurrentUsesFloat",new Class<?>[]{})).doubleValue();
            check(Math.abs(actual-new float[]{1f,.71345f,.25125f,.001f}[slot])<0.0001,scope+" charge "+slot);
            check(("原件电池 / slot "+(slot+1)).equals(field(itemType,"name").get(battery)),scope+" raw custom Unicode name "+slot);
            check(Boolean.TRUE.equals(call(battery,"isCustomName",new Class<?>[]{})),scope+" custom-name flag "+slot);
            check(originalDisplayNames.get(id).equals(call(battery,"getName",new Class<?>[]{})),scope+" native derived display name "+slot);
            Object md=call(battery,"getModData",new Class<?>[]{});
            check(Double.valueOf(slot+1).equals(get(md,"auditOriginalSlot")),scope+" numeric ModData "+slot);
            check(Boolean.valueOf(slot%2==0).equals(get(md,"auditBoolean")),scope+" boolean ModData "+slot);
            check(("nested original state "+slot).equals(get(get(md,"auditNested"),"note")),scope+" nested ModData "+slot);
            if (slots!=null) check(((Number)get(slots,Double.valueOf(slot+1))).intValue()==id,scope+" saved slot maps original item ID "+slot);
        }
    }

    private static void nativeRejectFunction(Object container, Object original) throws Exception {
        Class<?> lua=Class.forName("zombie.Lua.LuaManager");
        Object oldEnv=field(lua,"env").get(null), oldThread=field(lua,"thread").get(null);
        Object env=table(), platform=field(lua,"platform").get(null);
        Class<?> javaFunction=Class.forName("se.krka.kahlua.vm.JavaFunction");
        Object deny=Proxy.newProxyInstance(javaFunction.getClassLoader(),new Class<?>[]{javaFunction},
                new InvocationHandler() { public Object invoke(Object proxy,Method method,Object[] args) throws Throwable {
                    if (method.getName().equals("call")) {
                        args[0].getClass().getMethod("push",Object.class).invoke(args[0],Boolean.FALSE);
                        return Integer.valueOf(1);
                    }
                    if (method.getName().equals("toString")) return "Native storage audit reject function";
                    if (method.getName().equals("hashCode")) return System.identityHashCode(proxy);
                    if (method.getName().equals("equals")) return proxy==args[0];
                    throw new UnsupportedOperationException(method.toString());
                }});
        String functionName="SuQingPortals.BatterySlots.AcceptItem";
        Object portalNamespace=table(), slotNamespace=table();
        set(slotNamespace,"AcceptItem",deny);
        set(portalNamespace,"BatterySlots",slotNamespace);
        set(env,"SuQingPortals",portalNamespace);
        Object thread=Class.forName("se.krka.kahlua.vm.KahluaThread")
                .getConstructor(Class.forName("se.krka.kahlua.vm.Platform"),Class.forName("se.krka.kahlua.vm.KahluaTable"))
                .newInstance(platform,env);
        field(thread.getClass(),"debugOwnerThread").set(thread,Thread.currentThread());
        field(lua,"env").set(null,env); field(lua,"thread").set(null,thread);
        try {
            call(container,"setAcceptItemFunction",new Class<?>[]{String.class},functionName);
            check(Boolean.FALSE.equals(call(container,"isItemAllowed",new Class<?>[]{itemType},original)),
                    "minimal standalone function rejects normal native isItemAllowed");
            call(container,"Remove",new Class<?>[]{itemType},original);
            check(call(original,"getContainer",new Class<?>[]{})==null,"backend Remove releases original despite UI accept function");
            call(container,"AddItem",new Class<?>[]{itemType},original);
            check(call(original,"getContainer",new Class<?>[]{})==container,"backend AddItem restores same original despite UI accept function");
        } finally {
            call(container,"setAcceptItemFunction",new Class<?>[]{String.class},(Object)null);
            field(lua,"env").set(null,oldEnv); field(lua,"thread").set(null,oldThread);
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length!=1) throw new IllegalArgumentException("Usage: NativeInternalStorageAudit auditHome");
        Path home=Paths.get(args[0]).toAbsolutePath().normalize();
        System.setProperty("user.home",home.toString());
        Class<?> fs=Class.forName("zombie.ZomboidFileSystem");
        fs.getMethod("setCacheDir",String.class).invoke(fs.getField("instance").get(null),home.resolve("cache").toString());
        String cp=System.getProperty("java.class.path");
        check(!cp.toLowerCase(Locale.ENGLISH).contains("suqingportals.jar"),"classpath has no product Portal jar");
        check(NativeInternalStorageAudit.class.getClassLoader().getResource("suqing/portals/PortalBatteryCodec.class")==null,
                "old Portal codec/bridge class is unavailable");
        fixtures();
        Object object=objectType.getConstructor().newInstance();
        Object container=container(object);
        Object slots=table(), portal=table(), internal=table();
        set(portal,"schema",Double.valueOf(3));
        set(internal,"schema",Double.valueOf(3));
        set(internal,"containerType",TYPE);
        set(internal,"slots",slots); set(portal,"internalStorage",internal);
        set(call(object,"getModData",new Class<?>[]{}),"SuQingPortals",portal);
        Object[] originals=new Object[4];
        for (int slot=0;slot<4;slot++) {
            originals[slot]=item(slot);
            call(container,"AddItem",new Class<?>[]{itemType},originals[slot]);
            set(slots,Double.valueOf(slot+1),Double.valueOf(8421000+slot));
        }
        nativeRejectFunction(container,originals[0]);
        verifyItems(container,slots,"before save");

        ByteBuffer bytes=ByteBuffer.allocate(2*1024*1024);
        call(container,"save",new Class<?>[]{ByteBuffer.class},bytes);
        int containerBytes=bytes.position(); bytes.flip();
        Object newObject=objectType.getConstructor().newInstance(), restoredContainer=container(newObject);
        call(restoredContainer,"load",new Class<?>[]{ByteBuffer.class,int.class},bytes,WORLD_VERSION);
        check(!bytes.hasRemaining(),"native ItemContainer load consumes exact bytes");
        verifyItems(restoredContainer,slots,"native ItemContainer roundtrip");
        for (Object original:originals) {
            check(!((List<?>)call(restoredContainer,"getItems",new Class<?>[]{})).contains(original),
                    "native reload creates persisted instances rather than reusing fixture references");
        }

        // Give the serialized IsoObject a texture-free registered sprite. This
        // exercises the normal object container/ModData fields without GL.
        Class<?> manager=Class.forName("zombie.iso.sprite.IsoSpriteManager");
        Object sprite=call(manager.getField("instance").get(null),"AddSprite",new Class<?>[]{String.class,int.class},"suqingportal_internal_audit",61007);
        call(object,"setSprite",new Class<?>[]{Class.forName("zombie.iso.sprite.IsoSprite")},sprite);
        bytes.clear();
        call(object,"save",new Class<?>[]{ByteBuffer.class,boolean.class},bytes,false);
        int objectBytes=bytes.position(); bytes.flip();
        Object restored=objectType.getMethod("factoryFromFileInput",Class.forName("zombie.iso.IsoCell"),ByteBuffer.class)
                .invoke(null,null,bytes);
        check(restored!=null,"normal native IsoObject factory reads saved type header");
        call(restored,"load",new Class<?>[]{ByteBuffer.class,int.class,boolean.class},bytes,WORLD_VERSION,false);
        check(!bytes.hasRemaining(),"normal native IsoObject load consumes exact bytes");
        Object restoredPortal=get(call(restored,"getModData",new Class<?>[]{}),"SuQingPortals");
        Object restoredInternal=get(restoredPortal,"internalStorage");
        check(Double.valueOf(3).equals(get(restoredPortal,"schema")),"native object portal schema3 metadata persists");
        check(TYPE.equals(get(restoredInternal,"containerType")),"native object internal storage type metadata persists");
        verifyItems(call(restored,"getContainer",new Class<?>[]{}),get(restoredInternal,"slots"),"normal IsoObject roundtrip");
        check(call(restored,"getContainerCount",new Class<?>[]{}).equals(1),"normal native object retains one internal container");
        System.out.println("NATIVE_INTERNAL_STORAGE checks="+checks+" failures=0 containerBytes="+containerBytes+" objectBytes="+objectBytes+" format="+WORLD_VERSION);
        System.out.println("PASS original four IDs/types/charge/condition/custom Unicode names/nested ModData and slot-ID mapping retained through native object save/load.");
        System.out.println("PASS normal isItemAllowed rejection does not prevent dedicated backend direct AddItem/Remove of the original instance.");
        System.out.println("Scope: minimal standalone ScriptItem fixtures + current native persistence + one standalone reject JavaFunction. No product jar/codec, ScriptManager.Load, GameWindow.init, Lua mod files, world, GL, UI, game startup, or running-game interaction.");
    }
}
