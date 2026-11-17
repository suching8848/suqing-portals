package suqingportaltravelguard;

import me.zed_0xff.zombie_buddy.Patch;
import zombie.characters.IsoGameCharacter;

@Patch(className = "zombie.characters.IsoGameCharacter", methodName = "SetOnFire", strictMatch = true)
public final class PatchIgnition {
    private PatchIgnition() {}

    @Patch.OnEnter(skipOn = true)
    public static boolean enter(@Patch.This IsoGameCharacter owner) {
        return TravelGuard.protects(owner, 0);
    }
}

