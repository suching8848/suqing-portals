import java.lang.reflect.Field;
import me.zed_0xff.zombie_buddy.Exposer;
import me.zed_0xff.zombie_buddy.PatchEngine;
import sun.misc.Unsafe;
import suqingportaltravelguard.LuaApi;
import zombie.characters.IsoGameCharacter;
import zombie.characters.IsoPlayer;
import zombie.characters.PlayerCheats;
import zombie.core.Core;
import zombie.network.GameClient;
import zombie.network.GameServer;

public final class NativeTravelGuardAudit {
    private static int checks;

    public static void main(String[] args) throws Exception {
        Core.debug = false;
        zombie.core.random.RandStandard.INSTANCE.init();
        suqingportaltravelguard.Main.main(new String[0]);
        boolean expectProfile = !args[0].equals("no-pzo");
        verify(Exposer.isClassExposed(LuaApi.class) == expectProfile, "supported profile gate");
        IsoPlayer.numPlayers = 2;
        IsoPlayer alice = player(0);
        IsoPlayer bob = player(1);
        IsoPlayer nonLocal = player(0);
        IsoPlayer.players[0] = alice;
        IsoPlayer.players[1] = bob;
        verify(LuaApi.begin(alice) == 0, "before runtime weaving, the API refuses the actual player");
        if (!expectProfile) {
            System.out.println("PASS without PZ Optimization: API not exposed, no lease; " + checks + " assertions");
            return;
        }

        PatchEngine.applyPatches("suqingportaltravelguard", ClassLoader.getSystemClassLoader());
        verify(!Core.debug && !alice.isNoClip() && !alice.isGhostMode() && !alice.isGodMod(), "native responses before transit");
        boolean baselineFall = alice.shouldBeFalling();
        verify(LuaApi.begin(nonLocal) == 0, "unassociated player");
        GameClient.client = true;
        verify(LuaApi.begin(alice) == 0, "client denied");
        GameClient.client = false;
        GameServer.server = true;
        verify(LuaApi.begin(alice) == 0, "server denied");
        GameServer.server = false;

        double token = LuaApi.begin(alice);
        verify(token > 0 && LuaApi.active(alice, token), "debug-off native guard and runtime probe");
        verify(LuaApi.begin(alice) == token, "same player reacquires the same transfer handle");
        verify(alice.isNoClip() && alice.isGhostMode() && alice.isInvisible() && alice.isInvulnerable(),
            "woven PZO collision, visibility and incoming-attack responses");
        verify(!alice.shouldBeFalling(), "woven gravity response");
        zombie.iso.IsoGridSquare burning = new zombie.iso.IsoGridSquare(null, null, 100, 100, 0);
        burning.getProperties().set(zombie.iso.SpriteDetails.IsoFlagType.burning);
        Field actorSquare = zombie.iso.IsoObject.class.getDeclaredField("square");
        actorSquare.setAccessible(true);
        actorSquare.set(alice, burning);
        alice.FireCheck();
        alice.SetOnFire();
        verify(!alice.isOnFire(), "live burning-tile damage and explicit ignition are both suppressed during transit");
        alice.setOnFire(true);
        verify(alice.isOnFire(), "companion did not clear the actual existing on-fire flag");
        alice.setOnFire(false);
        actorSquare.set(alice, null);
        verify(!alice.isGodMod() && !Core.debug && !alice.isBlockMovement(), "God mode, debug and external movement remain untouched");
        verify(!bob.isNoClip() && !bob.isGhostMode() && bob.shouldBeFalling() == baselineFall && !bob.isInvulnerable(), "other local player unaffected");
        verify(!LuaApi.active(bob, token) && !LuaApi.finish(bob, token) && !LuaApi.finish(alice, token + 1), "owner and token enforced");
        verify(LuaApi.finish(alice, token) && !LuaApi.finish(alice, token), "idempotent protected-state removal");
        verify(!alice.isNoClip() && !alice.isGhostMode() && !alice.isInvulnerable() && alice.shouldBeFalling() == baselineFall,
            "engine responses restored");
        double next = LuaApi.begin(alice);
        verify(next > token && !LuaApi.finish(alice, token), "new session distinct from stale handle");
        IsoPlayer.players[0] = nonLocal;
        verify(!LuaApi.active(alice, next) && !nonLocal.isNoClip() && !alice.isNoClip(), "player replacement does not inherit lease");
        verify(LuaApi.finish(alice, next), "removed player can release outstanding handle");

        Core.debug = true;
        bob.setNoClip(true, true);
        bob.setGhostMode(true, true);
        bob.setGodMod(true);
        double existing = LuaApi.begin(bob);
        verify(existing > 0 && LuaApi.finish(bob, existing), "existing native flags coexist");
        verify(bob.isNoClip() && bob.isGhostMode() && bob.isGodMod(), "pre-existing flags preserved");
        Core.debug = false;
        verify(!bob.isNoClip() && !bob.isGhostMode() && !bob.isGodMod(), "global cheat gating still applies after travel");

        setupLua();
        Exposer.afterExposeAll();
        verifyLuaAlias(nonLocal, "early registration");
        Field registered = Exposer.class.getDeclaredField("g_exposed_classes");
        registered.setAccessible(true);
        ((java.util.Map<?, ?>) registered.get(null)).remove(LuaApi.class);
        setupLua();
        verify(zombie.Lua.LuaManager.env.rawget("SuQingPortalTravelGuard") == null, "before save-only registration");
        suqingportaltravelguard.Main.main(new String[0]);
        verifyLuaAlias(nonLocal, "save-only late registration");

        System.out.println("PASS actual B42.22.2 PZO classes, ZombieBuddy PatchEngine, and JVM; " + checks
            + " assertions; game UI, saves and worlds were not initialized");
    }

    private static void setupLua() {
        var platform = new se.krka.kahlua.j2se.J2SEPlatform();
        var env = platform.newEnvironment();
        var conversions = new se.krka.kahlua.converter.KahluaConverterManager();
        zombie.Lua.KahluaNumberConverter.install(conversions);
        zombie.Lua.LuaManager.env = env;
        zombie.Lua.LuaManager.exposer = new zombie.Lua.LuaManager.Exposer(conversions, platform, env);
        var thread = new se.krka.kahlua.vm.KahluaThread(platform, env);
        thread.debugOwnerThread = Thread.currentThread();
        zombie.Lua.LuaManager.thread = thread;
    }

    private static void verifyLuaAlias(IsoPlayer player, String stage) throws Exception {
        var lua = zombie.Lua.LuaManager.env;
        lua.rawset("TravelTestPlayer", player);
        var code = """
            local api = SuQingPortalTravelGuard
            assert(type(api) == "table")
            local token = api.begin(TravelTestPlayer)
            assert(type(token) == "number" and token > 0)
            assert(api.active(TravelTestPlayer, token) == true)
            assert(api.finish(TravelTestPlayer, token) == true)
            assert(api.active(TravelTestPlayer, token) == false)
            return true
            """;
        var closure = se.krka.kahlua.luaj.compiler.LuaCompiler.loadstring(code, "Portal API interop", lua);
        Object[] response = zombie.Lua.LuaManager.thread.pcall(closure, new Object[0]);
        verify(Boolean.TRUE.equals(response[0]) && Boolean.TRUE.equals(response[1]),
            "actual Kahlua alias and dot-call ABI (" + stage + "): " + java.util.Arrays.toString(response));
    }

    private static IsoPlayer player(int index) throws Exception {
        Field unsafeField = Unsafe.class.getDeclaredField("theUnsafe");
        unsafeField.setAccessible(true);
        IsoPlayer result = (IsoPlayer) ((Unsafe) unsafeField.get(null)).allocateInstance(IsoPlayer.class);
        result.playerIndex = index;
        result.cheats = new PlayerCheats();
        Field health = IsoGameCharacter.class.getDeclaredField("health");
        health.setAccessible(true);
        health.setFloat(result, 100f);
        Field components = zombie.iso.IsoObject.class.getDeclaredField("ecsComponentMap");
        components.setAccessible(true);
        components.set(result, new java.util.HashMap<>());
        result.setECSComponent(new zombie.characters.component.StateMachineComponent(result));
        Field grappleable = IsoGameCharacter.class.getDeclaredField("grappleable");
        grappleable.setAccessible(true);
        grappleable.set(result, new zombie.core.skinnedmodel.BaseGrappleable(result));
        return result;
    }

    private static void verify(boolean value, String label) {
        ++checks;
        if (!value) throw new AssertionError(label);
    }
}

