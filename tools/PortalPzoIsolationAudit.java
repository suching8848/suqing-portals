import java.lang.reflect.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.*;

/** Class/interface/config-path checks only, never game main/world/UI. */
public final class PortalPzoIsolationAudit {
    static int checks;
    static void check(boolean ok, String why) { checks++; if (!ok) throw new AssertionError(why); }
    public static void main(String[] args) throws Exception {
        Path game = Paths.get(args[0]).toRealPath();
        Path cache = Paths.get(args[1]).toRealPath();
        Class<?> fs = Class.forName("zombie.ZomboidFileSystem");
        fs.getMethod("setCacheDir", String.class).invoke(fs.getField("instance").get(null), cache.toString());
        Class<?> perf = Class.forName("zombie.core.PerformanceSettings", false, PortalPzoIsolationAudit.class.getClassLoader());
        Path owner = Paths.get(perf.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
        check(owner.equals(game.resolve("pzopt/aot/pzopt.jar").toRealPath()), "PerformanceSettings must come from the matching PZO jar");
        perf.getMethod("pzoptBenchmark", String.class, String.class);
        check(true, "Screenshot's missing benchmark API exists");
        Set<String> exposed = new HashSet<String>();
        for (Method method : perf.getMethods()) exposed.add(method.getName());
        Pattern call = Pattern.compile(":((?:pzopt|getPzopt|setPzopt|hasPzopt|isPzopt|canPzopt|releasePzopt)[A-Za-z0-9_]*)\\(");
        Set<String> requested = new TreeSet<String>();
        Path root = game.resolve("media/lua");
        List<Path> files = new ArrayList<Path>();
        try (java.util.stream.Stream<Path> stream = Files.walk(root)) {
            stream.filter(p -> Files.isRegularFile(p) && p.getFileName().toString().startsWith("pzopt_") && p.toString().endsWith(".lua")).forEach(files::add);
        }
        for (Path p : files) {
            Matcher matcher = call.matcher(new String(Files.readAllBytes(p), StandardCharsets.UTF_8));
            while (matcher.find()) requested.add(matcher.group(1));
        }
        check(files.size() >= 19, "Installed PZO Lua retained");
        for (String name : requested) check(exposed.contains(name), "Missing Lua-facing PZO method: " + name);
        Class<?> options = Class.forName("pzopt.UserOptions");
        Method path = options.getDeclaredMethod("file");
        path.setAccessible(true);
        Path userOptions = ((java.io.File)path.invoke(null)).getCanonicalFile().toPath();
        check(userOptions.equals(cache.resolve("pzopt/options.ini")), "PZO user options must stay inside the isolated cache: " + userOptions);
        System.out.println("PZO_ISOLATION_INTERFACES checks=" + checks + " failures=0 lua_files=" + files.size()
            + " lua_methods=" + requested.size() + " owner=" + owner + " user_options=" + userOptions
            + " game_started=false world_initialized=false ui_initialized=false");
    }
}
