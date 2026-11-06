package suqing.portals;

import java.io.IOException;
import java.io.DataInputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.BufferOverflowException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Base64;

/** Complete native InventoryItem codec only: no item factory, world or UI boot. */
public final class PortalBatteryCodec {
    private static final int WORLD_VERSION = 249; // Verified B42.21 native class constant.
    private static final int MAX_BYTES = 1024 * 1024;
    private static final String PREFIX = "SQPB2";
    private static boolean nativeVersionVerified;

    private PortalBatteryCodec() { }
    public static int formatVersion() { return 2; }
    public static int worldVersion() { return WORLD_VERSION; }

    private static Class<?> itemType() throws ClassNotFoundException {
        return Class.forName("zombie.inventory.InventoryItem", true, ClassLoader.getSystemClassLoader());
    }

    private static synchronized void verifyNativeVersion() throws Exception {
        if (nativeVersionVerified) return;
        // Read the compile-time constant from the class resource. Reflection
        // Field.get would initialize IsoWorld; this check deliberately does not.
        try (DataInputStream in = new DataInputStream(ClassLoader.getSystemResourceAsStream("zombie/iso/IsoWorld.class"))) {
            if (in.readInt() != 0xCAFEBABE) throw new IOException("storage_version");
            in.readInt();
            Object[] pool = new Object[in.readUnsignedShort()];
            for (int index=1; index<pool.length; index++) {
                int tag=in.readUnsignedByte();
                if (tag==1) pool[index]=in.readUTF();
                else if(tag==3) pool[index]=in.readInt();
                else if(tag==4) in.readInt();
                else if(tag==5 || tag==6) { in.readLong(); index++; }
                else if(tag==7 || tag==8 || tag==16 || tag==19 || tag==20) in.readUnsignedShort();
                else if(tag==9 || tag==10 || tag==11 || tag==12 || tag==17 || tag==18) in.readInt();
                else if(tag==15) { in.readUnsignedByte(); in.readUnsignedShort(); }
                else throw new IOException("storage_version");
            }
            in.readUnsignedShort(); in.readUnsignedShort(); in.readUnsignedShort();
            int interfaces=in.readUnsignedShort(); for(int i=0;i<interfaces;i++) in.readUnsignedShort();
            int fields=in.readUnsignedShort();
            for(int i=0;i<fields;i++) {
                in.readUnsignedShort(); String name=(String)pool[in.readUnsignedShort()]; in.readUnsignedShort();
                int attributes=in.readUnsignedShort();
                for(int a=0;a<attributes;a++) {
                    String attribute=(String)pool[in.readUnsignedShort()]; int length=in.readInt();
                    if("WorldVersion".equals(name) && "ConstantValue".equals(attribute) && length==2) {
                        if(!Integer.valueOf(WORLD_VERSION).equals(pool[in.readUnsignedShort()])) throw new IOException("storage_version");
                        nativeVersionVerified=true; return;
                    }
                    for(int remaining=length;remaining>0;) { int skipped=in.skipBytes(remaining); if(skipped<=0) throw new IOException("storage_version"); remaining-=skipped; }
                }
            }
        }
        throw new IOException("storage_version");
    }

    private static Object invoke(Method method, Object receiver, Object... arguments) throws Exception {
        try { return method.invoke(receiver, arguments); }
        catch (InvocationTargetException error) {
            Throwable cause = error.getCause();
            if (cause instanceof Exception) throw (Exception) cause;
            throw error;
        }
    }

    private static String hash(byte[] bytes) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder result = new StringBuilder(64);
        for (byte value : digest) result.append(String.format("%02x", value & 255));
        return result.toString();
    }

    public static String encode(Object item) throws Exception {
        verifyNativeVersion();
        Class<?> type = itemType();
        if (!type.isInstance(item)) throw new IOException("codec_invalid_item");
        int id = ((Number) invoke(type.getMethod("getID"), item)).intValue();
        String fullType = (String) invoke(type.getMethod("getFullType"), item);
        if (id <= 0 || fullType == null || fullType.length() > 256) throw new IOException("codec_invalid_identity");
        Method save = type.getMethod("saveWithSize", ByteBuffer.class, boolean.class);
        byte[] bytes = null;
        for (int size = 4096; size <= MAX_BYTES; size *= 2) {
            ByteBuffer buffer = ByteBuffer.allocate(size);
            try {
                invoke(save, item, buffer, Boolean.FALSE);
                bytes = Arrays.copyOf(buffer.array(), buffer.position());
                break;
            } catch (BufferOverflowException larger) {
                if (size == MAX_BYTES) throw new IOException("codec_item_too_large", larger);
            }
        }
        if (bytes == null || bytes.length < 4) throw new IOException("codec_empty_payload");
        String metadata = WORLD_VERSION + "|" + id + "|"
            + Base64.getEncoder().encodeToString(fullType.getBytes(StandardCharsets.UTF_8));
        byte[] authenticated = join(metadata, bytes);
        return PREFIX + "|" + metadata + "|" + hash(authenticated) + "|" + Base64.getEncoder().encodeToString(bytes);
    }

    private static byte[] join(String metadata, byte[] body) {
        byte[] prefix = (metadata + "|").getBytes(StandardCharsets.US_ASCII);
        byte[] result = Arrays.copyOf(prefix, prefix.length + body.length);
        System.arraycopy(body, 0, result, prefix.length, body.length);
        return result;
    }

    private static String[] fields(String encoded) throws IOException {
        if (encoded == null || encoded.length() > MAX_BYTES * 2) throw new IOException("storage_corrupt");
        String[] fields = encoded.split("\\|", -1);
        if (fields.length != 6 || !PREFIX.equals(fields[0])) throw new IOException("storage_version");
        if (!Integer.toString(WORLD_VERSION).equals(fields[1])) throw new IOException("storage_version");
        return fields;
    }

    public static int itemId(String encoded) throws Exception {
        String[] fields = fields(encoded);
        int id;
        try { id = Integer.parseInt(fields[2]); }
        catch (NumberFormatException error) { throw new IOException("storage_corrupt", error); }
        if (id <= 0) throw new IOException("storage_corrupt");
        return id;
    }

    public static Object decode(String encoded) throws Exception {
        verifyNativeVersion();
        String[] fields = fields(encoded);
        int expectedId = itemId(encoded);
        byte[] body;
        String expectedType;
        try {
            body = Base64.getDecoder().decode(fields[5]);
            expectedType = new String(Base64.getDecoder().decode(fields[3]), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException error) { throw new IOException("storage_corrupt", error); }
        if (body.length < 4 || body.length > MAX_BYTES || expectedType.length() > 256)
            throw new IOException("storage_corrupt");
        String metadata = fields[1] + "|" + fields[2] + "|" + fields[3];
        if (!hash(join(metadata, body)).equals(fields[4])) throw new IOException("storage_corrupt");
        Class<?> type = itemType();
        ByteBuffer buffer = ByteBuffer.wrap(body);
        Object result = invoke(type.getMethod("loadItem", ByteBuffer.class, int.class), null, buffer, WORLD_VERSION);
        if (result == null || buffer.hasRemaining()) throw new IOException("codec_native_readback_failed");
        if (((Number) invoke(type.getMethod("getID"), result)).intValue() != expectedId
            || !expectedType.equals(invoke(type.getMethod("getFullType"), result)))
            throw new IOException("codec_identity_mismatch");
        return result;
    }
}
