package suqingportaltravelguard;

import zombie.characters.IsoPlayer;

public final class LuaApi {
    private LuaApi() {}

    public static double begin(IsoPlayer player) {
        return TravelGuard.begin(player);
    }

    public static boolean active(IsoPlayer player, double token) {
        return TravelGuard.active(player, token);
    }

    public static boolean finish(IsoPlayer player, double token) {
        return TravelGuard.finish(player, token);
    }
}

