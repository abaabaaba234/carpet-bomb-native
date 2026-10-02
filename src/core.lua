-- HD2-Addon: mods/carpet_bomb_native/core
-- Native CarpetBomb grant and missing payload reconstruction.
local previous=rawget(_G,'CarpetBombNative')
if previous then return previous end
local S={version='0.5.1',phase='waiting',elapsed=0,owned={},writes=0,allocations={}}
rawset(_G,'CarpetBombNative',S)
local ffi=require('ffi')
local ROOT=(os.getenv('LOCALAPPDATA') or '')..'\\CowboyBingus\\Helldivers2\\Logs\\'
local LOG=ROOT..'CarpetBombNative.log'
local CFG=ROOT..'CarpetBombNative.cfg'
local first=true
local function log(message)
    S.status=message;pcall(print,'[CarpetBombNative] '..message)
    local f=io.open(LOG,first and 'w' or 'a')
    if f then first=false;f:write(os.date('%H:%M:%S ')..message..'\n');f:close() end
end
local function preset(axis,default)
    local ok,t=pcall(require,'mods/carpet_bomb_native/'..axis)
    return ok and type(t)=='table' and t.value or default
end
log('Loading v'..S.version..' manager presets')
local defaults={enabled=1,uses=preset('uses',2),cooldown=preset('cooldown',15),rearm=preset('rearm',-1),
    bomb=preset('bomb',170),bomb_count=20,forward=preset('forward',80)}
log('Manager presets: uses='..defaults.uses..' call_interval='..defaults.cooldown..' rearm='..defaults.rearm
    ..' projectile='..defaults.bomb..' bombs_per_aircraft='..defaults.bomb_count)
local config={};for k,v in pairs(defaults) do config[k]=v end
S.config=config
local last_text
local function read_config()
    local f=io.open(CFG,'rb')
    if not f then
        f=io.open(CFG,'wb')
        if f then f:write('# Native CarpetBomb. Save to reload. manager = deployed dropdown.\n',
          '# cooldown = interval between uses; rearm = return/reload cooldown for ALL carried Eagles.\n',
          '# rearm=-1 keeps the existing game setting.\n',
          '# bomb=170 (Airstrike), 192 (200 kg), 239 (Eagle 500 kg).\n',
          '# bomb_count is fixed at20; forward=0..300 metres along incoming flight direction.\n',
          'enabled=1\nuses=manager\ncooldown=manager\nrearm=manager\nbomb=manager\nbomb_count=manager\nforward=manager\n');f:close();f=io.open(CFG,'rb') end
    end
    local text=f and f:read('*a') or '';if f then f:close() end
    if text==last_text then return false end
    local next_config={};for k,v in pairs(defaults) do next_config[k]=v end
    for line in text:gmatch('[^\r\n]+') do
        local key,value=line:match('^%s*([%w_]+)%s*=%s*([%w_%-%.]+)')
        if key=='bomb_count' then
            if value~='manager' and value~='20' then log('Quantity override ignored: fixed20; executable patch withdrawn') end
            next_config.bomb_count=20
        elseif defaults[key]~=nil and value~='manager' then
            local n=tonumber(value)
            if not n or n%1~=0 or (key=='enabled' and n~=0 and n~=1)
                or (key=='uses' and n~=-1 and (n<1 or n>100))
                or (key=='cooldown' and (n<0 or n>1800))
                or (key=='rearm' and (n< -1 or n>1800))
                or (key=='bomb' and n~=170 and n~=192 and n~=239)
                or (key=='forward' and (n<0 or n>300)) then
                last_text=text;log('Config rejected: '..key..'='..value);return false
            end
            next_config[key]=n
        end
    end
    for k,v in pairs(next_config) do config[k]=v end;last_text=text;return true
end
local kernel={}
do
    local lib=ffi.load('kernel32')
    for _,d in ipairs({
      {'GetCurrentProcess','void *','(void)'},
      {'GetModuleHandleA','void *','(const char *)'},
      {'ReadProcessMemory','int','(void *, const void *, void *, size_t, size_t *)'},
      {'WriteProcessMemory','int','(void *, void *, const void *, size_t, size_t *)'},
      {'VirtualQuery','size_t','(const void *, void *, size_t)'},
      {'VirtualProtect','int','(void *, size_t, uint32_t, uint32_t *)'},
      {'VirtualAlloc','void *','(void *, size_t, uint32_t, uint32_t)'},
    }) do
        pcall(ffi.cdef,d[2]..' '..d[1]..d[3]..';')
        local ok,fn=pcall(function()return ffi.cast(d[2]..' (*)'..d[3],lib[d[1]])end)
        if not ok then S.phase='stopped';log('Cannot bind '..d[1]);return S end
        kernel[d[1]]=fn
    end
end
local process=kernel.GetCurrentProcess();local buffer=ffi.new('uint8_t[512]');local count=ffi.new('size_t[1]')
local function read(address,n)
    if not address or address<0x10000 or address+n>0x7fffffff0000 or n<1 or n>512 then return nil end
    if kernel.ReadProcessMemory(process,ffi.cast('const void *',address),buffer,n,count)==0 or tonumber(count[0])~=n then return nil end
    return ffi.string(buffer,n)
end
local function u32(s,o)
    local a,b,c,d=s:byte(o+1,o+4);return a and d and a+b*256+c*65536+d*16777216 or nil
end
local function u64(s,o)return u32(s,o)+u32(s,o+4)*4294967296 end
local function ptr(p)local s=read(p,8);return s and u64(s,0) or nil end
local function pack_u32(n)return ffi.string(ffi.new('uint32_t[1]',n),4)end
local function pack_ptr(n)return ffi.string(ffi.new('uint64_t[1]',n),8)end
local function pack_float(n)return ffi.string(ffi.new('float[1]',n),4)end
local function unhex(s)return(s:gsub('..',function(x)return string.char(tonumber(x,16))end))end
local mbi=ffi.new('uint8_t[48]')
local function writable(p,n)
    if kernel.VirtualQuery(ffi.cast('const void *',p),mbi,48)~=48 then return false end
    local s=ffi.string(mbi,48)
    return u32(s,32)==0x1000 and (u32(s,36)==4 or u32(s,36)==2)
        and u32(s,40)==0x20000 and p+n<=u64(s,0)+u64(s,24)
end
local function write(p,bytes)
    if not writable(p,#bytes) then return false end
    local protection=u32(ffi.string(mbi,48),36);local old=ffi.new('uint32_t[1]')
    if protection==2 and kernel.VirtualProtect(ffi.cast('void *',p),#bytes,4,old)==0 then return false end
    local ok=kernel.WriteProcessMemory(process,ffi.cast('void *',p),bytes,#bytes,count)~=0
        and tonumber(count[0])==#bytes and read(p,#bytes)==bytes
    if protection==2 and kernel.VirtualProtect(ffi.cast('void *',p),#bytes,protection,old)==0 then return false end
    if not ok then return false end
    S.writes=S.writes+1;return true
end
local TABLE=0x37cb600
local ANCHORS={
    {0x6ae4a9,'498b84c700b67c03'},
    {0x6ae4b1,'448b80c8000000'},
    {0x6ae4c3,'4b8b84c700b67c03'},
    {0x8795bc,'8b5f50'},
    {0x87974b,'f30f104068'},
    {0x89ee83,'e8b857c7ff0f1000'},
    {0x5146bc,'4869c198000000480540010000'},
    {0x8a4806,'418b4618'},
    {0x8a4d88,'ffc383fb140f82adfdffff'},
    {0x8a4b25,'f3440f1035ae2ab201'},
}
local PROJECTILES={
    [170]={mass=100,impact=194,expire=0,label='Airstrike'},
    [192]={mass=200,impact=182,expire=0,label='CarpetBomb 200 kg'},
    [239]={mass=500,impact=193,expire=277,label='Eagle 500 kg'},
}
local function projectile(t)
    local expected=PROJECTILES[t];local address=ptr(S.base+0x37c7670+t*8)
    local bytes=address and read(address,272)
    if not bytes then return nil end
    if u32(bytes,0)~=t or bytes:sub(0x25,0x28)~=pack_float(expected.mass)
        or bytes:sub(0x81,0x88)~=unhex('36b33606802fe571')
        or u32(bytes,0x90)~=expected.impact or u32(bytes,0x9c)~=expected.expire then
        error('Projectile identity differs: '..t)
    end
    return {type=t,addr=address}
end
local function projectile_intact(t)
    local p=projectile(t);if not p then return false end
    if not S.projectiles[t] then S.projectiles[t]=p end
    return p.addr==S.projectiles[t].addr
end
local function check_build()
    local base=tonumber(ffi.cast('uintptr_t',kernel.GetModuleHandleA('game.dll')))
    if not base or base==0 then return nil end
    local dos=read(base,64)
    if not dos or dos:sub(1,2)~='MZ' then error('Module header differs') end
    local pe=read(base+u32(dos,60),96)
    if not pe or pe:sub(1,4)~='PE\0\0' or u32(pe,8)~=0x6ab3b43f or u32(pe,80)~=0x4744000 then error('Unsupported game build') end
    for _,a in ipairs(ANCHORS) do
        local bytes=unhex(a[2]);if read(base+a[1],#bytes)~=bytes then error(string.format('Code differs at +0x%X',a[1])) end
    end
    return base
end
local function record(t,name,title)
    local p=ptr(S.base+TABLE+t*8);local bytes=p and read(p,0x190)
    if not bytes then return nil end
    local np=ptr(S.base+0x21d4aa0+t*8);local n=read(np,64)
    local text=read(u64(bytes,0x10),128)
    if u32(bytes,0)~=t or not n or n:match('^([^%z]+)')~=name
        or not text or text:match('^([^%z]+)')~=title then error('Stratagem identity differs: '..t) end
    return {type=t,addr=p,bytes=bytes}
end
local function same_record(r)return ptr(S.base+TABLE+r.type*8)==r.addr and read(r.addr,4)==pack_u32(r.type) end
local DATA={ -- Verified current datalibrary headers, capacities and record strides.
    {0xf12478,0xe96bca35,3344,152,76,12}, -- Visibility
    {0xf12490,0x6e8b3849,323136,1122,561,544}, -- Tag
    {0xf124a0,0xfb8d88a3,52000,540,271,160}, -- WeaponMagazine
    {0xf12558,0x7a858691,34592,1080,541,32}, -- LoadoutPackage
    {0xf126d8,0x8a40fe2f,58520,1330,665,56}, -- EncyclopediaEntry
    {0xf12738,0x4437574d,284224,3382,1692,136}, -- Unit
    {0xf12748,0x5653ea91,97304,1056,529,152}, -- Faction
    {0xf127b8,0x604434c9,2713472,1376,688,3912}, -- EffectReference
    {0xf127f0,0x3bf780f6,32320,1010,505,32}, -- Wieldable
    {0xf12968,0x4856d42d,109440,1520,760,112}, -- Animation
    {0xf12b70,0xc4b6b405,99288,126,63,1544}, -- OverlapDamage
    {0xf12b78,0xb3915de3,11108224,1002,502,22096}, -- Health
    {0xf12bd0,0x1f5ab323,14896,438,219,36}, -- WeaponWielder
    {0xf12bd8,0x88e4dbb1,462592,730,366,1232}, -- WeaponData
    {0xf12d50,0x3845b1e0,24744,324,163,120}, -- Mount
    {0xf12e78,0x556ff68b,1992,20,11,152}, -- Eagle
    {0xf12e80,0x45171b68,176224,542,272,616}, -- ProjectileWeapon
    {0xf12ea0,0x80c1ca70,184452,4096,0,32}, -- EntitySettings
}
local DONOR=unhex('29ca6a67b11ca02e');local NATIVE=unhex('c66cef766697cb6c')
local function read_large(p,n)
    local chunks={}
    for offset=0,n-1,512 do
        local bytes=read(p+offset,math.min(512,n-offset));if not bytes then return nil end
        chunks[#chunks+1]=bytes
    end
    return table.concat(chunks)
end
local function hash_slot(hash,capacity)
    local value=ffi.cast('const uint64_t *',hash)[0]
    return tonumber(value%ffi.new('uint64_t',capacity))
end
local function find_slot(index,hash,capacity,stride)
    local start=hash_slot(hash,capacity)
    for step=0,capacity-1 do
        local slot=(start+step)%capacity;local key=index:sub(slot*stride+1,slot*stride+8)
        if key==hash then return slot,true end
        if key==string.rep('\0',8) then return slot,false end
    end
    error('Component hash table is full')
end
local function repair_payload()
    if S.repair then return true end
    local root=ptr(S.base+0x346bf98);if not root or root<0x10000 then return false end
    local plan={};local tables={};local eagle
    -- Every required alias is prepared and checked before any published data is changed.
    for _,d in ipairs(DATA) do
        local slot=root+d[1];local p=ptr(slot);local header=p and read(p-28,28)
        if not header then return false end
        if header:sub(5,8)~='LDLD' or u32(header,0)~=d[2] or u32(header,12)~=d[2]
            or u32(header,8)~=1 or u32(header,16)~=d[3] or u32(header,20)~=1 then error('Payload datalibrary header differs') end
        local stride=d[5]==0 and 32 or 16;local index=read_large(p,d[4]*stride)
        if not index then return false end
        local source,found=find_slot(index,DONOR,d[4],stride)
        if not found then error('Donor payload component missing') end
        local target,exists=find_slot(index,NATIVE,d[4],stride)
        if exists then error('Native payload component already exists; refusing to overwrite') end
        local original=index:sub(target*stride+1,(target+1)*stride)
        local donor=index:sub(source*stride+1,(source+1)*stride)
        if d[5]>0 and u32(donor,8)>=d[5] then error('Donor component index differs') end
        tables[#tables+1]={slot=slot,original=p}
        if d[1]==0xf12e78 then
            local bytes=read_large(p,d[3]);local ri=u32(donor,8)
            local row=bytes:sub(d[4]*16+ri*152+1,d[4]*16+(ri+1)*152)
            if u32(row,16)~=5 or u32(row,20)~=0 or u32(row,24)~=170 then error('Eagle donor differs') end
            local native=row:sub(1,16)..pack_u32(6)..row:sub(21)
            -- CarpetBomb predicts a horizontal release. The Airstrike donor approaches
            -- from 1000 m and starts within that range, causing immediate, distant drops.
            -- Use a low approach for this private record so the plane enters release range.
            native=native:sub(1,0x3c)..pack_float(120)..native:sub(0x41)
            -- Extra record 11 keeps the native bombing mode and vanilla rows intact.
            local shadow=bytes:sub(1,target*16)..NATIVE..pack_u32(11)..donor:sub(13,16)..bytes:sub(target*16+17)..native
            local allocation=tonumber(ffi.cast('uintptr_t',kernel.VirtualAlloc(nil,#shadow+28,0x3000,4)))
            if not allocation or allocation<0x10000 then error('Payload allocation failed') end
            S.allocations[#S.allocations+1]=allocation
            local h=header:sub(1,16)..pack_u32(#shadow)..header:sub(21)
            local complete=h..shadow
            for o=0,#complete-1,512 do if not write(allocation+o,complete:sub(o+1,o+512)) then error('Private payload copy failed') end end
            eagle={slot=slot,address=slot,original=pack_ptr(p),wanted=pack_ptr(allocation+28),table=allocation+28}
        else
            if d[5]==0 and (u64(donor,16)~=22 or u32(donor,24)~=3547464239) then error('Eagle entity component list differs') end
            plan[#plan+1]={address=p+target*stride,original=original,wanted=NATIVE..donor:sub(9)}
        end
    end
    plan[#plan+1]=eagle
    for _,e in ipairs(plan) do if read(e.address,#e.original)~=e.original or not writable(e.address,#e.wanted) then error('Payload alias conflict or non-writable data') end end
    if ptr(S.base+0x346bf98)~=root then error('Payload root changed before publication') end
    for _,t in ipairs(tables) do if ptr(t.slot)~=t.original then error('Payload table changed before publication') end end
    local done={}
    for _,e in ipairs(plan) do
        done[#done+1]=e
        if not write(e.address,e.wanted) then
            for i=#done,1,-1 do local d=done[i];write(d.address,d.original) end
            error('Payload publication failed; rolled back')
        end
    end
    S.repair={root=root,plan=plan,tables=tables,eagle=eagle}
    log('Missing native payload reconstructed: 17 component/entity aliases; private Eagle payload 6, approach height 120 m; vanilla Eagles preserved')
    return true
end
local function repair_intact()
    local r=S.repair;if not r then return true end
    if ptr(S.base+0x346bf98)~=r.root then return false end
    for _,t in ipairs(r.tables) do
        local expected=t.slot==r.eagle.slot and u64(r.eagle.wanted,0) or t.original
        if ptr(t.slot)~=expected then return false end
    end
    for _,e in ipairs(r.plan) do if read(e.address,#e.wanted)~=e.wanted then return false end end
    return true
end
local function restore()
    local clean=true
    for i=#S.owned,1,-1 do
        local e=S.owned[i]
        if same_record(e.record) then
            local now=read(e.address,#e.original)
            if now==e.last then if not write(e.address,e.original) then clean=false end
            elseif now~=e.original then clean=false end
        else clean=false
        end
    end
    S.owned={};return clean
end
local function stop(reason)
    local clean=restore();S.phase='stopped';log('STOPPED: '..reason..(clean and '; restored owned fields' or '; some fields could not be restored'))
end
local function apply()
    if not same_record(S.carrier) or not same_record(S.native) then stop('Stratagem table changed');return end
    local active=config.enabled==1
    local custom_rearm=active and config.rearm>=0
    if (custom_rearm or S.rearm_owned) and not same_record(S.rearm) then stop('Eagle rearm record changed');return end
    if active and not repair_payload() then return end
    if active and not repair_intact() then stop('Payload alias identity changed');return end
    if active and not projectile_intact(config.bomb) then stop('Selected projectile record changed');return end
    if active and config.bomb==239 and not same_record(S.heavy) then stop('Eagle 500 kg resource package changed');return end
    local plan={}
    local function add(r,offset,wanted)
        plan[#plan+1]={record=r,address=r.addr+offset,original=r.bytes:sub(offset+1,offset+#wanted),wanted=wanted}
    end
    -- The game's extra-stratagem expansion applies to all existing inventory entries,
    -- including the mandatory Resupply (33). CarpetBomb (103) stays its own native type.
    add(S.native,0x50,active and pack_u32(config.uses==-1 and 0xffffffff or config.uses) or S.native.bytes:sub(0x51,0x54))
    add(S.native,0x68,active and pack_float(config.cooldown) or S.native.bytes:sub(0x69,0x6c))
    for _,field in ipairs({{0x70,4},{0x94,4},{0xc8,4},{0x104,4}}) do
        local offset,n=field[1],field[2]
        add(S.native,offset,active and S.donor.bytes:sub(offset+1,offset+n) or S.native.bytes:sub(offset+1,offset+n))
    end
    -- 200 kg uses the same bomb unit and impact effect already in Airstrike's
    -- package. 500 kg uses EagleBomb's package, including its delayed explosion.
    local package=active and (config.bomb==239 and S.heavy or S.donor).bytes:sub(0xa9,0xb0)
        or S.native.bytes:sub(0xa9,0xb0)
    add(S.native,0xa8,package)
    if S.repair then
        plan[#plan+1]={record=S.native,address=S.repair.eagle.table+1992+0x18,
            original=pack_u32(170),wanted=pack_u32(active and config.bomb or 170)}
    end
    -- Type 49 is shared by every carried Eagle. The vanilla choice neither
    -- writes nor monitors this field unless returning a value we previously owned.
    if custom_rearm or S.rearm_owned then
        add(S.rearm,0x68,custom_rearm and pack_float(config.rearm) or S.rearm.bytes:sub(0x69,0x6c))
    end
    -- Publish automatic carrying last, after the native payload and transport are valid.
    add(S.carrier,0xc8,active and pack_u32(103) or S.carrier.bytes:sub(0xc9,0xcc))
    local previous={};for _,e in ipairs(S.owned) do previous[e.address]=e end
    for _,e in ipairs(plan) do
        local old=previous[e.address];e.before=read(e.address,#e.wanted)
        if not e.before or (e.before~=e.original and (not old or e.before~=old.last))
            or (e.before~=e.wanted and not writable(e.address,#e.wanted)) then stop('Field conflict or non-writable data');return end
    end
    local done={}
    for _,e in ipairs(plan) do
        if e.before~=e.wanted then
            done[#done+1]=e
            if not write(e.address,e.wanted) then
                for i=#done,1,-1 do local d=done[i];write(d.address,d.before) end
                stop('Write failed; transaction rolled back');return
            end
        end
    end
    S.owned={};S.plan=plan
    for _,e in ipairs(plan) do e.last=e.wanted;if e.last~=e.original then S.owned[#S.owned+1]=e end end
    S.rearm_owned=custom_rearm
    if not custom_rearm then
        -- After restoring the rearm value, relinquish it so other mods can own it.
        local watched={};for _,e in ipairs(plan) do
            if e.record~=S.rearm then watched[#watched+1]=e end
        end
        S.plan=watched
    end
    S.phase=active and 'active' or 'disabled'
    log(string.format('%s: Resupply (33) additional_stratagem=%d; native CarpetBomb (103), uses=%s, call_interval=%ds, rearm=%s; projectile=%d (%s), bombs_per_aircraft=%d (%.2fx), forward=%dm; %d fields changed',
        S.phase,active and 103 or 0,config.uses==-1 and 'unlimited' or tostring(config.uses),config.cooldown,
        custom_rearm and (config.rearm..'s (all carried Eagles)') or 'unchanged',
        active and config.bomb or 170,PROJECTILES[active and config.bomb or 170].label,
        active and config.bomb_count or 20,(active and config.bomb_count or 20)/20,config.forward,#done))
end
local function vector(bytes,offset)
    local values=ffi.new('float[3]');ffi.copy(values,bytes:sub(offset+1,offset+12),12)
    local out={tonumber(values[0]),tonumber(values[1]),tonumber(values[2])}
    for _,v in ipairs(out) do if v~=v or math.abs(v)>10000000 then return nil end end
    return out
end
local function shift_incoming_targets(dt)
    if S.phase~='active' or S.forward_fault then return end
    S.forward_elapsed=(S.forward_elapsed or 0)+((type(dt)=='number' and dt>0 and dt<5) and dt or 1/60)
    if S.forward_elapsed<0.1 then return end;S.forward_elapsed=0
    local manager=ptr(S.base+0x3326650)
    local header=manager and read(manager,0x60);if not header then return end
    local n=u32(header,0x20);if n==0 then S.forward_seen={};return end
    if n>64 then error('Eagle state count differs; forward adjustment disabled') end
    local objects,states=u64(header,0x48),u64(header,0x58)
    if objects<0x10000 or states<0x10000 then return end
    local previous=S.forward_seen or {};local present={}
    for i=0,n-1 do
        local descriptor=ptr(objects+i*8);local identity=descriptor and read(descriptor,16)
        if identity and identity:sub(1,8)==NATIVE then
            local key=tostring(descriptor)..':'..u32(identity,8)..':'..u32(identity,12)
            present[key]=previous[key]
            if not present[key] then
                local address=states+i*0xfc;local state=read(address,0xfc)
                if state then
                    if config.forward==0 or state:byte(0x71)~=0 or state:byte(0x72)~=0 then
                        present[key]=true
                    else
                        local target,current,velocity=vector(state,0x54),vector(state,0x78),vector(state,0xd4)
                        if target and current and velocity then
                            local dx,dy=target[1]-current[1],target[2]-current[2]
                            local distance=math.sqrt(dx*dx+dy*dy)
                            local vx,vy=velocity[1],velocity[2];local speed=math.sqrt(vx*vx+vy*vy)
                            if distance>=50 and (speed<=1 or vx*dx+vy*dy>0) then
                                if speed>1 then dx,dy,distance=vx,vy,speed end
                                local x=target[1]+dx/distance*config.forward
                                local y=target[2]+dy/distance*config.forward
                                local before=state:sub(0x55,0x5c);local wanted=pack_float(x)..pack_float(y)
                                -- Recheck the native descriptor and current state allocation.
                                -- Only its horizontal target moves; beacon and altitude stay intact.
                                if read(descriptor,16)==identity and ptr(manager+0x48)==objects
                                    and ptr(manager+0x58)==states and read(address+0x54,8)==before then
                                    if not write(address+0x54,wanted) then
                                        if read(descriptor,16)==identity and ptr(manager+0x58)==states then write(address+0x54,before) end
                                        error('Forward target write failed; target restoration attempted')
                                    end
                                    present[key]=true;S.forward_adjustments=(S.forward_adjustments or 0)+1
                                    log(string.format('Forward strike shift: entity=%d, %dm, target=(%.1f, %.1f, %.1f) -> (%.1f, %.1f, %.1f)',
                                        u32(identity,8),config.forward,target[1],target[2],target[3],x,y,target[3]))
                                end
                            end
                        end
                    end
                end
            end
        end
    end
    S.forward_seen=present
end
local function initialize()
    S.base=check_build();if not S.base then return end
    local carrier=record(33,'AmmoRack','CONSUMABLES. RESUPPLY')
    local native=record(103,'CarpetBomb','MISSIONS CLAN STATION. Carpet Bombing Run')
    local donor=record(18,'EagleAirstrike','EAGLE. AIRSTRIKE')
    local rearm=record(49,'EagleRearm','EAGLE. REARM')
    local heavy=record(3,'EagleBomb','EAGLE. 500KG BOMB')
    if not carrier or not native or not donor or not rearm or not heavy then return end
    local projectiles={}
    projectiles[config.bomb]=projectile(config.bomb);if not projectiles[config.bomb] then return end
    if heavy.bytes:sub(0xa9,0xb0)~=unhex('5abda258703bc39b') then error('Eagle 500 kg package differs') end
    if u32(rearm.bytes,0x3c)~=7 then error('Eagle rearm category differs') end
    if u32(carrier.bytes,0x3c)~=2 or u32(carrier.bytes,0xc8)~=0 or u32(native.bytes,0x3c)~=0
        or u32(native.bytes,0x70)~=2 or u32(native.bytes,0x94)~=2 or u32(native.bytes,0xcc)~=1
        or u64(native.bytes,0xa0)~=1 or read(u64(native.bytes,0x98),8)~=unhex('c66cef766697cb6c') then
        error('Native/carrier fields differ from verified records')
    end
    if u32(donor.bytes,0x70)~=0 or u32(donor.bytes,0x94)~=0 or u32(donor.bytes,0xc8)~=49
        or donor.bytes:sub(0xa9,0xb0)~=unhex('f338ff0016cc331e') or u32(donor.bytes,0x104)~=0x1084 then error('Eagle transport settings differ') end
    S.carrier=carrier;S.native=native;S.donor=donor;S.rearm=rearm;S.heavy=heavy;S.projectiles=projectiles;apply()
end
local function tick(dt)
    if S.phase=='stopped' then return end
    S.elapsed=S.elapsed+((type(dt)=='number' and dt>0 and dt<5) and dt or 1/60)
    if S.elapsed<1 then return end;S.elapsed=0
    local changed=read_config()
    if not S.carrier then initialize();return end
    if changed or S.phase=='waiting' then apply();return end
    if not same_record(S.carrier) or not same_record(S.native) then stop('Record identity changed');return end
    if S.rearm_owned and not same_record(S.rearm) then stop('Eagle rearm record identity changed');return end
    if S.phase=='active' then
        if not repair_intact() then stop('Payload aliases changed');return end
        if not projectile_intact(config.bomb) then stop('Projectile table changed');return end
        for _,e in ipairs(S.plan) do
            if read(e.address,#e.wanted)~=e.wanted then stop('Another writer changed a configured field');return end
        end
    end
end
S.disable=function()config.enabled=0;if S.carrier then apply()end end
read_config();log('Loaded v'..S.version..'; native grant experiment, Bingus Shared Loader v18 / API 1')
local old_update=rawget(_G,'update')
if type(old_update)~='function' then S.phase='stopped';log('Global update callback unavailable');return S end
function update(dt,...)
    local ok,err=pcall(tick,dt);if not ok then stop(tostring(err)) end
    local shifted,shift_error=pcall(shift_incoming_targets,dt)
    if not shifted then S.forward_fault=true;log('Forward adjustment stopped: '..tostring(shift_error)) end
    return old_update(dt,...)
end
return S
