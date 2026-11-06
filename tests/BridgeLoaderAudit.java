import java.lang.reflect.*;

/** Checks the installed ZombieBuddy manual-exposure ABI without agent/game boot. */
public final class BridgeLoaderAudit {
    public static void main(String[] args) throws Exception {
        ClassLoader system=ClassLoader.getSystemClassLoader();
        Class<?> main=Class.forName("suqing.portals.Main",true,system);
        Class<?> codec=Class.forName("suqing.portals.PortalBatteryCodec",true,system);
        Class<?> exposer=Class.forName("me.zed_0xff.zombie_buddy.Exposer",true,system);
        if(main.getClassLoader()!=system || codec.getClassLoader()!=system || exposer.getClassLoader()!=system)
            throw new AssertionError("bridge and installed ZombieBuddy must share system loader as Loader.loadJar specifies");
        exposer.getMethod("exposeClass",Class.class,String.class);
        main.getMethod("main",String[].class).invoke(null,(Object)new String[0]);
        if(!Boolean.TRUE.equals(exposer.getMethod("isClassExposed",Class.class).invoke(null,codec)))
            throw new AssertionError("actual installed ZombieBuddy did not register codec");
        Field map=exposer.getDeclaredField("g_exposed_classes");map.setAccessible(true);
        if(!"SuQingPortalCodec".equals(((java.util.Map<?,?>)map.get(null)).get(codec)))
            throw new AssertionError("wrong global Lua alias");
        System.out.println("BRIDGE_LOADER checks=4 failures=0 manual_exposure=true game_started=false world_initialized=false");
    }
}
