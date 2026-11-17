package suqingportaltravelguard;

import java.lang.ref.WeakReference;
import java.util.concurrent.atomic.AtomicReferenceArray;
import zombie.characters.IsoGameCharacter;
import zombie.characters.IsoPlayer;
import zombie.network.GameClient;
import zombie.network.GameServer;

/** Temporary engine responses, scoped to the player object and one transfer handle. */
public final class TravelGuard {
    static final int COLLISION = 1;
    static final int VISIBILITY = 2;
    static final int GRAVITY = 4;
    static final int ATTACK_DAMAGE = 8;
    private static final int COMPLETE = COLLISION | VISIBILITY | GRAVITY | ATTACK_DAMAGE;
    private static final double LAST_EXACT_INTEGER = 9_007_199_254_740_991d;
    private static final AtomicReferenceArray<Lease> LEASES = new AtomicReferenceArray<>(4);
    private static final ThreadLocal<Lease> PROBE = new ThreadLocal<>();
    private static double sequence;
    private static boolean reported;

    private TravelGuard() {}

    private static final class Lease {
        final WeakReference<IsoPlayer> owner;
        final double token;
        int checked;
        volatile boolean enabled;

        Lease(IsoPlayer owner, double token) {
            this.owner = new WeakReference<>(owner);
            this.token = token;
        }
    }

    /**
     * Returns a positive transient handle or zero. Probe all four live advice
     * sites before authorizing a move or a debit, including late-loaded patches.
     */
    public static synchronized double begin(IsoPlayer player) {
        if (!singlePlayer() || player == null || player.isDead() || !Compatibility.supported()) {
            return 0;
        }
        int index = slot(player);
        if (index < 0 || sequence == LAST_EXACT_INTEGER) {
            return 0;
        }
        Lease old = LEASES.get(index);
        if (old != null && old.enabled && old.owner.get() == player) {
            return old.token;
        }

        Lease next = new Lease(player, ++sequence);
        PROBE.set(next);
        try {
            boolean noClip = player.isNoClip();
            boolean invisible = player.isInvisible();
            boolean falling = player.shouldBeFalling();
            boolean invulnerable = player.isInvulnerable();
            if (next.checked == COMPLETE && noClip && invisible && !falling && invulnerable) {
                next.enabled = true;
                LEASES.set(index, next);
                return next.token;
            }
        } catch (RuntimeException | LinkageError error) {
            if (!reported) {
                System.err.println("[SuQingPortalsTravelGuard] Live protection probe failed: " + error);
                reported = true;
            }
        } finally {
            PROBE.remove();
        }
        if (!reported) {
            System.err.println("[SuQingPortalsTravelGuard] One or more runtime patch sites unavailable. Mask=" + next.checked);
            reported = true;
        }
        return 0;
    }

    public static boolean active(IsoPlayer player, double token) {
        if (player == null || player.isDead() || !singlePlayer()) {
            return false;
        }
        int index = slot(player);
        return index >= 0 && matches(LEASES.get(index), player, token);
    }

    public static synchronized boolean finish(IsoPlayer player, double token) {
        if (player == null) {
            return false;
        }
        // Release also works after death or removal from the engine player slot.
        for (int index = 0; index < LEASES.length(); ++index) {
            Lease lease = LEASES.get(index);
            if (matches(lease, player, token)) {
                lease.enabled = false;
                LEASES.set(index, null);
                return true;
            }
        }
        return false;
    }

    /** Inlined ZombieBuddy advice calls this method from the engine's classes. */
    public static boolean protects(IsoGameCharacter character, int hook) {
        if (!(character instanceof IsoPlayer player) || !singlePlayer()) {
            return false;
        }
        Lease probe = PROBE.get();
        if (probe != null && probe.owner.get() == player) {
            probe.checked |= hook;
            return true;
        }
        int index = slot(player);
        if (index < 0) {
            return false;
        }
        Lease lease = LEASES.get(index);
        return lease != null && lease.enabled && lease.owner.get() == player;
    }

    private static boolean matches(Lease lease, IsoPlayer player, double token) {
        return token > 0 && lease != null && lease.enabled && lease.token == token && lease.owner.get() == player;
    }

    private static int slot(IsoPlayer player) {
        int index = player.getPlayerNum();
        return index >= 0 && index < LEASES.length() && index < IsoPlayer.numPlayers
            && IsoPlayer.players[index] == player ? index : -1;
    }

    private static boolean singlePlayer() {
        return !GameClient.client && !GameServer.server;
    }
}

