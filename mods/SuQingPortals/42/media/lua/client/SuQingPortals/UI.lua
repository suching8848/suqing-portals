require "ISUI/ISCollapsableWindow"
require "ISUI/ISUIElement"
require "ISUI/ISPanel"
require "ISUI/ISButton"
require "ISUI/ISComboBox"
require "ISUI/ISTextEntryBox"
require "ISUI/ISContextMenu"
require "SuQingPortals/Core"
require "SuQingPortals/Actions"

local P = SuQingPortals
P.UI = P.UI or {}
local U = P.UI
local Window = ISCollapsableWindow:derive("SuQingPortalsWindow")
U.Window = Window
local purple = {0.86,0.75,1}
local pale = {0.80,0.84,0.9}
local function text(key, ...) return getText("IGUI_SQP_" .. key, ...) end

function U.transferCost(snapshot)
    local cost=tonumber(snapshot and snapshot.cost)
    if cost and cost==cost and cost>0 then return cost end
    return P.Core.getTransferCost()
end

function U.tripCount(snapshot)
    return math.max(0,math.floor(((snapshot and snapshot.totalCharge or 0)+P.Core.EPSILON)/U.transferCost(snapshot)))
end

function U.reasonText(code,snapshot)
    local cost=string.format("%.2f",U.transferCost(snapshot))
    if code=="insufficient_charge" then return text("InsufficientCharge",cost) end
    if not code then return text("ReadyReason",cost) end
    return U.resultText(code)
end

-- Source labels come from the loaded gate's verified World snapshot only.
function U.powerText(snapshot)
    local info=snapshot and snapshot.powerInfo
    if not info or info.powered==nil then return text("PowerUnknown"),nil end
    if not info.powered then return text("PowerDisconnected"),false end
    local source=info.source
    local known={grid=true,generator=true,solar=true,livewire=true,grid_generator=true,grid_area=true,area=true}
    if not known[source] then source="area" end
    return text("PowerConnected",text("PowerSource_"..source)),true
end

function U.chargingState(snapshot)
    local s=snapshot or {}
    if s.migrationRequired then return "MigrationStatus" end
    if not s.storageReady then return "StorageUnavailable" end
    if s.pending then return "TravelBusy" end
    if s.chargeError=="power_unsupported" then return "ChargingUnsupported" end
    if s.chargeError=="power_livewire_unavailable" then return "ChargingLiveWireUnavailable" end
    if s.chargeError then return "ChargingFault" end
    local installed,healthy,needsCharge=0,0,false
    for slot=1,4 do
        local item=s.slots and s.slots[slot]
        if item and item.itemId then
            installed=installed+1
            if (item.condition or 0)>0 then
                healthy=healthy+1
                if (item.charge or 0)<1-P.Core.EPSILON then needsCharge=true end
            end
        end
    end
    if installed==0 then return "ChargingNoBattery" end
    if healthy==0 then return "ChargingDamaged" end
    if not needsCharge then return "ChargingFull" end
    if s.loaded==false then return "ChargingUnloaded" end
    local info=s.powerInfo
    if info and info.error=="power_livewire_unavailable" then return "ChargingLiveWireUnavailable" end
    if not info or info.powered==nil then return "ChargingUnknown" end
    if info.powered and info.metered==false then return "ChargingUnsupported" end
    return info.powered and "ChargingActive" or "ChargingUnpowered"
end

function U.resultText(code)
    local key = "IGUI_SQP_Result_" .. tostring(code or "unknown")
    local translated = getTextOrNull and getTextOrNull(key) or getText(key)
    if translated and translated ~= key then return translated end
    print("[SuQingPortals] untranslated result: " .. tostring(code))
    return text("Result_unknown")
end

function U.collectBatteries(container, result)
    result = result or {}
    if not container then return result end
    local items = container:getItems()
    for index = 0, items:size() - 1 do
        local item = items:get(index)
        if P.Core.isBattery(item) then result[#result+1] = item end
        if instanceof(item, "InventoryContainer") then U.collectBatteries(item:getInventory(), result) end
    end
    table.sort(result,function(a,b)
        if a:getDisplayName() == b:getDisplayName() then return a:getID() < b:getID() end
        return a:getDisplayName() < b:getDisplayName()
    end)
    return result
end

function U.batteryLabel(item)
    local percent = math.floor(P.Core.chargeOf(item) * 100 + 0.5)
    return text("BatteryMenu", item:getDisplayName(), tostring(percent))
end

local function addButton(window, parent, x, y, width, label, callback, height,argument)
    local caption=argument~=nil and text(label,argument) or text(label)
    local button = ISButton:new(x,y,width,height or window.rowH,caption,window,callback)
    button:initialise();button:instantiate();parent:addChild(button)
    return button
end

local function line(panel,label,x,y,width,color,font)
    font=font or UIFont.Small
    local shown=tostring(label or "")
    local tm=getTextManager()
    if tm:MeasureStringX(font,shown)>width then
        while #shown>0 and tm:MeasureStringX(font,shown.."...")>width do shown=shown:sub(1,-2) end
        shown=shown.."..."
    end
    panel:drawText(shown,x,y,color[1],color[2],color[3],1,font)
end

function Window:new(player,object)
    local screenW,screenH=getCore():getScreenWidth(),getCore():getScreenHeight()
    local fontH=getTextManager():getFontHeight(UIFont.Small)
    local width=math.min(math.max(900,fontH*44),math.max(1,screenW-40))
    local height=math.min(708,math.max(1,screenH-40))
    local o=ISCollapsableWindow.new(self,(screenW-width)/2,(screenH-height)/2,width,height)
    o.player,o.object=player,object
    o.fontH=fontH
    o.rowH=math.max(28,o.fontH+10)
    o.resizable=true
    o.minimumWidth=math.min(640,math.max(1,screenW-40))
    o.minimumHeight=math.min(500,math.max(1,screenH-40))
    o.title=text("WindowTitle")
    o.backgroundColor={r=0.06,g=0.055,b=0.09,a=0.97}
    o.borderColor={r=0.61,g=0.48,b=0.8,a=0.95}
    o.message="";o.refreshTicks=0
    return o
end

function Window:createChildren()
    ISCollapsableWindow.createChildren(self)
    self:setResizable(true)
    local content=ISPanel:new(12,self:titleBarHeight()+8,self.width-24,100)
    content:initialise();content:instantiate();content:noBackground()
    content:addScrollBars();content:setScrollChildren(true)
    content.doStencilRender=true
    content.onMouseWheel=function(panel,delta) panel:setYScroll(panel:getYScroll()-delta*36);return true end
    content.prerender=function(panel)
        panel:setStencilRect(0,0,panel:getWidth(),panel:getHeight())
        ISPanel.prerender(panel)
    end
    content.render=function(panel)
        self:renderContent(panel)
        panel:clearStencilRect()
    end
    self:addChild(content);self.content=content
    self.nameEntry=ISTextEntryBox:new("",8,0,100,self.rowH)
    self.nameEntry:initialise();self.nameEntry:instantiate();self.nameEntry:setMaxTextLength(48)
    content:addChild(self.nameEntry)
    self.renameButton=addButton(self,content,0,0,132,"Rename",self.onRename)
    self.slotCards={};self.slotButtons={}
    for slot=1,4 do
        local button=addButton(self,content,0,0,100,"Install",self.onBattery)
        button.slot=slot;self.slotButtons[slot]=button
    end
    self.targetCombo=ISComboBox:new(8,0,100,self.rowH,self,nil)
    self.targetCombo:initialise();self.targetCombo:instantiate();content:addChild(self.targetCombo)
    self.refreshButton=addButton(self,content,0,0,132,"Refresh",self.onRefresh)
    self.pairButton=addButton(self,content,0,0,100,"Pair",self.onPair)
    self.unpairButton=addButton(self,content,0,0,100,"Unpair",self.onUnpair)
    self.legacyButton=addButton(self,content,0,0,100,"RecoverLegacy",self.onRecoverLegacy)
    self.teleportButton=addButton(self,self,16,0,self.width-32,"Teleport",self.onTeleport,self.rowH+10,string.format("%.2f",U.transferCost(nil)))
    self.teleportButton.backgroundColor={r=0.29,g=0.18,b=0.43,a=1}
    self.teleportButton.backgroundColorMouseOver={r=0.42,g=0.27,b=0.60,a=1}
    self:layout()
    self:refresh(true);self:refreshList()
end

local function place(control,x,y,width,height)
    control:setX(x);control:setY(y);control:setWidth(width);control:setHeight(height)
end

-- Reflow the existing controls; resizing preserves typed names and list selection.
function Window:layout()
    if not self.content then return end
    local top=self:titleBarHeight()+8
    local footerH=self.rowH+12+self.fontH*2+14+self:resizeWidgetHeight()
    local footerY=self.height-footerH
    place(self.content,12,top,math.max(1,self.width-24),math.max(40,footerY-top-6))
    local width=math.max(1,self.content.width-20)
    local side=math.min(132,math.floor(width*0.3))
    local y=6
    place(self.nameEntry,8,y,math.max(1,width-side-16),self.rowH)
    place(self.renameButton,width-side,y,side,self.rowH)
    y=y+self.rowH+6;self.identityY=y;self.destinationY=y
    self.identityW=math.floor(width*0.4)-12
    self.destinationX=math.floor(width*0.4)+8
    y=y+self.fontH+4
    self.powerY=y;self.powerH=self.fontH*3+16
    self.connectionY=y+6;self.chargingY=y+self.fontH+10;self.rateY=y+self.fontH*2+14
    y=y+self.powerH+8;self.metricsY=y
    y=y+self.fontH+6;self.slotsTitleY=y
    y=y+self.fontH+6
    local cardW=math.floor((width-24)/2)
    self.cardH=self.fontH*2+30
    local tm=getTextManager()
    local buttonW=math.min(math.floor(cardW*0.48),math.max(112,
        tm:MeasureStringX(UIFont.Small,text("Install"))+18,tm:MeasureStringX(UIFont.Small,text("Remove"))+18))
    for slot=1,4 do
        local cardX=8+((slot-1)%2)*(cardW+8)
        local cardY=y+math.floor((slot-1)/2)*(self.cardH+8)
        self.slotCards[slot]={x=cardX,y=cardY,w=cardW,h=self.cardH,buttonW=buttonW}
        place(self.slotButtons[slot],cardX+cardW-buttonW-8,cardY+self.fontH+13,buttonW,self.rowH)
    end
    y=y+2*(self.cardH+8)+2
    self.pairTitleY=y;y=y+self.fontH+6
    place(self.targetCombo,8,y,math.max(1,width-side-16),self.rowH)
    place(self.refreshButton,width-side,y,side,self.rowH)
    y=y+self.rowH+6
    local half=math.floor((width-16)/2)
    place(self.pairButton,8,y,math.max(1,half-4),self.rowH)
    place(self.unpairButton,half+12,y,math.max(1,half-4),self.rowH)
    y=y+self.rowH+6
    self.layoutLegacy=self.snapshot and self.snapshot.migrationRequired==true or false
    place(self.legacyButton,8,y,math.max(1,width-8),self.rowH)
    if self.layoutLegacy then y=y+self.rowH+6 end
    -- The two travel notes remain available in the transfer tooltip. Keeping
    -- them out of the main stack leaves all four slots and pair controls in
    -- view at 1366x768 with the larger native Small font.
    local contentHeight=y+6
    self.content:setScrollHeight(contentHeight)
    self.content:setYScroll(math.max(math.min(0,self.content:getYScroll()),
        math.min(0,self.content.height-contentHeight)))
    place(self.teleportButton,16,footerY,self.width-32,self.rowH+10)
    self.reasonY=footerY+self.rowH+16
    self.messageY=self.reasonY+self.fontH+4
end

function Window:onResize()
    local screenW,screenH=getCore():getScreenWidth(),getCore():getScreenHeight()
    local availableW,availableH=math.max(1,screenW-40),math.max(1,screenH-40)
    self.minimumWidth=math.min(640,availableW);self.minimumHeight=math.min(500,availableH)
    ISUIElement.onResize(self)
    if self.width>availableW then self:setWidth(availableW) end
    if self.height>availableH then self:setHeight(availableH) end
    self:setX(math.max(0,math.min(self.x,screenW-self.width)))
    self:setY(math.max(0,math.min(self.y,screenH-self.height)))
    self:layout()
end

function Window:close()
    self:setVisible(false);self:removeFromUIManager()
    if U.instance==self then U.instance=nil end
end

function Window:setResult(ok,code)
    self.message=U.resultText(code or (ok and "ok" or "unknown"));self.messageGood=ok
    self:refresh(false);self:refreshList()
end

function Window:command(command,args)
    if not P.World or not P.World.command then return self:setResult(false,"not_ready") end
    local ok,code=P.World.command(self.player,self.object,command,args or {})
    self:setResult(ok,code)
end

function Window:queueAction(command,args)
    local window=self
    local ok,code=P.Actions.queue(self.player,self.object,command,args,function(success,result)
        if U.instance==window then window:setResult(success,result)
        else window.player:Say(U.resultText(result)) end
    end)
    self:setResult(ok,code)
end

function Window:onRename() self:command("rename",{name=self.nameEntry:getText()}) end
function Window:onRefresh() self:refresh(false);self:refreshList() end
function Window:onUnpair() self:command("unpair") end
function Window:onRecoverLegacy() self:queueAction("recoverLegacy",{}) end
function Window:onPair()
    local id=self.targetCombo:getOptionData(self.targetCombo.selected)
    if not id then return self:setResult(false,"select_target") end
    self:command("pair",{targetId=id})
end

function Window:onBattery(button)
    local slot=button.slot
    local entry=self.snapshot and self.snapshot.slots and self.snapshot.slots[slot]
    if entry and entry.itemId then return self:queueAction("remove",{slot=slot,itemId=entry.itemId}) end
    local batteries=U.collectBatteries(self.player:getInventory())
    if #batteries==0 then return self:setResult(false,"no_battery") end
    local menu=ISContextMenu.get(self.player:getPlayerNum(),getMouseX(),getMouseY())
    for _,battery in ipairs(batteries) do
        menu:addOption(U.batteryLabel(battery),self,function(window,itemId,index)
            window:queueAction("install",{itemId=itemId,slot=index})
        end,battery:getID(),slot)
    end
end

function Window:onTeleport()
    if self.blockReason then return self:setResult(false,self.blockReason) end
    local ok,code=P.Transfer.begin(self.player,self.object)
    self:setResult(ok,code)
    if ok then self:close() end
end

function Window:refreshList()
    if not self.targetCombo then return end
    local selected=self.targetCombo:getOptionData(self.targetCombo.selected)
    self.targetCombo:clear();self.targetCombo:addOptionWithData(text("SelectTarget"),nil)
    local source=self.snapshot and self.snapshot.id
    for _,record in ipairs(P.World and P.World.list and P.World.list() or {}) do
        if record.id~=source then
            local label=text("TargetMenu",record.name or text("Name"),tostring(record.x),tostring(record.y),tostring(record.z))
            if record.pairId then label=label.." "..text("PairedTag") end
            self.targetCombo:addOptionWithData(label,record.id)
            if selected==record.id then self.targetCombo.selected=self.targetCombo:getOptionCount() end
        end
    end
end

function Window:reason(snapshot)
    if not snapshot then return "not_ready" end
    if snapshot.reason then return snapshot.reason end
    if snapshot.migrationRequired then return snapshot.migrationError or "migration_required" end
    if not snapshot.storageReady then return "bridge_missing" end
    if snapshot.pending or P.Transfer.isBusy(self.player) then return "transfer_pending" end
    if P.Actions.isBusy(self.player) then return "player_busy" end
    if self.player:getVehicle() then return "in_vehicle" end
    local square=self.object:getSquare()
    if not square or math.floor(self.player:getZ())~=square:getZ() or
        (self.player:getX()-square:getX())^2+(self.player:getY()-square:getY())^2>9 then return "too_far" end
    if not snapshot.pairId then return "unpaired" end
    if (snapshot.totalCharge or 0)+P.Core.EPSILON<U.transferCost(snapshot) then return "insufficient_charge" end
    if not snapshot.canTeleport then return "not_ready" end
end

function Window:refresh(first)
    if not P.World or not P.World.getSnapshot then return end
    self.snapshot=P.World.getSnapshot(self.object)
    local s=self.snapshot
    if not s then return end
    if first then self.nameEntry:setText(s.name or "") end
    self.blockReason=self:reason(s)
    local busy=s.pending or P.Transfer.isBusy(self.player) or P.Actions.isBusy(self.player)
    local storage=s.storageReady and not s.migrationRequired
    for slot=1,4 do
        local entry=s.slots and s.slots[slot]
        self.slotButtons[slot]:setTitle(text(entry and entry.itemId and "Remove" or "Install"))
        self.slotButtons[slot]:setEnable(not busy and storage)
        if entry and entry.itemId then
            local percent=math.floor(math.max(0,math.min(1,entry.charge or 0))*100+0.5)
            local condition=math.floor((entry.condition or 0)*100/math.max(1,entry.conditionMax or 100)+0.5)
            self.slotButtons[slot].tooltip=text("SlotName",tostring(slot),entry.name or entry.type).."\n"..
                text("BatteryStats",tostring(percent),tostring(condition))
        else self.slotButtons[slot].tooltip=text("SlotVacant") end
    end
    self.renameButton:setEnable(not busy)
    self.pairButton:setEnable(not busy and not s.pairId and storage)
    self.unpairButton:setEnable(not busy and s.pairId~=nil)
    local legacyJava=s.reason=="legacy_java_storage" or s.migrationError=="legacy_java_storage"
    self.legacyButton:setVisible(s.migrationRequired==true)
    self.legacyButton:setTitle(text(legacyJava and "LegacyJavaStorage" or "RecoverLegacy"))
    self.legacyButton:setEnable(not busy and s.migrationRequired==true and not legacyJava)
    self.legacyButton.tooltip=legacyJava and U.resultText("legacy_java_storage") or nil
    if self.layoutLegacy~=(s.migrationRequired==true) then self:layout() end
    self.teleportButton:setEnable(self.blockReason==nil)
    self.teleportButton:setTitle(text("Teleport",string.format("%.2f",U.transferCost(s))))
    self.teleportButton.tooltip=U.reasonText(self.blockReason,s).."\n"..
        text("ReceiverNote",string.format("%.2f",U.transferCost(s))).."\n"..text("ChargeNote")
end

function Window:update()
    ISCollapsableWindow.update(self)
    self.refreshTicks=self.refreshTicks+1
    if self.refreshTicks>=15 then
        self.refreshTicks=0
        if not self.object or not self.object:getSquare() or not self.player or self.player:isDead() then return self:close() end
        self:refresh(false)
    end
end

function Window:renderContent(panel)
    local s=self.snapshot
    if not s then return end
    local width=panel.width-30
    line(panel,text("PortalId",tostring(s.id or "")),8,self.identityY,self.identityW,pale)
    local targetName=text("Unpaired")
    for _,record in ipairs(P.World.list()) do if record.id==s.pairId then targetName=record.name end end
    line(panel,text("Destination",targetName),self.destinationX,self.destinationY,width-self.destinationX,purple)
    local cost=string.format("%.2f",U.transferCost(s))
    local trips=U.tripCount(s)
    line(panel,text("EnergySummary",string.format("%.2f",s.totalCharge or 0),cost,tostring(trips)),8,self.metricsY,width,purple)
    local powerLabel,powered=U.powerText(s)
    local powerColor=powered==nil and pale or (powered and {0.65,0.98,0.75} or {1,0.72,0.45})
    panel:drawRect(4,self.powerY,width+8,self.powerH,0.95,0.11,0.10,0.18)
    panel:drawRectBorder(4,self.powerY,width+8,self.powerH,1,powerColor[1],powerColor[2],powerColor[3])
    line(panel,powerLabel,12,self.connectionY,width-12,powerColor)
    line(panel,text(U.chargingState(s)),12,self.chargingY,width-12,pale)
    local rate=s.chargePerHour or (SandboxVars and SandboxVars.SuQingPortals and SandboxVars.SuQingPortals.ChargePerHour) or 0.5
    line(panel,text("ChargeRate",string.format("%.2f",rate)),12,self.rateY,width-12,pale)
    line(panel,text("BatteryTitle"),8,self.slotsTitleY,width,purple)
    for slot=1,4 do
        local card=self.slotCards[slot]
        panel:drawRect(card.x,card.y,card.w,card.h,0.8,0.12,0.095,0.17)
        panel:drawRectBorder(card.x,card.y,card.w,card.h,0.8,0.38,0.3,0.49)
        local item=s.slots and s.slots[slot]
        local occupied=item and item.itemId~=nil
        line(panel,text("SlotName",tostring(slot),occupied and (item.name or item.type) or text("SlotVacant")),card.x+8,card.y+6,card.w-16,purple)
        if occupied then
            local percent=math.floor(math.max(0,math.min(1,item.charge or 0))*100+0.5)
            local condition=math.floor((item.condition or 0)*100/math.max(1,item.conditionMax or 100)+0.5)
            local statsW=card.w-card.buttonW-28
            line(panel,text("BatteryStats",tostring(percent),tostring(condition)),card.x+8,card.y+self.fontH+13,statsW,pale)
            local barY=card.y+card.h-10
            panel:drawRect(card.x+8,barY,statsW,5,1,0.23,0.18,0.3)
            panel:drawRect(card.x+8,barY,statsW*math.max(0,math.min(1,item.charge or 0)),5,1,0.64,0.48,0.88)
        end
    end
    line(panel,text("PairTitle"),8,self.pairTitleY,width,purple)
end

function Window:render()
    ISCollapsableWindow.render(self)
    local reason=U.reasonText(self.blockReason,self.snapshot)
    line(self,reason,16,self.reasonY,self.width-32,self.blockReason and {1,0.72,0.52} or {0.65,0.94,0.76})
    if self.message~="" then line(self,self.message,16,self.messageY,self.width-32,self.messageGood and {0.65,0.94,0.76} or {1,0.65,0.65}) end
end

function U.open(player,object)
    if U.instance then U.instance:close() end
    local window=Window:new(player,object)
    window:initialise();window:instantiate();window:addToUIManager()
    U.instance=window
    return window
end

return U
