import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Only standalone native parser calls, no PZ world/engine/renderer startup. */
public class PortalAssetsNativeReadback {
    static Object call(Class<?> type, String name, Class<?>[] signature, Object... args) throws Exception {
        Method method = type.getDeclaredMethod(name, signature);
        method.setAccessible(true);
        return method.invoke(null, args);
    }
    static int readInt(Class<?> type, InputStream input) throws Exception {
        return (Integer)call(type, "readInt", new Class<?>[]{InputStream.class}, input);
    }
    static Object field(Object object, String name) throws Exception {
        Field field = object.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field.get(object);
    }
    public static void main(String[] args) throws Exception {
        Path media = Paths.get(args[0]);
        Class<?> pageType = Class.forName("zombie.core.textures.TexturePackPage");
        try (InputStream input = new BufferedInputStream(Files.newInputStream(media.resolve("texturepacks/SuQingPortals_tiles.pack")))) {
            byte[] magic = new byte[4];
            if (input.read(magic) != 4 || !Arrays.equals(magic, new byte[]{80,90,80,75})) throw new AssertionError("pack magic");
            if (readInt(pageType,input) != 1 || readInt(pageType,input) != 1) throw new AssertionError("version/page count");
            String page = (String)call(pageType,"ReadString",new Class<?>[]{InputStream.class},input);
            if (!"SuQingPortals_tiles_0".equals(page) || readInt(pageType,input) != 64 || readInt(pageType,input) != 1) throw new AssertionError("page layout");
            for (int i=0; i<64; i++) {
                String name=(String)call(pageType,"ReadString",new Class<?>[]{InputStream.class},input);
                if (!name.equals("suqing_portal_01_"+i)) throw new AssertionError("sprite name "+i);
                int[] wanted={(i%4)*128,(i/4)*256,128,256,0,0,128,256};
                for (int value:wanted) if (readInt(pageType,input)!=value) throw new AssertionError("sprite rectangle "+i);
            }
            int length=readInt(pageType,input); byte[] png=new byte[length]; int pos=0,n;
            while (pos<length && (n=input.read(png,pos,length-pos))!=-1) pos+=n;
            if (pos!=length || input.read()!=-1) throw new AssertionError("PNG byte length/EOF");
            java.awt.image.BufferedImage image=javax.imageio.ImageIO.read(new ByteArrayInputStream(png));
            if (image==null || image.getWidth()!=512 || image.getHeight()!=4096) throw new AssertionError("PNG decode");
            System.out.println("PASS current PZ TexturePackPage integer/string readers: 64 standard 128x256 RGBA frames, 512x4096 PNG");
        }
        Class<?> objReader=Class.forName("viewpoint.packs.ObjReader");
        for (int mask=0;mask<16;mask++) {
            Object mesh=call(objReader,"parse",new Class<?>[]{List.class},Files.readAllLines(media.resolve("viewpoint/portal_"+mask+".obj")));
            Method vm=mesh.getClass().getDeclaredMethod("vertices"); vm.setAccessible(true);
            Method im=mesh.getClass().getDeclaredMethod("indices"); im.setAccessible(true);
            Method mm=mesh.getClass().getDeclaredMethod("mtllib"); mm.setAccessible(true);
            float[] vertices=(float[])vm.invoke(mesh); int[] indices=(int[])im.invoke(mesh);
            if (vertices.length==0 || indices.length!=(1128+Integer.bitCount(mask)*36)*3) throw new AssertionError("OBJ geometry "+mask);
            if (!"portal.mtl".equals(mm.invoke(mesh))) throw new AssertionError("MTL reference "+mask);
            for (float value:vertices) if (!Float.isFinite(value)) throw new AssertionError("OBJ nonfinite "+mask);
            System.out.println("PASS current Viewpoint ObjReader slotMask="+mask+", triangles="+indices.length/3);
        }
        Class<?> manifestType=Class.forName("viewpoint.packs.PackManifest");
        Object parsed=call(manifestType,"parse",new Class<?>[]{List.class},Files.readAllLines(media.resolve("viewpoint/package.properties")));
        List<?> errors=(List<?>)field(parsed,"errors");
        Map<?,?> binds=(Map<?,?>)field(parsed,"binds"), models=(Map<?,?>)field(parsed,"models");
        if (!errors.isEmpty() || binds.size()!=64 || models.size()!=16) throw new AssertionError("manifest "+errors);
        int[] degrees={0,-90,180,90};
        for (int i=0;i<64;i++) {
            Object entry=binds.get("suqing_portal_01_"+i);
            if (entry==null || ((Float)field(entry,"degrees")).floatValue()!=degrees[i%4]
                    || !("suqing_portal_"+(i/4)).equals(field(entry,"model"))) throw new AssertionError("bind "+i);
            if (((Float)field(entry,"x")).floatValue()!=0f || ((Float)field(entry,"y")).floatValue()!=0f
                    || ((Float)field(entry,"z")).floatValue()!=0f || ((Float)field(entry,"scale")).floatValue()!=1f)
                throw new AssertionError("unintended model pivot/scale compensation "+i);
        }
        System.out.println("PASS current Viewpoint PackManifest: 16 occupancy models, 64 correctly rotated bindings, no parser errors");

        // WorldMesher's current source passes j+0.5/i+0.5 to PackGather, which
        // forwards those centers into Recipe.model. Verify this latter native
        // placement step adds only authored bind offsets, never another 0.5.
        Class<?> packModelType=Class.forName("viewpoint.render.PackModel");
        Class<?> bindType=Class.forName("viewpoint.packs.PackBind");
        Object binding=bindType.getConstructor(packModelType,float.class,float.class,float.class,float.class,float.class)
                .newInstance(null,0f,0f,0f,0f,1f);
        Class<?> recipeType=Class.forName("viewpoint.world.Recipe");
        Constructor<?> recipeConstructor=recipeType.getDeclaredConstructor(int.class); recipeConstructor.setAccessible(true);
        Object recipe=recipeConstructor.newInstance(0);
        Method modelMethod=recipeType.getDeclaredMethod("model",recipeType,bindType,boolean.class,
                float.class,float.class,float.class,int.class,int.class,int.class);
        modelMethod.setAccessible(true);
        modelMethod.invoke(null,recipe,binding,true,0.5f,0.5f,0f,0,0,0);
        List<?> operations=(List<?>)field(recipe,"models");
        Object operation=operations.get(0);
        if (((Float)field(operation,"dx")).floatValue()!=0.5f || ((Float)field(operation,"dy")).floatValue()!=0.5f
                || ((Float)field(operation,"height")).floatValue()!=0f) throw new AssertionError("model center placement");
        System.out.println("PASS current Viewpoint Recipe.model keeps supplied tile center (0.5,0.5), floor Z=0, no duplicate center offset");
        System.out.println("Scope: offline standalone parser calls only. No engine, world, GL, game process, or gameplay acceptance.");
    }
}
