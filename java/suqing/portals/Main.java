package suqing.portals;

/** ZombieBuddy's documented regular-load Main hook; no bytecode patches. */
public final class Main {
    public static void main(String[] args) throws Exception {
        Class<?> exposer = Class.forName("me.zed_0xff.zombie_buddy.Exposer", true, ClassLoader.getSystemClassLoader());
        exposer.getMethod("exposeClass", Class.class, String.class)
            .invoke(null, PortalBatteryCodec.class, "SuQingPortalCodec");
        System.out.println("[SuQingPortals] native battery codec registered; format=2 worldVersion=249");
    }
}
