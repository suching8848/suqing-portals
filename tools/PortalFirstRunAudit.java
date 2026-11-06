import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Native config-only regression. Never starts GameWindow, a world, or UI. */
public final class PortalFirstRunAudit {
    private static final List<String> EXPECTED = Arrays.asList(
        "ZombieBuddy", "Viewpoint", "SuQingPortals", "B42ModTrans_CN", "B42Trans_CN");
    private static final String MARKER = "reset-mods-42_00.txt";
    private static int checks;
    private static Object filesystem;
    private static Class<?> fsType;
    private static Class<?> activeType;
    private static Class<?> fileType;

    private static void check(boolean condition, String message) {
        checks++;
        if (!condition) throw new AssertionError(message);
    }

    private static void cache(Path path) throws Exception {
        fsType.getMethod("setCacheDir", String.class).invoke(filesystem, path.toString());
        check(Paths.get((String) fsType.getMethod("getCacheDir").invoke(filesystem)).toAbsolutePath().normalize()
            .equals(path.toAbsolutePath().normalize()), "native cache points only at requested config directory");
    }

    private static List<String> read(Path path, String name) throws Exception {
        Object active = activeType.getMethod("getById", String.class).invoke(null, name);
        Object parser = fileType.getConstructor().newInstance();
        check(Boolean.TRUE.equals(fileType.getMethod("read", String.class, activeType)
            .invoke(parser, path.toString(), active)), "native ActiveModsFile can read " + path);
        List<?> raw = (List<?>) activeType.getMethod("getMods").invoke(active);
        List<String> result = new ArrayList<String>();
        for (Object item : raw) result.add((String) item);
        return result;
    }

    private static void reset() throws Exception {
        fsType.getMethod("resetDefaultModsForNewRelease", String.class).invoke(filesystem, "42_00");
    }

    private static String config() {
        StringBuilder result = new StringBuilder("VERSION = 1,\n\nmods\n{\n");
        for (String id : EXPECTED) result.append("    mod = ").append(id).append(",\n");
        return result.append("}\n\nmaps\n{\n}\n").toString();
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Usage: PortalFirstRunAudit <isolatedCache>");
        Path isolated = Paths.get(args[0]).toAbsolutePath().normalize();
        Path originalDefault = isolated.resolve("mods/default.txt");
        Path originalMarker = isolated.resolve("mods").resolve(MARKER);
        // Fail before invoking a native writer if the supplied profile is not
        // already protected by its current-release marker.
        check(Files.isRegularFile(originalMarker), "isolated profile has current-release marker");
        check(Files.isRegularFile(originalDefault), "isolated profile has default.txt");
        byte[] original = Files.readAllBytes(originalDefault);
        byte[] markerBefore = Files.readAllBytes(originalMarker);

        fsType = Class.forName("zombie.ZomboidFileSystem");
        filesystem = fsType.getField("instance").get(null);
        activeType = Class.forName("zombie.modding.ActiveMods");
        fileType = Class.forName("zombie.modding.ActiveModsFile");
        cache(isolated);
        check(EXPECTED.equals(read(originalDefault, "portal-first-run-profile")),
            "isolated profile has exactly five expected IDs in original order");
        reset();
        check(Arrays.equals(original, Files.readAllBytes(originalDefault)),
            "existing marker prevents native first-run reset from changing isolated default.txt");
        check(Arrays.equals(markerBefore, Files.readAllBytes(originalMarker)),
            "native existing-marker branch does not rewrite marker contents");
        check(EXPECTED.equals(read(originalDefault, "portal-first-run-profile-after")),
            "native readback after reset retains five expected ordered IDs");

        Path results = Paths.get(System.getProperty("portal.audit.results",
            "E:\\code\\suqing-portals\\tests\\results")).toAbsolutePath().normalize();
        Path probes = results.resolve("first-run-probe");
        Files.createDirectories(probes);
        Path run = Files.createTempDirectory(probes, "run-");
        Path absent = run.resolve("absent-marker");
        Path present = run.resolve("present-marker");
        Files.createDirectories(absent.resolve("mods"));
        Files.createDirectories(present.resolve("mods"));
        byte[] initial = config().getBytes(StandardCharsets.UTF_8);
        Files.write(absent.resolve("mods/default.txt"), initial);
        Files.write(present.resolve("mods/default.txt"), initial);

        cache(absent);
        check(!Files.exists(absent.resolve("mods").resolve(MARKER)), "negative control starts without marker");
        reset();
        check(Files.isRegularFile(absent.resolve("mods").resolve(MARKER)),
            "native first-run reset creates release marker in negative-control config only");
        check(read(absent.resolve("mods/default.txt"), "portal-first-run-negative").isEmpty(),
            "negative control confirms absent marker clears enabled mods");

        byte[] arbitrary = "Only marker existence matters; contents are not parsed.\n".getBytes(StandardCharsets.UTF_8);
        Files.write(present.resolve("mods").resolve(MARKER), arbitrary);
        cache(present);
        reset();
        check(Arrays.equals(initial, Files.readAllBytes(present.resolve("mods/default.txt"))),
            "arbitrary existing marker preserves positive-control default.txt bytes");
        check(Arrays.equals(arbitrary, Files.readAllBytes(present.resolve("mods").resolve(MARKER))),
            "positive control proves marker contents are neither parsed nor rewritten");
        check(EXPECTED.equals(read(present.resolve("mods/default.txt"), "portal-first-run-positive")),
            "positive control native reader retains all five IDs in order");

        check(Arrays.equals(original, Files.readAllBytes(originalDefault)),
            "requested isolated profile unchanged after both temporary controls");
        check(Arrays.equals(markerBefore, Files.readAllBytes(originalMarker)),
            "requested isolated marker unchanged after both temporary controls");
        System.out.println("PORTAL_FIRST_RUN_NATIVE checks=" + checks
            + " failures=0 expected_mods=" + EXPECTED + " probe=" + run
            + " game_started=false world_initialized=false ui_initialized=false");
    }
}
