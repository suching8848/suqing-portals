package viewpoint.addons;

import java.io.File;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;
import viewpoint.ModelPacksLua;
import viewpoint.packs.ModelPacks;
import viewpoint.packs.PackBind;
import viewpoint.packs.PackLoads;
import viewpoint.render.PackData;
import zombie.ZomboidFileSystem;
import zombie.core.Core;
import zombie.gameStates.ChooseGameInfo;

public final class VerifyResourceCompanion {
    private static final String MOD = "SuQingViewpointModelResources";
    private static final String PORTAL = "suqing-portals-models";
    private static final String FRIDGE = "suqing-freshness-fridge-models";
    private static int assertions;

    public static void main(String[] args) throws Exception {
        Path data = Path.of(args[0]).toRealPath();
        ZomboidFileSystem.instance.setCacheDir(data.toString());
        ZomboidFileSystem.instance.setModFoldersOrder("mods");
        ZomboidFileSystem.instance.init();
        Core.getInstance();
        var folders = new java.util.ArrayList<String>();
        ZomboidFileSystem.instance.getAllModFolders(folders);
        System.out.println("Native mod folders " + folders);
        System.out.println("Native direct info " + ChooseGameInfo.readModInfo(data.resolve("mods").resolve(MOD).toString()));
        var mod = ChooseGameInfo.getAvailableModDetails(MOD);
        check(mod != null, "native game discovers companion Mod ID");
        check(Path.of(mod.getDir()).toRealPath().equals(data.resolve("mods").resolve(MOD)), "private mod source path");
        check(Set.copyOf(mod.getRequire()).equals(Set.of("Viewpoint")), "only dependency is Viewpoint");
        check(Discovery.begin(List.of("ZombieBuddy", "Viewpoint", MOD)), "startup discovery begins for companion alone");
        Found found = Discovery.current().get(30, TimeUnit.SECONDS);
        check(found.mods().equals(List.of("ZombieBuddy", "Viewpoint", MOD)), "startup scans platform, Viewpoint, and companion, with gameplay mods absent");
        check(found.packages().size() == 2 && found.legacy().isEmpty(), "two declarative resource packages, no legacy packages");
        Installed portal = requirePackage(found, PORTAL, "SuQingPortals", 16, 64);
        Installed fridge = requirePackage(found, FRIDGE, "SuQingFreshnessFridge", 1, 4);
        Release release = release("42.22", "0.1.7");
        for (Installed pack : List.of(portal, fridge)) {
            check(release.misfit(pack.descriptor()) == null, "supported installed branch and version");
            check(release("42.22", "0.1.6.2").misfit(pack.descriptor()) != null, "old Viewpoint refused");
            check(release("42.22", "0.1.8").misfit(pack.descriptor()) != null, "unverified newer Viewpoint refused");
            check(release("42.21", "0.1.7").misfit(pack.descriptor()) != null, "old game branch refused");
            check(!Discovery.suspended(pack, Set.of("SuQingPortals", "SuQingFreshnessFridge")), "resource pack need not be a gameplay save mod");
        }

        ModelPacks.order(List.of());
        check(ModelPacksLua.register("SuQingPortals", "media/viewpoint/package.properties"), "actual old portal register succeeds");
        check(ModelPacksLua.register("SuQingFreshnessFridge", "media/viewpoint/package.properties"), "actual old fridge register succeeds");
        check(ModelPacks.bind("suqing_portal_01_0") == null, "old portal absent under managed startup order");
        check(ModelPacks.bind("suqing_freshness_fridge_01_1") == null, "old fridge absent under managed startup order");
        check(LegacyPacks.atRunTime(found.legacy(), Discovery.mods(), ModelPacks.legacyRegistrations()).isEmpty(), "registered late legacy packs have no startup slots");
        check(!Discovery.begin(List.of("SuQingPortals", "SuQingFreshnessFridge")), "loading the formal mods does not replace startup snapshot");

        Map<String, String> values = new HashMap<>();
        Choices.Store store = new Choices.Store() {
            public String get(String key) { return values.get(key); }
            public void put(String key, String value) {
                if (value == null) values.remove(key);
                else values.put(key, value);
            }
        };
        Choices choices = new Choices(store);
        DiskChecks disk = new DiskChecks(Discovery::mods);
        ClassLoader loader = VerifyResourceCompanion.class.getClassLoader();
        TrustGate gate = new TrustGate(ZbTrust.live(), new Consent(store), AllowListFile.enrich(AllowListFile.read(loader), loader, disk, () -> found), Discovery.worker());
        AddonManager manager = new AddonManager(choices, release, new AssetsOnly(), gate, () -> Set.of("SuQingPortals", "SuQingFreshnessFridge"));
        manager.assets(new PackContent(null, gate));
        manager.install(found);
        manager.request(PORTAL);
        manager.request(FRIDGE);
        tickUntil(manager, () -> ModelPacks.bind("suqing_portal_01_0") != null && ModelPacks.bind("suqing_freshness_fridge_01_1") != null);
        check(choices.active().containsAll(List.of(PORTAL, FRIDGE)), "activating resource cards stores both choices");
        check(choices.active().stream().noneMatch(id -> id.startsWith("legacy.")), "no legacy activation");
        check(gate.consented(portal) && gate.consented(fridge), "normal packs auto-consent via the stock resource manager");
        check(disk.check(portal).assets().problems().isEmpty() && disk.check(fridge).assets().problems().isEmpty(), "stock asset scan accepts both packs");

        verifyBindings(portal, 64);
        verifyBindings(fridge, 4);
        verifyMeshAndArt(portal, data.resolve("mods/SuQingPortals/42/media/viewpoint"), "portal_atlas.png", 16);
        verifyMeshAndArt(fridge, data.resolve("mods/SuQingFreshnessFridge/42/media/viewpoint"), "fridge_atlas.png", 1);
        manager.disable(FRIDGE);
        tickUntil(manager, () -> ModelPacks.bind("suqing_freshness_fridge_01_1") == null);
        verifyBindings(portal, 64);
        manager.request(FRIDGE);
        tickUntil(manager, () -> ModelPacks.bind("suqing_freshness_fridge_01_1") != null);
        verifyBindings(fridge, 4);
        manager.disable(PORTAL);
        tickUntil(manager, () -> ModelPacks.bind("suqing_portal_01_0") == null);
        verifyBindings(fridge, 4);
        manager.request(PORTAL);
        tickUntil(manager, () -> ModelPacks.bind("suqing_portal_01_0") != null);
        verifyBindings(portal, 64);
        System.out.println("PASS " + assertions + " assertions, both existing legacy versions excluded, 68 exact sprite lookups and 17 OBJ/material/atlas decodes, independently toggleable through native AddonManager.");
    }

    private static Release release(String game, String viewpoint) {
        return new Release(Version.parse(game), Version.parse(viewpoint), Version.parse("1.0.0"));
    }

    private static Installed requirePackage(Found found, String id, String sourceId, int models, int binds) throws Exception {
        Installed pack = found.accepted(id);
        check(pack != null && pack.kind() == Kind.RESOURCE_PACK && !pack.legacy(), "native descriptor accepts " + id);
        check(pack.modId().equals(MOD), "discovery ownership of " + id);
        Path manifest = pack.root().resolve(pack.descriptor().get("models"));
        Properties properties = read(manifest);
        check(properties.stringPropertyNames().stream().filter(key -> key.startsWith("model.")).count() == models, "model count " + sourceId);
        check(properties.stringPropertyNames().stream().filter(key -> key.startsWith("bind.")).count() == binds, "sprite count " + sourceId);
        return pack;
    }

    private static Properties read(Path manifest) throws Exception {
        Properties properties = new Properties();
        try (Reader reader = Files.newBufferedReader(manifest, StandardCharsets.UTF_8)) {
            properties.load(reader);
        }
        return properties;
    }

    private static void verifyBindings(Installed pack, int count) throws Exception {
        Properties properties = read(pack.root().resolve(pack.descriptor().get("models")));
        int checked = 0;
        for (String key : properties.stringPropertyNames()) {
            if (!key.startsWith("bind.")) continue;
            String[] expected = properties.getProperty(key).split(",");
            PackBind bind = ModelPacks.bind(key.substring(5));
            check(bind != null, "bound sprite " + key);
            Path expectedFile = pack.root().resolve(properties.getProperty("model." + expected[0]));
            check(bind.model.obj.toPath().toRealPath().equals(expectedFile.toRealPath()), "actual model owner path " + key);
            double radians = Math.toRadians(Double.parseDouble(expected[1]));
            check(near(bind.cos, Math.cos(radians)) && near(bind.sin, Math.sin(radians))
                && near(bind.x, Double.parseDouble(expected[2])) && near(bind.y, Double.parseDouble(expected[3]))
                && near(bind.z, Double.parseDouble(expected[4])) && near(bind.scale, Double.parseDouble(expected[5])), "native sprite transform " + key);
            checked++;
        }
        check(checked == count, "checked sprite count " + pack.id());
    }

    private static void verifyMeshAndArt(Installed pack, Path original, String atlas, int count) throws Exception {
        var load = PackLoads.class.getDeclaredMethod("load", File.class, Path.class);
        load.setAccessible(true);
        Properties properties = read(pack.root().resolve(pack.descriptor().get("models")));
        int checked = 0;
        for (String key : properties.stringPropertyNames()) {
            if (!key.startsWith("model.")) continue;
            String file = properties.getProperty(key);
            PackData before = (PackData) load.invoke(null, original.resolve(file).toFile(), original);
            PackData after = (PackData) load.invoke(null, pack.root().resolve(file).toFile(), pack.root());
            check(after.vertices().length > 0 && after.indices().length > 0 && after.indices().length % 3 == 0, "non-empty triangles for " + file);
            check(after.art().endsWith(atlas) && after.width() > 0 && after.height() > 0, "atlas resolved for " + file);
            check(Arrays.equals(before.vertices(), after.vertices()) && Arrays.equals(before.indices(), after.indices()), "same native geometry for " + file);
            check(Arrays.deepEquals(before.levels(), after.levels()), "same native texture levels for " + file);
            checked++;
        }
        check(checked == count, "native decoded model count " + pack.id());
    }

    private static boolean near(float actual, double expected) {
        return Math.abs(actual - expected) < 0.00001;
    }

    private static void tickUntil(AddonManager manager, BooleanSupplier condition) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(20);
        do {
            manager.frame();
            if (condition.getAsBoolean()) return;
            Thread.sleep(15);
        } while (System.nanoTime() < deadline);
        throw new AssertionError(manager.entries() + " notice=" + manager.takeNotice());
    }

    private static void check(boolean condition, String detail) {
        if (!condition) throw new AssertionError(detail);
        assertions++;
    }

    private static final class AssetsOnly implements Activator {
        public void enable(Installed installed, String jar) {
            throw new AssertionError("resource packs do not load Java: " + installed);
        }
        public void disable(Installed installed) {
            throw new AssertionError("resource packs do not unload Java: " + installed);
        }
        public boolean hooksLive(Installed installed) { return false; }
        public boolean lingering(Installed installed) { return false; }
    }
}



