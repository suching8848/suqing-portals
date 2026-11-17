package suqingportaltravelguard;

import me.zed_0xff.zombie_buddy.Patch;
import zombie.characters.IsoGameCharacter;

@Patch(className = "zombie.characters.IsoGameCharacter", methodName = "isInvulnerable", strictMatch = true)
public final class PatchAttackDamage {
    private PatchAttackDamage() {}

    @Patch.OnExit
    public static void exit(@Patch.This IsoGameCharacter owner, @Patch.Return(readOnly = false) boolean result) {
        if (TravelGuard.protects(owner, TravelGuard.ATTACK_DAMAGE)) {
            result = true;
        }
    }
}

