-- HD2-Addon: mods/carpet_bomb_native/core
-- Native CarpetBomb grant experiment. No Eagle entity or payload replacement.
local previous=rawget(_G,'CarpetBombNative')
if previous then return previous end
local S={version='0.1.0',phase='waiting',elapsed=0,owned={},writes=0}
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
local defaults={enabled=1,uses=preset('uses',1),cooldown=preset('cooldown',900)}
local config={};for k,v in pairs(defaults) do config[k]=v end
S.config=config
local last_text
local function read_config()
    local f=io.open(CFG,'rb')
    if not f then
        f=io.open(CFG,'wb')
        if f then f:write('# Native CarpetBomb. Save to reload. manager = deployed dropdown.\n',
          'enabled=1\nuses=manager\ncooldown=manager\n');f:close();f=io.open(CFG,'rb') end
    end
    local text=f and f:read('*a') or '';if f then f:close() end
    if text==last_text then return false end
    local next_config={};for k,v in pairs(defaults) do next_config[k]=v end
    for line in text:gmatch('[^\r\n]+') do
        local key,value=line:match('^%s*([%w_]+)%s*=%s*([%w_%-%.]+)')
        if defaults[key]~=nil and value~='manager' then
            local n=tonumber(value)
            if not n or n%1~=0 or (key=='enabled' and n~=0 and n~=1)
                or (key=='uses' and n~=-1 and (n<1 or n>100))
                or (key=='cooldown' and (n<0 or n>1800)) then
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
local function pack_float(n)return ffi.string(ffi.new('float[1]',n),4)end
local function unhex(s)return(s:gsub('..',function(x)return string.char(tonumber(x,16))end))end
local mbi=ffi.new('uint8_t[48]')
local function writable(p,n)
    if kernel.VirtualQuery(ffi.cast('const void *',p),mbi,48)~=48 then return false end
    local s=ffi.string(mbi,48)
    return u32(s,32)==0x1000 and u32(s,36)==4 and u32(s,40)==0x20000 and p+n<=u64(s,0)+u64(s,24)
end
local function write(p,bytes)
    if not writable(p,#bytes) then return false end
    if kernel.WriteProcessMemory(process,ffi.cast('void *',p),bytes,#bytes,count)==0
        or tonumber(count[0])~=#bytes or read(p,#bytes)~=bytes then return false end
    S.writes=S.writes+1;return true
end
local TABLE=0x37cb600
local ANCHORS={
    {0x6ae4a9,'498b84c700b67c03'},
    {0x6ae4b1,'448b80c8000000'},
    {0x6ae4c3,'4b8b84c700b67c03'},
    {0x8795bc,'8b5f50'},
    {0x87974b,'f30f104068'},
}
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
local function restore()
    local clean=true
    for _,e in ipairs(S.owned) do
        if same_record(e.record) then
            local now=read(e.address,#e.original)
            if now==e.last then if not write(e.address,e.original) then clean=false end
            elseif now~=e.original then clean=false end
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
    local plan={}
    local function add(r,offset,wanted)
        plan[#plan+1]={record=r,address=r.addr+offset,original=r.bytes:sub(offset+1,offset+#wanted),wanted=wanted}
    end
    -- The game's extra-stratagem expansion applies to all existing inventory entries,
    -- including the mandatory Resupply (33). CarpetBomb (103) stays its own native type.
    add(S.carrier,0xc8,active and pack_u32(103) or S.carrier.bytes:sub(0xc9,0xcc))
    add(S.native,0x50,active and pack_u32(config.uses==-1 and 0xffffffff or config.uses) or S.native.bytes:sub(0x51,0x54))
    add(S.native,0x68,active and pack_float(config.cooldown) or S.native.bytes:sub(0x69,0x6c))
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
    S.phase=active and 'active' or 'disabled'
    log(string.format('%s: Resupply (33) additional_stratagem=%d; native CarpetBomb (103), uses=%s, cooldown=%ds; %d fields changed',
        S.phase,active and 103 or 0,config.uses==-1 and 'unlimited' or tostring(config.uses),config.cooldown,#done))
end
local function initialize()
    S.base=check_build();if not S.base then return end
    local carrier=record(33,'AmmoRack','CONSUMABLES. RESUPPLY')
    local native=record(103,'CarpetBomb','MISSIONS CLAN STATION. Carpet Bombing Run')
    if not carrier or not native then return end
    if u32(carrier.bytes,0x3c)~=2 or u32(carrier.bytes,0xc8)~=0 or u32(native.bytes,0x3c)~=0
        or u32(native.bytes,0x70)~=2 or u32(native.bytes,0x94)~=2 or u32(native.bytes,0xcc)~=1
        or u64(native.bytes,0xa0)~=1 or read(u64(native.bytes,0x98),8)~=unhex('c66cef766697cb6c') then
        error('Native/carrier fields differ from verified records')
    end
    S.carrier=carrier;S.native=native;apply()
end
local function tick(dt)
    if S.phase=='stopped' then return end
    S.elapsed=S.elapsed+((type(dt)=='number' and dt>0 and dt<5) and dt or 1/60)
    if S.elapsed<1 then return end;S.elapsed=0
    local changed=read_config()
    if not S.carrier then initialize();return end
    if changed then apply();return end
    if not same_record(S.carrier) or not same_record(S.native) then stop('Record identity changed');return end
    if S.phase=='active' then
        for _,e in ipairs(S.plan) do if read(e.address,#e.wanted)~=e.wanted then stop('Another writer changed a configured field');return end end
    end
end
S.disable=function()config.enabled=0;if S.carrier then apply()end end
read_config();log('Loaded v'..S.version..'; native grant experiment, Bingus Shared Loader v18 / API 1')
local old_update=rawget(_G,'update')
if type(old_update)~='function' then S.phase='stopped';log('Global update callback unavailable');return S end
function update(dt,...)
    local ok,err=pcall(tick,dt);if not ok then stop(tostring(err)) end
    return old_update(dt,...)
end
return S
