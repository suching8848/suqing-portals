package suqingportaltravelguard;

import me.zed_0xff.zombie_buddy.Patch;
import zombie.characters.IsoGameCharacter;

@Patch(className = "zombie.characters.IsoGameCharacter", methodName = "FireCheck", strictMatch = true)
public final class PatchContactFire {
    private PatchContactFire() {}

    @Patch.OnEnter(skipOn = true)
    public static boolean enter(@Patch.This IsoGameCharacter owner) {
        return TravelGuard.protects(owner, 0);
    }
}

