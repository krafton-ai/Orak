local dkjson = dofile("Data/Lua/dkjson.lua")

XPOS = XPOS or 1
YPOS = YPOS or 2
ID = ID or 3
UNITTYPE = UNITTYPE or 4
NAME = NAME or 5

-- Backup the original doupdate function
local original_doupdate = doupdate

-- New doupdate function that includes game state saving
function doupdate(...)
    -- Call the original game update logic first
    original_doupdate(...)

    -- Save the game state after all updates have been applied
    save_game_state()
end

function get_game_state()
    local state = {
        level_info = {
            name = generaldata.strings[LEVELNAME],
            id = generaldata.strings[LEVELNUMBER],
            width = roomsizex,
            height = roomsizey
        },
        objects = {}
    }
    
    if units ~= nil then
        for _, unit in ipairs(units) do
            if unit.strings and unit.values then
                table.insert(state.objects, {
                    name = unit.strings[NAME],
                    type = unit.strings[UNITTYPE],
                    position = {
                        x = unit.values[XPOS],
                        y = unit.values[YPOS]
                    }
                })
            end
        end
    end
    
    return state
end

function save_game_state()
    local state = get_game_state()
    if not state or not state.level_info then return end
    
    local state_key = string.format("state_%s", (state.level_info.name or "unknown"):gsub("[%s<>:\"/\\|%?%*]", "_"))
    
    if MF_store then
        MF_setfile("save", state_key .. ".ba")
        MF_store("save", "states", state_key, dkjson.encode(state, {indent = true}))
        timedmessage(string.format("State saved: %s", state_key), 1, 1)
    end
end