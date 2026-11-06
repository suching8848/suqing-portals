-- Generated from the current installed native Lua. No game execution.
ISInventoryPaneContextMenu.getContainers = function(character)
    if not character then return end
    local playerNum = character and character:getPlayerNum() or -1;
    -- get all the surrounding inventory of the player, gonna check for the item in them too
    local containerList = ArrayList.new();
    for i,v in ipairs(getPlayerInventory(playerNum).inventoryPane.inventoryPage.backpacks) do
        containerList:add(v.inventory);
    end
    for i,v in ipairs(getPlayerLoot(playerNum).inventoryPane.inventoryPage.backpacks) do
        local parent = v.inventory:getParent()
        if instanceof(parent, "IsoThumpable") then
            if not parent:isLockedToCharacter(character) then
                containerList:add(v.inventory);
            end
        else
            containerList:add(v.inventory);
        end
    end
    return containerList;
end

function ISInventoryPage:selectContainer(button)
	local playerObj = getSpecificPlayer(self.player)

    if button.inventory ~= self.inventoryPane.lastinventory then
        if self.mouseOverColoredContainer then
            self:stopHighlightContainer(self.mouseOverColoredContainer);
        end
        self.mouseOverColoredContainer = nil;
        local object = button.inventory and button.inventory:getParent() or nil
        if instanceof(object, "IsoThumpable") and object:isLockedToCharacter(playerObj) then
            return
        end
        self:playContainerOpenCloseSounds(button)
    end

    self.inventoryPane.lastinventory = button.inventory;
    self.inventoryPane.inventory = button.inventory;
    self.inventoryPane.selected = {}
    if not button.inventory:isExplored() then
        if not isClient() then
			ItemPicker.fillContainer(button.inventory, playerObj);
        else
            button.inventory:requestServerItemsForContainer();
        end
        button.inventory:setExplored(true);
    end

	self.title = button.name;

	self.capacity = button.capacity;

    self:refreshBackpacks();
end

function ISInventoryPage:setNewContainer(inventory)
    self.inventoryPane.inventory = inventory;
    self.inventory = inventory;
    self.inventoryPane:refreshContainer();

    local playerObj = getSpecificPlayer(self.player)
    self.capacity = inventory:getEffectiveCapacity(playerObj);

    -- highlight the container if it is in the list
	for i,containerButton in ipairs(self.backpacks) do
		if containerButton.inventory == inventory then
			containerButton:setBackgroundRGBA(0.7, 0.7, 0.7, 1.0)
			self.title = containerButton.name;
            self:playContainerOpenCloseSounds(containerButton)
            self.inventoryPane.lastinventory = inventory;
		else
			containerButton:setBackgroundRGBA(0.0, 0.0, 0.0, 0.0)
		end
	end
end

function ISInventoryTransferAction:isValid()
	if not self.item then
		return false;
	end
	if not self.destContainer or not self.srcContainer then
		return false;
    end
    if self.isTransferIntoVehicleSeatFromOutside then
        -- fix for players being able to replace items into containers they shouldn't
        local containers = ISInventoryPaneContextMenu.getContainers(self.character)
        if not containers:contains(self.destContainer) then
            return false;
        end
        -- fix for players being able to add ingredients to evolved recipes after walking away from the container they are in
        -- Items can be taken from bags inside bags in the player's inventory.
        -- This isn't done for bags inside bags in object containers.
        -- Bags in vehicle containers and on seats work, since those are displayed in the loot window.
        if not containers:contains(self.srcContainer) and self.srcContainer:getOutermostContainer() ~= self.character:getInventory() then
            return false;
        end
    end
	-- fix for items that were consumed in crafting still being put back into their container
	if self.item:getIsCraftingConsumed() then
		return false;
	end
	self.dontAdd = false;

    if not self.srcContainer:contains(self.item) then
        self.dontAdd = true;
        return true;
    end

	-- Limit items per container in MP
	if isClient() then
		local tradingUI = ISTradingUI.GetUIForPlayer(self.character)
		if tradingUI and tradingUI:isVisible() then
			return false;
		end
		if not self.started and not isItemTransactionConsistent(self.item, self.srcContainer, self.destContainer, nil, self.character) then
			return false
		end
		local limit = getServerOptions():getInteger("ItemNumbersLimitPerContainer");
		if limit > 0 and (not instanceof(self.destContainer:getParent(), "IsoGameCharacter")) then
			--allow dropping full bags on an empty square or put full container in an empty container
			if not self.destContainer:getItems():isEmpty() then
				local destRoot = luautils.findRootInventory(self.destContainer);
				local srcRoot = luautils.findRootInventory(self.srcContainer);
				--total count remains the same if the same root container
				if srcRoot ~= destRoot then
					local transferItemsNum = 1;
					if self.item:getCategory() == "Container" then
						transferItemsNum = luautils.countItemsRecursive({self.item:getInventory()}, 1);
					end;
					--count items from the root container
					local destContainerItemsNum = luautils.countItemsRecursive({destRoot}, 0);
					--if destination is an item then add 1
					if destRoot:getContainingItem() then destContainerItemsNum = destContainerItemsNum + 1; end;
					--total items must not exceed the server limit
					if destContainerItemsNum + transferItemsNum > limit then
						return false;
					end;
				end;
			end;
		end;
		return true;
	end;

	if (not self.destContainer:isExistYet()) or (not self.srcContainer:isExistYet()) then
		return false
	end

	local parent = self.srcContainer:getParent()
	-- Duplication exploit: drag items from a corpse to another container while pickup up the corpse.
	-- ItemContainer:isExistYet() would detect this if SystemDisabler.doWorldSyncEnable was true.
	if instanceof(parent, "IsoDeadBody") and parent:getStaticMovingObjectIndex() == -1 then
		return false
	end

	-- Don't fail if the item was transferred by a previous action.
	if self:isAlreadyTransferred(self.item) then
		return true
	end

	if not self.srcContainer:contains(self.item) then
		return false;
    end
    if self.srcContainer == self.destContainer then return false; end

    if self.destContainer:getType()=="floor" then
		--[[
        if instanceof(self.item, "Moveable") and self.item:getSpriteGrid()==nil then
            if not self.item:CanBeDroppedOnFloor() then
                return false;
            end
        end
        ]]--
        if self:getNotFullFloorSquare(self.item) == nil then
            return false;
        end
    elseif not self.destContainer:hasRoomFor(self.character, self.item) then
        return false;
    end

    if not self.srcContainer:isRemoveItemAllowed(self.item) then
        return false;
    end
    if not self.destContainer:isItemAllowed(self.item) then
        return false;
    end
    if self.item:getContainer() == self.srcContainer and not self.destContainer:isInside(self.item) then
        return true;
    end
    if isClient() and self.srcContainer:getSourceGrid() and SafeHouse.isSafeHouse(self.srcContainer:getSourceGrid(), self.character:getUsername(), true) then
        return false;
	end
    return false;
end

function ISInventoryTransferAction:transferItem(item)
	if self:isAlreadyTransferred(item) then
		return
	end
	
	if self.dontAdd then
		-- Crafting ingredient was destroyed and can't be put back into the container it came from.
		return
	end

--	print("transfering ", item)
	self.item = item;
	--self.character:ClearVariable("LootPosition");
	self.item:setJobDelta(0.0);
	if self.item:isFavorite() and not self.destContainer:isInCharacterInventory(self.character) then
--		ISBaseTimedAction.perform(self);
		return;
	end

	local square = self:getNotFullFloorSquare(item)
	self.item = ISTransferAction:transferItem(self.character, self.item, self.srcContainer, self.destContainer, square)

	-- clear it from the queue.
	self.srcContainer:setDrawDirty(true);
	self.srcContainer:setHasBeenLooted(true);
	self.destContainer:setDrawDirty(true);

	if instanceof(self.srcContainer:getParent(), "IsoDeadBody") then
		self.item:setAttachedSlot(-1);
		self.item:setAttachedSlotType(nil);
		self.item:setAttachedToModel(nil);
	end

	if instanceof(self.destContainer:getParent(), 'IsoMannequin') then
		local mannequin = self.destContainer:getParent()
		mannequin:wearItem(self.item, self.character)
	end
	
	-- Hack for giving cooking XP.
	if instanceof(self.item, "Food") then
		self.item:setChef(self.character:getFullName())
	end
	if self.destContainer:getType() == "stonefurnace" then
		self.item:setWorker(self.character:getFullName());
	end

	ISInventoryPage.renderDirty = true

	-- do the overlay sprite
    if self.srcContainer:getParent() and self.srcContainer:getParent():getOverlaySprite() then
        ItemPicker.updateOverlaySprite(self.srcContainer:getParent())
    end
    if self.destContainer:getParent() then
        ItemPicker.updateOverlaySprite(self.destContainer:getParent())
    end

    if not isServer() then
        self:playTransferCompleteSound(item)
    end
end

function ISInventoryTransferAction:setOnComplete(func, arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8)
	self.onCompleteFunc = func
	self.onCompleteArgs = { arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8 }
end

function ISInventoryTransferAction:getTimeDelta()
	return 0;
end

function TEST.nativeFinishRefresh(self, oldNumBackpacks)
local playerObj=getSpecificPlayer(self.player)
local floorContainer=ISInventoryPage.GetFloorContainer(self.player)
	triggerEvent("OnRefreshInventoryWindowContainers", self, "buttonsAdded")

	local found = false
	local foundIndex = -1
	for index,containerButton in ipairs(self.backpacks) do
		if containerButton.inventory == self.inventoryPane.inventory then
			foundIndex = index
			found = true
			break
		end
	end

    for _, button in ipairs(self.buttonPool) do
        if self.mouseOverColoredContainer and self:getContainerParent(button.inventory) == self.mouseOverColoredContainer then
            self:stopHighlightContainer(self.mouseOverColoredContainer);
            self.mouseOverColoredContainer = nil;
            break;
        end
    end

	self.inventoryPane.inventory = self.inventoryPane.lastinventory
	self.inventory = self.inventoryPane.inventory
	if self.backpackChoice ~= nil and playerObj:getJoypadBind() ~= -1 then
		if not self.onCharacter and oldNumBackpacks == 1 and #self.backpacks > 1 then
			self.backpackChoice = 1
		end
		if self.backpackChoice > #self.backpacks then
			self.backpackChoice = 1
		end
		if self.backpacks[self.backpackChoice] ~= nil then
			self.inventoryPane.inventory = self.backpacks[self.backpackChoice].inventory
			self.capacity = self.backpacks[self.backpackChoice].capacity
		end
	else
		if not self.onCharacter and oldNumBackpacks == 1 and #self.backpacks > 1 then
			self.inventoryPane.inventory = self.backpacks[1].inventory
			self.capacity = self.backpacks[1].capacity
		elseif found then
			self.inventoryPane.inventory = self.backpacks[foundIndex].inventory
			self.capacity = self.backpacks[foundIndex].capacity
		elseif not found and #self.backpacks > 0 then
			if self.backpacks[1] and self.backpacks[1].inventory and (not self.backpacks[1].inventory:isLockedToCharacter(playerObj)) then
				self.inventoryPane.inventory = self.backpacks[1].inventory
				self.capacity = self.backpacks[1].capacity
            else
                self.inventoryPane.inventory = floorContainer
                self.capacity = floorContainer:getMaxWeight()
			end
		elseif self.inventoryPane.lastinventory ~= nil then
			self.inventoryPane.inventory = self.inventoryPane.lastinventory
		end
	end

	-- ISInventoryTransferAction sometimes turns the player to face a container.
	-- Which container is selected changes as the player changes direction.
	-- Although ISInventoryTransferAction forces a container to be selected,
	-- sometimes the action completes before the player finishes turning.
	if self.forceSelectedContainer then
		if self.forceSelectedContainerTime > getTimestampMs() then
			for _,containerButton in ipairs(self.backpacks) do
				if containerButton.inventory == self.forceSelectedContainer then
					self.inventoryPane.inventory = containerButton.inventory
					self.capacity = containerButton.capacity
					break
				end
			end
		else
			self.forceSelectedContainer = nil
		end
	end

	self.inventoryPane:bringToTop()
	self.resizeWidget2:bringToTop()
	self.resizeWidget:bringToTop()

	self.inventory = self.inventoryPane.inventory

	self.title = nil
	for k,containerButton in ipairs(self.backpacks) do
		if containerButton.inventory == self.inventory then
            self.selectedButton = containerButton;
			containerButton:setBackgroundRGBA(0.7, 0.7, 0.7, 1.0)
			self.title = containerButton.name
		else
			containerButton:setBackgroundRGBA(0.0, 0.0, 0.0, 0.0)
		end
	end

	if self.inventoryPane ~= nil then
		self.inventoryPane:refreshContainer()
	end

	self:refreshWeight()

	self:updateItemCount()

	if self.controlsUI then
        self.controlsUI:arrange()
        self.inventoryPane:setHeight(self.height - self.inventoryPane.y - self.resizeWidget.height - self.controlsUI.height)
    end
    self.containerButtonPanel:setHeight(self.inventoryPane.height)
    self.containerButtonPanel:setY(self.inventoryPane.y)
    self.containerButtonPanel:setScrollHeight(self.backpacks[#self.backpacks]:getBottom())

	triggerEvent("OnRefreshInventoryWindowContainers", self, "end")
end

function ISTransferAction:transferItem(character, item, srcContainer, destContainer, dropSquare)

	if destContainer:getType() ~= "TradeUI" then
		srcContainer:DoRemoveItem(item);
		if isServer() then
			sendRemoveItemFromContainer(srcContainer, item)
		end
	end

	-- deal with containers that are floor
	if destContainer:getType() == "floor" then
		if dropSquare then
			local addToWorld = ISTransferAction:removeItemOnCharacter(character, item)
			-- might have been added by the masking system (if you have a bag equipped and drop it on ground for example)
			if addToWorld then
				destContainer:DoAddItemBlind(item)
				local dropX,dropY,dropZ = ISTransferAction.GetDropItemOffset(character, dropSquare, item)
				dropSquare:AddWorldInventoryItem(item, dropX, dropY, dropZ)
				if instanceof(item, "Radio") then
					local _obj = IsoRadio.new(getCell(), dropSquare, nil)
					local deviceData = item:getDeviceData()
					if deviceData then
						_obj:setDeviceData(deviceData)
					end
					_obj:getModData().RadioItemID = item:getID()
					dropSquare:AddSpecialObject(_obj, dropSquare:getObjects():size())
					_obj:transmitCompleteItemToClients()
					_obj:transmitModData()
					triggerEvent("OnObjectAdded", _obj)
					dropSquare:RecalcProperties()
					dropSquare:RecalcAllWithNeighbours(true)
				end
			end
		else
			error "no square to drop item on"
		end
	elseif srcContainer:getType() == "floor" and item:getWorldItem() ~= nil then
		DesignationZoneAnimal.removeItemFromGround(item:getWorldItem())
		if instanceof(item, "Radio") then
			local grabSquare = item:getWorldItem():getSquare()
			local _obj = nil
			for i=0, grabSquare:getObjects():size()-1 do
				local tObj = grabSquare:getObjects():get(i)
				if instanceof(tObj, "IsoRadio") then
					if tObj:getModData().RadioItemID == item:getID() then
						_obj = tObj
						break
					end
				end
			end
			if _obj ~= nil then
				local deviceData = _obj:getDeviceData()
				if deviceData then
					item:setDeviceData(deviceData)
				end
				grabSquare:transmitRemoveItemFromSquare(_obj)
				grabSquare:RecalcProperties()
				grabSquare:RecalcAllWithNeighbours(true)
			end
		end

		item:getWorldItem():getSquare():transmitRemoveItemFromSquare(item:getWorldItem())
		item:getWorldItem():getSquare():removeWorldObject(item:getWorldItem())
		--item:getWorldItem():getSquare():getObjects():remove(item:getWorldItem())
		item:setWorldItem(nil)
		destContainer:AddItem(item)
	else
		if srcContainer:getType() ~= "TradeUI" then
			destContainer:AddItem(item)
		end
		if character:getInventory() ~= destContainer then
			ISTransferAction:removeItemOnCharacter(character, item)
		end
		if item:getType() == "CandleLit" then
			local candle = destContainer:AddItem("Base.Candle")
			candle:setUsedDelta(item:getCurrentUsesFloat())
			candle:setCondition(item:getCondition())
			candle:setFavorite(item:isFavorite())
			destContainer:Remove(item)
			item = candle
		end
        if item:getType() == "Lantern_HurricaneLit" then
            local candle = destContainer:AddItem("Base.Lantern_Hurricane");
            candle:setUsedDelta(self.item:getCurrentUsesFloat());
            candle:setCondition(self.item:getCondition());
            candle:setFavorite(self.item:isFavorite());
            destContainer:Remove(self.item)
            item = candle;
        end
	end

	if destContainer:getParent() and instanceof(destContainer:getParent(), "BaseVehicle") and destContainer:getParent():getPartById(destContainer:getType()) then
		local part = destContainer:getParent():getPartById(destContainer:getType())
		part:setContainerContentAmount(part:getItemContainer():getCapacityWeight())
	end

	if srcContainer:getParent() and instanceof(srcContainer:getParent(), "BaseVehicle") and srcContainer:getParent():getPartById(srcContainer:getType()) then
		local part = srcContainer:getParent():getPartById(srcContainer:getType())
		part:setContainerContentAmount(part:getItemContainer():getCapacityWeight())
	end

	return item
end

function TEST.nativeCleanUIPosition(self,index)
    local columns = math.max(1, tonumber(self.containerButtonColumns) or self:cleanUIUpdateContainerPanelMetrics())
    local zeroIndex = math.max(0, (tonumber(index) or 1) - 1)
    local column = zeroIndex % columns
    local row = math.floor(zeroIndex / columns)
    local x = self.padding + column * (self.buttonSize + self.padding)
    local y = self.padding + row * (self.buttonSize + self.padding)
    return x, y
end

TEST.nativeGetContainers=ISInventoryPaneContextMenu.getContainers
