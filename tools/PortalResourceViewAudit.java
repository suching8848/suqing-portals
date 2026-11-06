import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Offline file-index inspection only. No MainScreenState, world, UI, renderer,
 * game loop, Lua execution, or connection to a running game is invoked.
 * Compile with Java 8; execute with installed Java 25 from engineRoot as cwd.
 * Arguments: engineRoot cacheRoot.
 */
public final class PortalResourceViewAudit {
    private static int checks;

    private static void check(boolean value, String label) {
        if (!value) throw new AssertionError(label);
        ++checks;
    }

    private static Path normalized(Path path) {
        return path.toAbsolutePath().normalize();
    }

    private static Path assertMapped(Class<?> type, Object fs, Path engine,
                                     String key, boolean privateCopy) throws Exception {
        String resolved = (String)type.getMethod("getString", String.class).invoke(fs, key);
        Path wanted = normalized(engine.resolve(key));
        Path actual = normalized(Paths.get(resolved));
        check(actual.equals(wanted), "getString preserves engine lexical path: " + key
                + " -> " + resolved);
        check(Files.isRegularFile(actual) && Files.isReadable(actual), "mapped file readable: " + key);
        if (privateCopy) {
            check(actual.toRealPath().equals(wanted), "private script does not canonicalize to original root: " + key);
        }
        String relative = (String)type.getMethod("getRelativeFile", String.class).invoke(fs, actual.toString());
        check(relative.replace('\\', '/').equalsIgnoreCase(key), "relative key remains intact: " + key);
        System.out.println("PASS resource mapping " + key + " -> " + actual);
        return actual;
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Usage: PortalResourceViewAudit engineRoot cacheRoot");
        Path engine = normalized(Paths.get(args[0]));
        Path cache = normalized(Paths.get(args[1]));
        Path cwd = normalized(Paths.get("."));
        check(cwd.equals(engine), "process cwd must be the independent engine root");
        check(Files.isDirectory(engine.resolve("media/lua")), "independent media/lua directory exists");
        check(Files.isDirectory(cache), "isolated cache directory already exists");
        check(engine.resolve("media").toRealPath().equals(engine.resolve("media")), "media root itself is a real independent directory");

        Class<?> type = Class.forName("zombie.ZomboidFileSystem");
        URI jarUri = type.getProtectionDomain().getCodeSource().getLocation().toURI();
        Path jar = normalized(Paths.get(jarUri));
        check(Files.isRegularFile(jar) && jar.getFileName().toString().equals("projectzomboid.jar"),
                "file-index implementation comes from the original vanilla jar");
        Path original = jar.getParent();
        check(!original.equals(engine), "independent engine cwd differs from original game root");

        Object fs = type.getField("instance").get(null);
        type.getMethod("setCacheDir", String.class).invoke(fs, cache.toString());
        // Only file-index initialization. Its current DoFrameReady callback
        // returns without keyboard work while no text-entry UI is active.
        type.getMethod("init").invoke(fs);
        File mediaFile = (File)type.getMethod("getMediaRootFile").invoke(fs);
        check(normalized(mediaFile.toPath()).equals(engine.resolve("media")),
                "native mediaRoot resolves to independent engine/media");
        check(normalized(Paths.get((String)type.getMethod("getCacheDir").invoke(fs))).equals(cache),
                "native cache root remains isolated");

        assertMapped(type, fs, engine, "media/lua/shared/defines.lua", true);
        assertMapped(type, fs, engine, "media/lua/client/ISUI/ISInventoryPane.lua", true);

        Field mapField = type.getField("activeFileMap");
        Map<?, ?> map = (Map<?, ?>)mapField.get(fs);
        check(!map.isEmpty(), "native resource index contains entries");
        List<String> excluded = new ArrayList<String>();
        for (String row : Files.readAllLines(original.resolve("pzopt-files.txt"), StandardCharsets.UTF_8)) {
            String entry = row.trim().replace('\\', '/');
            if (entry.startsWith("media/lua/") || entry.startsWith("media/shaders/")) {
                excluded.add(entry);
                check(!Files.exists(engine.resolve(entry)), "PZO addition physically absent: " + entry);
                check(!map.containsKey(entry.toLowerCase(Locale.ENGLISH)), "PZO addition absent from native index: " + entry);
                String resolved = (String)type.getMethod("getString", String.class).invoke(fs, entry);
                check(resolved.equals(entry), "missing PZO resource remains unresolved: " + entry);
            }
        }
        check(!excluded.isEmpty(), "PZO manifest supplied explicit exclusion entries");
        for (Object key : map.keySet()) {
            String name = key.toString().replace('\\', '/').toLowerCase(Locale.ENGLISH);
            check(!(name.startsWith("media/lua/") && name.contains("/pzopt/")), "no PZO Lua directory entry in resource index");
        }

        Path stdlib = engine.resolve("stdlib.lua");
        check(Files.isRegularFile(stdlib) && Files.isReadable(stdlib), "cwd stdlib.lua exists and is readable");
        check(stdlib.toRealPath().equals(stdlib), "stdlib.lua is a private file at independent cwd");
        check(Arrays.equals(Files.readAllBytes(stdlib), Files.readAllBytes(original.resolve("stdlib.lua"))),
                "private stdlib.lua matches original bytes");
        System.out.println("PASS native mediaRoot " + mediaFile);
        System.out.println("PASS explicit PZO Lua/shader exclusions: " + excluded.size());
        System.out.println("PASS cwd stdlib.lua; native resource index entries=" + map.size());
        System.out.println("PASS total file-index assertions=" + checks);
        System.out.println("Scope: standalone filesystem-index initialization and readback only; no game, world, UI, renderer, Lua execution, or gameplay acceptance.");
    }
}
