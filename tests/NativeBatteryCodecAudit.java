import java.lang.reflect.*;
import java.nio.*;
import java.util.*;
import suqing.portals.PortalBatteryCodec;

/** Isolated native item fixtures, not ScriptManager.Load/world/game/UI startup. */
public final class NativeBatteryCodecAudit {
    static int checks;
    static void check(boolean value, String reason) { checks++; if (!value) throw new AssertionError(reason); }
    static Field field(Class<?> type, String name) throws Exception {
        for (Class<?> current=type;current!=null;current=current.getSuperclass()) {
            try { Field f=current.getDeclaredField(name);f.setAccessible(true);return f; }
            catch(NoSuchFieldException missing) { }
        }
        throw new NoSuchFieldException(name);
    }
    static Object call(Object target, String name, Class<?>[] types, Object... args) throws Exception {
        return target.getClass().getMethod(name,types).invoke(target,args);
    }
    @SuppressWarnings("unchecked")
    static Object fixture() throws Exception {
        Class<?> random=Class.forName("zombie.core.random.RandStandard");
        random.getMethod("init").invoke(random.getField("INSTANCE").get(null));
        Class<?> moduleType=Class.forName("zombie.scripting.objects.ScriptModule");
        Object module=moduleType.getConstructor().newInstance();
        field(moduleType,"name").set(module,"Base");
        Class<?> scriptType=Class.forName("zombie.scripting.objects.Item");
        Object script=scriptType.getConstructor().newInstance();
        field(scriptType,"module").set(script,module);
        field(scriptType,"name").set(script,"CarBattery1");
        field(scriptType,"moduleDotType").set(script,"Base.CarBattery1");
        field(scriptType,"scriptObjectName").set(script,"CarBattery1");
        Class<?> itemKind=Class.forName("zombie.scripting.objects.ItemType");
        call(script,"setItemType",new Class<?>[]{itemKind},itemKind.getField("DRAINABLE").get(null));
        call(script,"setRegistry_id",new Class<?>[]{short.class},(short)123);
        call(script,"setUseDelta",new Class<?>[]{float.class},0.00001f);
        call(script,"setConditionMax",new Class<?>[]{int.class},100);
        call(script,"setDisplayName",new Class<?>[]{String.class},"Native Battery Audit");
        Object bucket=field(moduleType,"items").get(module);
        ((Map<String,Object>)call(bucket,"getScriptMap",new Class<?>[]{})).put("CarBattery1",script);
        Class<?> managerType=Class.forName("zombie.scripting.ScriptManager");
        Object manager=managerType.getField("instance").get(null);
        ((Map<String,Object>)field(managerType,"moduleMap").get(manager)).put("Base",module);
        Object collection=field(managerType,"items").get(manager);
        ((Map<String,Object>)call(collection,"getFullTypeToScriptMap",new Class<?>[]{})).put("Base.CarBattery1",script);
        Class<?> infoType=Class.forName("zombie.world.ItemInfo");
        Object info=infoType.getConstructor().newInstance();
        field(infoType,"scriptItem").set(info,script);
        field(infoType,"entityScript").set(info,script);
        field(infoType,"name").set(info,"CarBattery1");
        field(infoType,"moduleName").set(info,"Base");
        field(infoType,"fullType").set(info,"Base.CarBattery1");
        field(infoType,"registryId").set(info,(short)123);
        field(infoType,"isLoaded").set(info,true);
        Class<?> dictionary=Class.forName("zombie.world.WorldDictionary");
        Object data=field(dictionary,"data").get(null);
        if(data==null) {
            Constructor<?> ctor=Class.forName("zombie.world.DictionaryData").getDeclaredConstructor();ctor.setAccessible(true);
            data=ctor.newInstance();field(dictionary,"data").set(null,data);
        }
        ((Map<Short,Object>)field(data.getClass(),"itemIdToInfoMap").get(data)).put((short)123,info);
        ((Map<String,Object>)field(data.getClass(),"itemTypeToInfoMap").get(data)).put("Base.CarBattery1",info);
        return Class.forName("zombie.inventory.InventoryItemFactory").getMethod("CreateItem",String.class)
            .invoke(null,"Base.CarBattery1");
    }
    public static void main(String[] args) throws Exception {
        Object original=fixture();
        check(original!=null,"native fixture created through item factory");
        call(original,"setID",new Class<?>[]{int.class},8420611);
        call(original,"setCondition",new Class<?>[]{int.class},37);
        call(original,"setUsedDelta",new Class<?>[]{float.class},0.71345f);
        call(original,"setName",new Class<?>[]{String.class},"Unique original battery");
        Object modData=call(original,"getModData",new Class<?>[]{});
        modData.getClass().getMethod("rawset",Object.class,Object.class).invoke(modData,"portalAuditState","retained custom data");
        String encoded=PortalBatteryCodec.encode(original);
        Object restored=PortalBatteryCodec.decode(encoded);
        check(restored!=original,"reload restores persisted identity into a distinct native process object");
        check(call(restored,"getID",new Class<?>[]{}).equals(8420611),"original game item ID preserved");
        check(call(restored,"getFullType",new Class<?>[]{}).equals("Base.CarBattery1"),"original type preserved");
        check(call(restored,"getCondition",new Class<?>[]{}).equals(37),"nondefault condition preserved");
        check(Math.abs(((Number)call(restored,"getCurrentUsesFloat",new Class<?>[]{})).doubleValue()-0.71345)<0.0001,"native integer Uses charge preserved");
        check(call(restored,"getName",new Class<?>[]{}).equals("Unique original battery"),"custom name preserved");
        Object restoredData=call(restored,"getModData",new Class<?>[]{});
        check("retained custom data".equals(restoredData.getClass().getMethod("rawget",Object.class).invoke(restoredData,"portalAuditState")),"arbitrary native item ModData preserved");
        check(PortalBatteryCodec.itemId(encoded)==8420611,"envelope ID readback");
        Object twice=PortalBatteryCodec.decode(PortalBatteryCodec.encode(restored));
        check(call(twice,"getID",new Class<?>[]{}).equals(8420611)
            && call(twice,"getCondition",new Class<?>[]{}).equals(37)
            && call(twice,"getName",new Class<?>[]{}).equals("Unique original battery"),"repeated native roundtrip preserves nondefault identity/state");
        boolean corrupt=false;
        int bodyStart=encoded.lastIndexOf('|')+1;
        char changed=encoded.charAt(bodyStart)=='A'?'B':'A';
        String altered=encoded.substring(0,bodyStart)+changed+encoded.substring(bodyStart+1);
        try { PortalBatteryCodec.decode(altered); } catch(Exception expected) { corrupt=true; }
        check(corrupt,"altered native payload rejected before publishing item");
        boolean version=false;
        try { PortalBatteryCodec.decode(encoded.replace("|249|","|248|")); } catch(Exception expected) { version=true; }
        check(version,"unsupported world-format version rejected");
        Class<?> objectType=Class.forName("zombie.iso.IsoObject");
        Class<?> containerType=Class.forName("zombie.inventory.ItemContainer");
        Class<?> squareType=Class.forName("zombie.iso.IsoGridSquare");
        Class<?> itemType=Class.forName("zombie.inventory.InventoryItem");
        Object object=objectType.getConstructor().newInstance();
        Object container=containerType.getConstructor(String.class,squareType,objectType).newInstance("suqingportalbattery",null,object);
        call(object,"setContainer",new Class<?>[]{containerType},container);
        call(container,"AddItem",new Class<?>[]{itemType},original);
        check(call(original,"getContainer",new Class<?>[]{})==container,"native add owns the exact original item");
        call(container,"Remove",new Class<?>[]{itemType},original);
        check(call(original,"getContainer",new Class<?>[]{})==null,"native remove releases original item for dedicated slot");
        call(object,"removeAllContainers",new Class<?>[]{});
        check(call(object,"getContainer",new Class<?>[]{})==null && call(object,"getContainerCount",new Class<?>[]{}).equals(0),"native primary-container detach removes loot container");
        Object secondary=containerType.getConstructor(String.class,squareType,objectType).newInstance("auditSecondary",null,object);
        call(object,"addSecondaryContainer",new Class<?>[]{containerType},secondary);
        check(call(object,"getContainerCount",new Class<?>[]{}).equals(1),"native secondary container remains independently visible");
        call(object,"removeAllContainers",new Class<?>[]{});
        check(call(object,"getContainerCount",new Class<?>[]{}).equals(0),"native removeAllContainers clears confirmed-empty secondary containers");
        System.out.println("NATIVE_BATTERY_CODEC checks="+checks+" failures=0 world_initialized=false game_started=false ui_initialized=false");
    }
}
