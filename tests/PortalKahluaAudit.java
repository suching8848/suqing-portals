import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.Arrays;

/** Standalone interpreter only: no game main, world, rendering or saves. */
public final class PortalKahluaAudit {
    public static void main(String[] args) throws Exception {
        Class<?> p = Class.forName("se.krka.kahlua.j2se.J2SEPlatform");
        Object platform = p.newInstance();
        Object env = p.getMethod("newEnvironment").invoke(platform);
        Class<?> table = Class.forName("se.krka.kahlua.vm.KahluaTable");
        Class<?> fn = Class.forName("se.krka.kahlua.vm.JavaFunction");
        Object print = Proxy.newProxyInstance(fn.getClassLoader(), new Class<?>[]{fn}, (proxy, method, values) -> {
            if (method.getName().equals("call")) {
                Object frame = values[0];
                int n = ((Integer) values[1]).intValue();
                Method get = frame.getClass().getMethod("get", int.class);
                StringBuilder out = new StringBuilder();
                for (int i = 0; i < n; i++) { if (i > 0) out.append('\t'); out.append(get.invoke(frame, i)); }
                System.out.println(out);
                return Integer.valueOf(0);
            }
            return method.getName().equals("toString") ? "Portal audit print" : null;
        });
        table.getMethod("rawset", Object.class, Object.class).invoke(env, "print", print);
        Method compiler = Class.forName("se.krka.kahlua.luaj.compiler.LuaCompiler")
            .getMethod("loadstring", String.class, String.class, table);
        Class<?> threadClass = Class.forName("se.krka.kahlua.vm.KahluaThread");
        Object thread = threadClass.getConstructor(Class.forName("se.krka.kahlua.vm.Platform"), table).newInstance(platform, env);
        threadClass.getField("debugOwnerThread").set(thread, Thread.currentThread());
        Method call = threadClass.getMethod("pcall", Object.class, Object[].class);
        boolean compileOnly = args.length > 0 && args[0].equals("--compile");
        int count = 0;
        for (int i = compileOnly ? 1 : 0; i < args.length; i++) {
            String file = args[i];
            Object closure = compiler.invoke(null, new String(Files.readAllBytes(Paths.get(file)), StandardCharsets.UTF_8), file, env);
            if (!compileOnly) {
                Object[] result = (Object[]) call.invoke(thread, closure, new Object[0]);
                if (!Boolean.TRUE.equals(result[0])) throw new RuntimeException(file + ": " + Arrays.toString(result));
            }
            count++;
        }
        System.out.println((compileOnly ? "COMPILE" : "EXECUTE") + " PASS files=" + count);
    }
}
