import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Standalone ConfigFile reader. Does not load a game or a world. */
public final class PortalIsolationAudit {
    public static void main(String[] args) throws Exception {
        Class<?> c = Class.forName("zombie.config.ConfigFile");
        Object file = c.newInstance();
        if (!Boolean.TRUE.equals(c.getMethod("read", String.class).invoke(file, args[0])))
            throw new RuntimeException("Preset unreadable");
        int version = ((Number)c.getMethod("getVersion").invoke(file)).intValue();
        if (version != 6) throw new RuntimeException("Wrong preset version: " + version);
        Object options = c.getMethod("getOptions").invoke(file);
        Map<String,String> entries = new HashMap<String,String>();
        for (Object o : (Iterable<?>)options) {
            String name = (String)o.getClass().getMethod("getName").invoke(o);
            String value = (String)o.getClass().getMethod("getValueAsString").invoke(o);
            entries.put(name, value);
        }
        if (entries.containsKey("SuQingPortals.DebugTools")) throw new RuntimeException("Retired test-tools key remains");
        if (!"0.5".equals(entries.get("SuQingPortals.ChargePerHour"))) throw new RuntimeException("Charge rate differs");
        double transferCost = entries.containsKey("SuQingPortals.TransferCost")
            ? Double.parseDouble(entries.get("SuQingPortals.TransferCost")) : 2.0;
        if (transferCost != 2.0) throw new RuntimeException("Default transfer cost differs");
        if (!"6".equals(entries.get("Zombies"))) throw new RuntimeException("Wrong zombie preset");
        System.out.println("NATIVE PRESET PASS version=" + version + " entries=" + entries.size());
    }
}
