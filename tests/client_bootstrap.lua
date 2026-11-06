-- Client-only streaming/flag mocks layered over the shared World fixture.
TEST.clock = 0
function getTimestampMs() return TEST.clock end
SandboxVars = { SuQingPortals = { ChargePerHour = 0.5 } }
TEST.queued={}
ISTimedActionQueue={getTimedActionQueue=function(player) return {queue=TEST.queued} end,
    add=function(action) TEST.queued[#TEST.queued+1]=action end}
luautils={walkAdjObject=function() TEST.walkRequests=(TEST.walkRequests or 0)+1;return not TEST.pathBlocked end}
ISBaseTimedAction={}
function ISBaseTimedAction:derive() local t={};t.__index=t;setmetatable(t,{__index=self});return t end
function ISBaseTimedAction.new(self,character) return setmetatable({character=character},self) end
function ISBaseTimedAction:perform()
    for i,action in ipairs(TEST.queued) do if action==self then table.remove(TEST.queued,i);break end end
end
function ISBaseTimedAction:stop() ISBaseTimedAction.perform(self) end
function ISBaseTimedAction:setActionAnim() end
local baseSquare,basePlayer = TEST.square,TEST.player
function TEST.square(x,y,z,powered)
    local square=baseSquare(x,y,z,powered)
    square.floor,square.free,square.moving=true,true,TEST.list()
    function square:TreatAsSolidFloor() return self.floor end
    function square:isFree() return self.free end
    function square:isVehicleIntersecting() return self.vehicle or false end
    function square:haveFire() return self.fire or false end
    function square:getMovingObjects() return self.moving end
    function square:canReachTo(other) return not self.unreachable end
    return square
end
function TEST.player(square,index)
    local player=basePlayer(square,index)
    player.x,player.y,player.z=square.x+0.5,square.y+0.5,square.z
    player.noClip,player.ghost,player.block=false,false,false
    player.messages={}
    function player:getX() return self.x end
    function player:getY() return self.y end
    function player:getZ() return self.z end
    function player:getSquare() return getCell():getGridSquare(math.floor(self.x),math.floor(self.y),math.floor(self.z)) end
    function player:isDead() return self.dead or false end
    function player:isOnFire() return self.onFire or false end
    function player:getVehicle() return self.vehicle end
    function player:isNoClip() return self.noClip end
    function player:isGhostMode() return self.ghost end
    function player:isBlockMovement() return self.block end
    function player:setNoClip(value,force)
        if self.rejectProtection and value then return end
        if self.rejectRestore and not value then return end
        self.noClip=value
    end
    function player:setGhostMode(value,force)
        if self.rejectProtection and value then return end
        self.ghost=value
    end
    function player:setBlockMovement(value) self.block=value end
    function player:teleportTo(x,y,z)
        if self.failMoveOnce then self.failMoveOnce=false;error('native move failed') end
        self.x,self.y,self.z=x,y,z
        self.moveCount=(self.moveCount or 0)+1
    end
    function player:Say(text) self.messages[#self.messages+1]=text end
    function player:faceThisObject() end
    function player:shouldBeTurning() return false end
    function player:SetVariable() end
    return player
end
function TEST.reset()
    local database=ModData.getOrCreate("SuQingPortals.World")
    for entry in pairs(database) do database[entry]=nil end
    TEST.squares,TEST.players,TEST.generators={},{},{}
    TEST.queued={}
    TEST.pathBlocked=false
    if SuQingPortals.Actions then SuQingPortals.Actions.pending={} end
    TEST.clock=0
    TEST.hours=100
    SandboxVars.SuQingPortals.TransferCost=2
    if SuQingPortals and SuQingPortals.Transfer then SuQingPortals.Transfer.active={} end
    Events.OnGameStart.run()
end

-- Presentation-only UI mocks. Native text formatting is verified separately by
-- PortalBuildingAudit using the current game's actual Translator.getText.
local function widget()
    local t={}
    function t:derive() local c={};c.__index=c;setmetatable(c,{__index=self});return c end
    function t:new(x,y,w,h) return setmetatable({x=x,y=y,width=w,height=h,children={},scrollY=0},self) end
    function t:initialise() end
    function t:instantiate() if not self.created then self.created=true;self:createChildren() end end
    function t:createChildren() end
    function t:addChild(child) self.children[#self.children+1]=child end
    function t:noBackground() end
    function t:addScrollBars() self.vscroll={} end
    function t:setScrollChildren() end
    function t:setScrollHeight(value) self.scrollHeight=value end
    function t:getYScroll() return self.scrollY or 0 end
    function t:setYScroll(value) self.scrollY=value end
    function t:setStencilRect() end
    function t:clearStencilRect() end
    function t:titleBarHeight() return math.max(16,(TEST.fontH or 16)+1) end
    function t:getX() return self.x end
    function t:getY() return self.y end
    function t:getWidth() return self.width end
    function t:getHeight() return self.height end
    function t:setX(value) self.x=value end
    function t:setY(value) self.y=value end
    function t:setWidth(value)
        local delta=value-self.width;self.width=value
        for _,child in ipairs(self.children) do
            if child.anchorRight then
                if child.anchorLeft then child.width=child.width+delta else child.x=child.x+delta end
            end
        end
    end
    function t:setHeight(value)
        local delta=value-self.height;self.height=value
        for _,child in ipairs(self.children) do
            if child.anchorBottom then
                if child.anchorTop then child.height=child.height+delta else child.y=child.y+delta end
            end
        end
    end
    function t:onResize()
        TEST.nativeResizeCalls=(TEST.nativeResizeCalls or 0)+1
        if self.minimumWidth and self.width<self.minimumWidth then self:setWidth(self.minimumWidth) end
        if self.minimumHeight and self.height<self.minimumHeight then self:setHeight(self.minimumHeight) end
    end
    function t:setVisible(value) self.visible=value end
    function t:setEnable(value) self.enabled=value end
    function t:setTitle(value) self.title=value end
    function t:addToUIManager() self.visible=true end
    function t:removeFromUIManager() self.visible=false end
    function t:prerender() end
    function t:render() end
    function t:update() end
    function t:drawText(value) TEST.drawn=TEST.drawn or {};TEST.drawn[#TEST.drawn+1]=value end
    function t:drawRect(x,y,w,h) TEST.assert(w>=0 and h>=0,'UI draws nonnegative geometry') end
    function t:drawRectBorder() end
    return t
end
ISPanel=widget();ISPanel.__index=ISPanel
ISUIElement=ISPanel
ISCollapsableWindow=ISPanel:derive()
function ISCollapsableWindow:resizeWidgetHeight() return ((TEST.fontH or 16)+6)/2+2 end
function ISCollapsableWindow:createChildren()
    local h=self:resizeWidgetHeight()
    self.resizeWidget=ISPanel:new(self.width-h,self.height-h,h,h)
    self.resizeWidget.anchorRight,self.resizeWidget.anchorBottom=true,true
    self:addChild(self.resizeWidget)
    self.resizeWidget2=ISPanel:new(0,self.height-h,self.width-h,h)
    self.resizeWidget2.anchorLeft,self.resizeWidget2.anchorRight,self.resizeWidget2.anchorBottom=true,true,true
    self:addChild(self.resizeWidget2)
end
function ISCollapsableWindow:setResizable(value)
    self.resizable=value
    self.resizeWidget:setVisible(value);self.resizeWidget2:setVisible(value)
end
ISButton=ISPanel:derive()
function ISButton:new(x,y,w,h,title,target,callback)
    local o=ISPanel.new(self,x,y,w,h);o.title,o.target,o.callback=title,target,callback;return o
end
ISComboBox=ISPanel:derive()
function ISComboBox:new(x,y,w,h) local o=ISPanel.new(self,x,y,w,h);o.options={};o.selected=1;return o end
function ISComboBox:clear() self.options={};self.selected=1 end
function ISComboBox:addOptionWithData(text,data) self.options[#self.options+1]={text=text,data=data} end
function ISComboBox:getOptionData(index) return self.options[index] and self.options[index].data end
function ISComboBox:getOptionCount() return #self.options end
ISTextEntryBox=ISPanel:derive()
function ISTextEntryBox:new(value,x,y,w,h) local o=ISPanel.new(self,x,y,w,h);o.value=value;return o end
function ISTextEntryBox:setText(value) self.value=value end
function ISTextEntryBox:getText() return self.value end
function ISTextEntryBox:setMaxTextLength(value) self.limit=value end
UIFont={Small='Small',Medium='Medium'}
function getCore() return {getScreenWidth=function() return TEST.screenWidth or 1366 end,getScreenHeight=function() return TEST.screenHeight or 768 end,
    getZoom=function() return TEST.zoom or 1 end} end
function getTextManager() return {getFontHeight=function() return TEST.fontH or 16 end,
    MeasureStringX=function(self,font,value) return #value*((TEST.fontH or 16)/2) end} end
function getText(key,...)
    local args={...}
    TEST.textCalls=TEST.textCalls or {}
    TEST.textCalls[#TEST.textCalls+1]={key=key,args=args}
    local out=key;for _,arg in ipairs(args) do out=out..' '..tostring(arg) end;return out
end
function getTextOrNull(key) return 'ui:'..key end
function getMouseX() return TEST.mouseX or 0 end
function getMouseY() return TEST.mouseY or 0 end
function instanceof(item,typeName) return item and (item.class==typeName or (typeName=='InventoryContainer' and item.getInventory~=nil)) end
IsoUtils={XToScreen=function(x,y,z) return (x-y)*64 end,YToScreen=function(x,y,z) return (x+y)*32-z*96 end}
IsoCamera={getOffX=function() return 0 end,getOffY=function() return 0 end,getScreenLeft=function() return 0 end,getScreenTop=function() return 0 end}
TEST.contextPickCalls=0
TEST.pickThumpableCalls=0
IsoObjectPicker={Instance={
    ContextPick=function()
        TEST.contextPickCalls=TEST.contextPickCalls+1
        error('ContextPick returns an opaque native ClickObject; production must not consume it')
    end,
    PickThumpable=function(self,x,y)
        TEST.pickThumpableCalls=TEST.pickThumpableCalls+1
        TEST.lastPickerX,TEST.lastPickerY=x,y
        return TEST.picked
    end,
}}
ISWorldObjectContextMenu={}
for _,name in ipairs({'OnGameBoot','OnFillWorldObjectContextMenu'}) do
    Events[name]={Add=function() end}
end

local baseBattery=TEST.battery
function TEST.battery(...)
    local item=baseBattery(...)
    function item:getDisplayName() return self:getName() end
    function item:getConditionMax() return 100 end
    return item
end

local baseContainer=TEST.container
function TEST.container(parent)
    local container=baseContainer(parent)
    local addOriginal=container.AddItem
    function container:AddItem(item)
        if type(item)=="string" then
            if TEST.failCreateType==item then TEST.failCreateType=nil;return nil end
            -- Standalone factory fixture only. Native recipe auditing separately
            -- verifies these exact installed-game item IDs and tool semantics.
            item=TEST.battery(item=="Base.CarBattery1" and 0.25 or 1,item,100)
        end
        return addOriginal(self,item)
    end
    function container:getItemWithIDRecursiv(id)
        for _,item in ipairs(self.list.values) do
            if item.getID and item:getID()==id then return item end
            if item.getInventory then
                local found=item:getInventory():getItemWithIDRecursiv(id)
                if found then return found end
            end
        end
    end
    function container:containsRecursive(item)
        if self:contains(item) then return true end
        for _,candidate in ipairs(self.list.values) do
            if candidate.getInventory and candidate:getInventory():containsRecursive(item) then return true end
        end
        return false
    end
    return container
end
