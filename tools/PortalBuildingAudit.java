import java.lang.reflect.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.function.Function;

/** Only standalone parsers; never starts GameWindow, a world, or game UI. */
public class PortalBuildingAudit {
    static int checks;
    static void check(boolean condition, String label) {
        checks++;
        if (!condition) throw new AssertionError(label);
    }
    static Field field(Class<?> type, String name) throws Exception {
        for (Class<?> c=type; c!=null; c=c.getSuperclass()) {
            try { Field f=c.getDeclaredField(name); f.setAccessible(true); return f; }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    static Object parse(Path path) throws Exception {
        Class<?> parser=Class.forName("zombie.scripting.ScriptParser");
        String text=new String(Files.readAllBytes(path),StandardCharsets.UTF_8);
        text=(String)parser.getMethod("stripComments",String.class).invoke(null,text);
        return parser.getMethod("parse",String.class).invoke(null,text);
    }
    static Object first(Object block) throws Exception {
        return ((List<?>)block.getClass().getField("children").get(block)).get(0);
    }
    static String optionValue(Object option, String key) throws Exception {
        Object value=option.getClass().getMethod("getValue",String.class).invoke(option,key);
        return value==null?null:((String)value.getClass().getMethod("getValue").invoke(value)).trim();
    }
    public static void main(String[] args) throws Exception {
        Path mod=Paths.get(args[0]);
        Path scripts=mod.resolve("media/scripts");
        Class<?> manager=Class.forName("zombie.scripting.ScriptManager");
        field(manager,"currentLoadFileMod").set(null,"SuQingPortals");
        field(manager,"currentLoadFileAbsPath").set(null,scripts.resolve("SuQingPortals_Building.txt").toString());
        field(manager,"currentLoadFileName").set(null,"SuQingPortals_Building.txt");
        Object root=parse(scripts.resolve("SuQingPortals_Building.txt"));
        Class<?> block=root.getClass();
        Object moduleBlock=first(root),entityBlock=first(moduleBlock);
        check("SuQingPortals".equals(block.getField("id").get(moduleBlock)),"independent module");
        check("Portal".equals(block.getField("id").get(entityBlock)),"native portal entity");
        Object options=parse(mod.resolve("media/sandbox-options.txt"));
        Object transferOption=block.getMethod("getBlock",String.class,String.class).invoke(options,"option","SuQingPortals.TransferCost");
        check(transferOption!=null,"native sandbox parser finds transfer cost option");
        check("double".equals(optionValue(transferOption,"type")),"transfer cost uses native numeric sandbox type");
        check(Double.parseDouble(optionValue(transferOption,"min"))==0.5,"transfer cost minimum half battery");
        check(Double.parseDouble(optionValue(transferOption,"max"))==4.0,"transfer cost maximum four batteries");
        check(Double.parseDouble(optionValue(transferOption,"default"))==2.0,"transfer cost defaults to two batteries");
        check("SuQingPortals".equals(optionValue(transferOption,"page")),"transfer cost stays on portal sandbox page");
        check("SuQingPortals_TransferCost".equals(optionValue(transferOption,"translation")),"transfer cost translated option reference");
        Class<?> moduleType=Class.forName("zombie.scripting.objects.ScriptModule");
        Object module=moduleType.getConstructor().newInstance();
        moduleType.getField("name").set(module,"SuQingPortals");
        Class<?> entityType=Class.forName("zombie.scripting.entity.GameEntityScript");
        Object entity=entityType.getConstructor().newInstance();
        entityType.getMethod("setModule",moduleType).invoke(entity,module);
        field(entityType,"name").set(entity,"Portal");
        field(entityType,"scriptObjectName").set(entity,"Portal");
        for(Object child:(List<?>)block.getField("children").get(entityBlock))
            entityType.getMethod("LoadComponentBlock",block).invoke(entity,child);
        Class<?> componentType=Class.forName("zombie.entity.ComponentType");
        Object craftType=componentType.getMethod("valueOf",String.class).invoke(null,"CraftRecipe");
        Object spriteType=componentType.getMethod("valueOf",String.class).invoke(null,"SpriteConfig");
        Object craft=entityType.getMethod("getComponentScriptFor",componentType).invoke(entity,craftType);
        Object sprite=entityType.getMethod("getComponentScriptFor",componentType).invoke(entity,spriteType);
        Object recipe=craft.getClass().getMethod("getCraftRecipe").invoke(craft);
        Class<?> rc=recipe.getClass();
        check("SuQingPortals".equals(rc.getMethod("getCategory").invoke(recipe)),"dedicated native build category");
        check("IGUI_SQP_Name".equals(craft.getClass().getMethod("getBuildCategory").invoke(craft)),"translated build menu tag");
        check(((Integer)rc.getMethod("getOutputCount").invoke(recipe))==0,"no kit item output duplication path");
        check(((Integer)rc.getMethod("getRequiredSkillCount").invoke(recipe))==2,"exactly two approved native skill requirements");
        Map<String,Integer> requiredSkills=new HashMap<String,Integer>();
        for(int i=0;i<2;i++) {
            Object requirement=rc.getMethod("getRequiredSkill",int.class).invoke(recipe,i);
            Object perk=requirement.getClass().getMethod("getPerk").invoke(requirement);
            requiredSkills.put((String)perk.getClass().getMethod("getId").invoke(perk),
                (Integer)requirement.getClass().getMethod("getLevel").invoke(requirement));
        }
        check(Integer.valueOf(4).equals(requiredSkills.get("Electricity")),"native Electricity level four");
        check(Integer.valueOf(3).equals(requiredSkills.get("MetalWelding")),"native MetalWelding level three");
        List<?> inputs=(List<?>)rc.getMethod("getInputs").invoke(recipe);
        check(inputs.size()==9,"three retained tools and six exact material rows; no battery or extra welding consumables");
        Class<?> input=Class.forName("zombie.scripting.entity.components.crafting.InputScript");
        String[] tools={"screwdriver","blowtorch","welding mask"};
        for(int i=0;i<3;i++) {
            Object row=inputs.get(i);
            check(((Float)input.getMethod("getAmount").invoke(row))==1,"one retained "+tools[i]);
            check((Boolean)input.getMethod("isKeep").invoke(row),"native keep mode retains "+tools[i]);
            check(!(Boolean)input.getMethod("isDestroy").invoke(row),"retained tool is never destroyed "+tools[i]);
            check((Boolean)input.getMethod("isItemCount").invoke(row),"tool counts original item, not drainable fuel uses "+tools[i]);
        }
        Class<?> itemTag=Class.forName("zombie.scripting.objects.ItemTag");
        check(((Set<?>)input.getMethod("getItemTags").invoke(inputs.get(0))).contains(itemTag.getField("SCREWDRIVER").get(null)),"native screwdriver tag");
        check(((List<?>)input.getMethod("getItems").invoke(inputs.get(1))).equals(Arrays.asList("Base.BlowTorch")),"actual native blowtorch ID retained without fuel debit");
        check(((Set<?>)input.getMethod("getItemTags").invoke(inputs.get(2))).contains(itemTag.getField("WELDING_MASK").get(null)),"native welding mask tag");
        String[] ids={"Base.SmallSheetMetal","Base.MetalPipe","Base.ElectricWire","Base.ElectronicsScrap","Base.CameraExpensive"};
        int[] amounts={8,4,8,16,1,1};
        for(int i=0;i<6;i++) {
            Object row=inputs.get(i+3);
            check(((Float)input.getMethod("getAmount").invoke(row))==amounts[i],"exact material count row "+i);
            check((Boolean)input.getMethod("isItemCount").invoke(row),"physical material count row "+i);
            check((Boolean)input.getMethod("isDestroy").invoke(row),"native whole-item consumption row "+i);
            check(!(Boolean)input.getMethod("isKeep").invoke(row),"material is not retained row "+i);
            if(i<5) check(((List<?>)input.getMethod("getItems").invoke(row)).equals(Arrays.asList(ids[i])),"exact native material ID row "+i);
        }
        Set<String> walkieIds=new HashSet<String>(Arrays.asList("Base.WalkieTalkie1","Base.WalkieTalkie2","Base.WalkieTalkie3","Base.WalkieTalkie4","Base.WalkieTalkie5","Base.WalkieTalkieMakeShift"));
        List<?> walkieOptions=(List<?>)input.getMethod("getItems").invoke(inputs.get(8));
        check(walkieOptions.size()==6&&new HashSet<Object>(walkieOptions).equals(walkieIds),"one handheld walkie-talkie accepts all six current vanilla variants only");
        check("SuQingPortals.World.OnCreate".equals(sprite.getClass().getMethod("getOnCreate").invoke(sprite)),"registration callback only");
        check(((Integer)sprite.getClass().getMethod("getHealth").invoke(sprite))==500,"fixed gate health");
        Set<String> faces=new HashSet<String>(),tiles=new HashSet<String>();
        for(int i=0;i<4;i++) {
            Object face=sprite.getClass().getMethod("getFace",int.class).invoke(sprite,i);
            check(face!=null,"face exists "+i);
            faces.add(face.getClass().getMethod("getFaceName").invoke(face).toString().toUpperCase());
            Object layer=face.getClass().getMethod("getLayer",int.class).invoke(face,0);
            Object row=layer.getClass().getMethod("getRow",int.class).invoke(layer,0);
            Object tile=row.getClass().getMethod("getTile",int.class).invoke(row,0);
            tiles.add((String)tile.getClass().getMethod("getTileName").invoke(tile));
            check(((Integer)face.getClass().getMethod("getTotalWidth").invoke(face))==1,"single-tile width");
            check(((Integer)face.getClass().getMethod("getTotalHeight").invoke(face))==1,"single-tile depth");
        }
        check(faces.equals(new HashSet<String>(Arrays.asList("S","E","N","W"))),"four compass facings");
        for(int i=0;i<4;i++) check(tiles.contains("suqing_portal_01_"+i),"empty gate art mapping "+i);
        Object styleBlock=first(first(first(parse(scripts.resolve("SuQingPortals_Xui.txt")))));
        Class<?> skinType=Class.forName("zombie.scripting.objects.XuiSkinScript");
        Object skin=skinType.getConstructor().newInstance();
        Method load=skinType.getDeclaredMethod("LoadEntityBlock",block);load.setAccessible(true);load.invoke(skin,styleBlock);
        Object style=((Map<?,?>)skinType.getMethod("getEntityUiScriptMap").invoke(skin)).get("ES_SuQingPortal");
        check(style!=null,"native XUI entity style");
        check("IGUI_SQP_Name".equals(style.getClass().getMethod("getDisplayName").invoke(style)),"translated native XUI name");
        check("IGUI_SQP_BuildDescription".equals(style.getClass().getMethod("getBuildDescription").invoke(style)),"translated native XUI description");
        Class<?> translator=Class.forName("zombie.core.Translator"),languageType=Class.forName("zombie.core.Language");
        Constructor<?> languageCtor=languageType.getDeclaredConstructor(String.class,String.class,String.class,boolean.class);languageCtor.setAccessible(true);
        Method fill=translator.getDeclaredMethod("tryFillMapFromFile",String.class,String.class,Map.class,languageType,Function.class);fill.setAccessible(true);
        final Method formatFixer=translator.getDeclaredMethod("formatFixer",String.class);formatFixer.setAccessible(true);
        Function<String,String> nativeFormat=new Function<String,String>() {
            public String apply(String value) {
                try { return (String)formatFixer.invoke(null,value); }
                catch(ReflectiveOperationException error) { throw new IllegalStateException("Native translation format conversion failed",error); }
            }
        };
        String[] filenames={"IG_UI","Recipes","Sandbox","Tooltip","Mod"};
        for(String lang:Arrays.asList("CN","EN")) {
            Object language=languageCtor.newInstance(lang,lang,"EN",false);
            translator.getField("language").set(null,language);
            for(String file:filenames) {
                Map<String,String> map=new HashMap<String,String>();
                // The real JSON loader converts legacy source %1 to Java %1$s.
                // Identity bypasses this conversion and falsely accepts %1$s
                // in source JSON, which becomes %1$s$s in the actual game.
                fill.invoke(null,mod.toString(),file,map,language,nativeFormat);
                check(!map.isEmpty(),"native JSON translation reader "+lang+"/"+file);
                if(file.equals("IG_UI")) {
                    String rawJson=new String(Files.readAllBytes(mod.resolve("media/lua/shared/Translate").resolve(lang).resolve("IG_UI.json")),StandardCharsets.UTF_8);
                    Class<?> jsonType=Class.forName("org.json.JSONObject");
                    Object json=jsonType.getConstructor(String.class).newInstance(rawJson);
                    @SuppressWarnings("unchecked") Map<String,Object> sourceMap=(Map<String,Object>)jsonType.getMethod("toMap").invoke(json);
                    for(Map.Entry<String,Object> entry:sourceMap.entrySet()) {
                        String source=String.valueOf(entry.getValue());
                        check(!source.matches("(?s).*%[1-9]\\$[sdf].*")&&!source.contains("$s"),
                            "raw JSON uses native source placeholders without printf suffix "+lang+" "+entry.getKey());
                    }
                    check(map.containsKey("IGUI_SQP_Open")&&map.containsKey("IGUI_SQP_Teleport"),"management UI localization "+lang);
                    check(map.containsKey("IGUI_SQP_Result_arrived"),"player result localization "+lang);
                    @SuppressWarnings("unchecked") Map<String,String> actual=(Map<String,String>)field(translator,"igui").get(null);
                    actual.clear();actual.putAll(map);
                    Method getText=translator.getMethod("getText",String.class,Object[].class);
                    String named=(String)getText.invoke(null,"IGUI_SQP_OpenNamed",new Object[]{"SQP-5"});
                    String expectedNamed=lang.equals("CN")?"打开 SQP-5 的传送门管理":"Manage portal: SQP-5";
                    check(expectedNamed.equals(named),"actual native source-loader OpenNamed SQP-5 exact "+lang);
                    String literalName="Gate $s with 100% name";
                    String namedLiteral=(String)getText.invoke(null,"IGUI_SQP_OpenNamed",new Object[]{literalName});
                    String expectedLiteral=lang.equals("CN")?"打开 "+literalName+" 的传送门管理":"Manage portal: "+literalName;
                    check(expectedLiteral.equals(namedLiteral),"player name containing literal dollar-s and percent remains intact "+lang);
                    for(String percent:Arrays.asList("0","50","100")) {
                        String installed=(String)getText.invoke(null,"IGUI_SQP_SlotInstalled",new Object[]{"4",percent});
                        check(installed.contains(percent+"%")&&!installed.contains("%1")&&!installed.contains("$s")&&!installed.contains("%%"),"actual native slot formatter "+lang+" "+percent);
                        String stats=(String)getText.invoke(null,"IGUI_SQP_BatteryStats",new Object[]{percent,"80"});
                        check(stats.contains(percent+"%")&&stats.contains("80%")&&!stats.contains("$s")&&!stats.contains("%%"),"actual native charge/condition formatter "+lang+" "+percent);
                        String menu=(String)getText.invoke(null,"IGUI_SQP_BatteryMenu",new Object[]{"Battery with 100% name",percent});
                        check(menu.contains("Battery with 100% name")&&menu.contains(percent+"%"),"item names do not become format strings "+lang+" "+percent);
                    }
                    for(Map.Entry<String,String> entry:map.entrySet()) {
                        String rendered=(String)getText.invoke(null,entry.getKey(),new Object[]{"1","50","80","0"});
                        // Sentinel arguments contain no tokens, so any suffix
                        // here is template residue, not a legitimate player name.
                        check(!rendered.matches("(?s).*%[1-9](?:\\$[sdf])?.*")&&!rendered.contains("$s"),"native parameter substitution "+lang+" "+entry.getKey());
                    }
                }
                if(file.equals("Recipes")) check(map.containsKey("Portal")&&map.containsKey("SuQingPortals.Portal"),"native recipe names "+lang);
                if(file.equals("Sandbox")) check(map.containsKey("Sandbox_SuQingPortals_TransferCost")&&map.containsKey("Sandbox_SuQingPortals_TransferCost_tooltip"),"transfer cost sandbox name and tooltip "+lang);
                if(file.equals("Mod")) check(map.containsKey("name")&&map.containsKey("description"),"native mod selector fields "+lang);
            }
        }
        System.out.println("PORTAL_BUILDING_NATIVE checks="+checks+" failures=0 game_started=false");
    }
}
