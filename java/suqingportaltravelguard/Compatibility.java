package suqingportaltravelguard;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Map;
import me.zed_0xff.zombie_buddy.Exposer;
import zombie.characters.IsoGameCharacter;
import zombie.characters.IsoPlayer;
import zombie.core.Core;
import zombie.iso.IsoMovingObject;

final class Compatibility {
    private static final Map<String, String> STOCK_CLASSES = Map.of(
        "zombie/characters/IsoPlayer.class", "643585044A88AD1B29E8D5173774F66085C685C363ED10A89C0B79018DE2874E",
        "zombie/characters/IsoGameCharacter.class", "1CCABC492BA130F51486BF38A8400334545852253BBAC9C46FFF71242AB672F6",
        "zombie/characters/PlayerCheats.class", "BAF237781B71CA57E3449AECADF316E999B7BB970C8EE43F31527F22961A7754",
        "zombie/iso/IsoMovingObject.class", "70C0249C3BDB7B4C4FC335E644C74BC98C37AA0E4BFDC0665A75521460EA0900"
    );
    private static final Map<String, String> PZO_FILES = Map.of(
        "agent/pzopt-agent.jar", "D93B34A512DEC7B16AF0C1D696BC9C905B2E06A13E3B0F5FA5E41339D7F34BB6",
        "overrides/zombie/characters/IsoPlayer.class", "C10615CD159F440B289F9A1F2B504B557F8475BCFD9D37E773A3134824DF2EB6",
        "overrides/zombie/characters/IsoGameCharacter.class", "98A03292584E24215688DFF78C7AA282042BE9660FEA68E9942C8E1F400DC114",
        "overrides/zombie/iso/IsoMovingObject.class", "16A73A1A0B54A901CD9132EA9B7AABF3C18FA805CC358CBC4CA3D36CD31B5AE2",
        "overrides/zombie/characters/IsoZombie.class", "007D52B99F0285861C68B9F33B588BAE82B9FB5EF0815B9BF5BF193771B0BE33",
        "overrides/zombie/iso/IsoChunkMap.class", "5B9A9B9EB1F66F4A71FD4AEC54DAD7B86598312A753850B162F7E5598343A86B"
    );
    private static final String ZOMBIE_BUDDY_HASH = "EB79B9876332010733A8E0D7CE4FE0377846059A9E28859029E2A0FB449F6CF2";

    private Compatibility() {}

    private static final class Status {
        private static final boolean VERIFIED = verify();
    }

    static boolean supported() {
        return Status.VERIFIED;
    }

    private static boolean verify() {
        try {
            if (!"42.22.2".equals(Core.getInstance().getGameAndBuildVersion())) {
                throw new IOException("unsupported game build");
            }
            Path gameJar = Path.of(Core.class.getProtectionDomain().getCodeSource().getLocation().toURI());
            requireHash(Path.of(Exposer.class.getProtectionDomain().getCodeSource().getLocation().toURI()), ZOMBIE_BUDDY_HASH);
            for (var entry : STOCK_CLASSES.entrySet()) {
                try (InputStream stream = Core.class.getClassLoader().getResourceAsStream(entry.getKey())) {
                    if (stream == null || !entry.getValue().equals(hash(stream))) {
                        throw new IOException("unexpected stock class " + entry.getKey());
                    }
                }
            }
            Path pzo = gameJar.toAbsolutePath().getParent().resolve("pzopt");
            for (var entry : PZO_FILES.entrySet()) {
                requireHash(pzo.resolve(entry.getKey()), entry.getValue());
            }
            // PZO's transformer replaces bytes before class definition, so system
            // resources alone show stock content even with PZO active.
            IsoPlayer.class.getDeclaredField("pzoptLos");
            IsoGameCharacter.class.getDeclaredField("pzoptShadowStamp");
            IsoMovingObject.class.getDeclaredField("pzoptSnapshotIndex");
            return true;
        } catch (Exception | LinkageError error) {
            System.err.println("[SuQingPortalsTravelGuard] Disabled: " + error);
            return false;
        }
    }

    private static void requireHash(Path file, String expected) throws Exception {
        try (InputStream stream = Files.newInputStream(file)) {
            if (!expected.equals(hash(stream))) {
                throw new IOException("unexpected hash for " + file);
            }
        }
    }

    private static String hash(InputStream stream) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[65536];
        int count;
        while ((count = stream.read(buffer)) != -1) {
            digest.update(buffer, 0, count);
        }
        return HexFormat.of().withUpperCase().formatHex(digest.digest());
    }
}

