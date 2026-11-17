package suqingportaltravelguard;

import me.zed_0xff.zombie_buddy.Patch;
import zombie.characters.IsoGameCharacter;

@Patch(className = "zombie.characters.IsoGameCharacter", methodName = "shouldBeFalling", strictMatch = true)
public final class PatchGravity {
    private PatchGravity() {}

    @Patch.OnExit
    public static void exit(@Patch.This IsoGameCharacter owner, @Patch.Return(readOnly = false) boolean result) {
        if (TravelGuard.protects(owner, TravelGuard.GRAVITY)) {
            result = false;
        }
    }
}

