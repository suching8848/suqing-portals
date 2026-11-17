package suqingportaltravelguard;

import me.zed_0xff.zombie_buddy.Patch;
import zombie.characters.IsoGameCharacter;

@Patch(className = "zombie.characters.IsoGameCharacter", methodName = "isInvisible", strictMatch = true)
public final class PatchVisibility {
    private PatchVisibility() {}

    @Patch.OnExit
    public static void exit(@Patch.This IsoGameCharacter owner, @Patch.Return(readOnly = false) boolean result) {
        if (TravelGuard.protects(owner, TravelGuard.VISIBILITY)) {
            result = true;
        }
    }
}

