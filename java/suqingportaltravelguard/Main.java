package suqingportaltravelguard;

import me.zed_0xff.zombie_buddy.Exposer;

public final class Main {
    private Main() {}

    public static void main(String[] args) {
        if (Compatibility.supported()) {
            Exposer.exposeClass(LuaApi.class, "SuQingPortalTravelGuard");
            System.out.println("[SuQingPortalsTravelGuard] Debug-independent guard registered for verified 42.22.2 / PZO / ZombieBuddy 2.3.4.");
        }
    }
}

