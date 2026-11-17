package suqingportaltravelguard;

import me.zed_0xff.zombie_buddy.Patch;
import zombie.characters.IsoPlayer;

@Patch(className = "zombie.characters.IsoPlayer", methodName = "isNoClip", strictMatch = true)
public final class PatchCollision {
    private PatchCollision() {}

    @Patch.OnExit
    public static void exit(@Patch.This IsoPlayer owner, @Patch.Return(readOnly = false) boolean result) {
        if (TravelGuard.protects(owner, TravelGuard.COLLISION)) {
            result = true;
        }
    }
}

