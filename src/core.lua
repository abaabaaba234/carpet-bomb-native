-- HD2-Addon: mods/carpet_bomb_native/core
-- Native CarpetBomb grant and missing payload reconstruction.
local previous=rawget(_G,'CarpetBombNative')
if previous then return previous end
local S={version='0.5.1-menu-perf2',phase='waiting',elapsed=0,owned={},writes=0,allocations={},projectiles={},
    recovery={},protection_pending={},cleanup_attempts=0}
rawset(_G,'CarpetBombNative',S)
local ffi=require('ffi')
local ROOT=(os.getenv('LOCALAPPDATA') or '')..'\\CowboyBingus\\Helldivers2\\Logs\\'
local LOG=ROOT..'CarpetBombNative.log'
local CFG=ROOT..'CarpetBombNative.cfg'
local kernel={}
local first=true
local function log(message)
    S.status=message;pcall(print,'[CarpetBombNative] '..message)
    local f=io.open(LOG,first and 'w' or 'a')
    if f then first=false;f:write(os.date('%H:%M:%S ')..message..'\n');f:close() end
end
local SCHEMA={
    language={default='zh',choices={zh=true,en=true}},
    enabled={default=1,min=0,max=1},
    uses={default=2,min=1,max=100,sentinel=-1,manager=true},
    cooldown={default=15,min=0,max=1800,manager=true},
    rearm={default=-1,min=0,max=1800,sentinel=-1,manager=true},
    bomb={default=170,choices={[170]=true,[192]=true,[239]=true},manager=true},
    bomb_count={default=20,min=20,max=20,manager=true},
    forward={default=80,min=0,max=300,manager=true},
}
local function valid_value(key,value,allow_sentinel)
    local spec=SCHEMA[key];if not spec then return false end
    if spec.choices then return spec.choices[value]==true end
    if type(value)~='number' or value~=value or value%1~=0 then return false end
    return (allow_sentinel and value==spec.sentinel) or (value>=spec.min and value<=spec.max)
end
local function preset(axis,default)
    local ok,t=pcall(require,'mods/carpet_bomb_native/'..axis)
    if ok and type(t)=='table' and valid_value(axis,t.value,true) then return t.value end
    if ok then log('Invalid manager preset: '..axis..'; using default') end
    return default
end
log('Loading v'..S.version..' manager presets')
local defaults={}
for key,spec in pairs(SCHEMA) do
    defaults[key]=spec.manager and key~='bomb_count' and preset(key,spec.default) or spec.default
end
log('Manager presets: uses='..defaults.uses..' call_interval='..defaults.cooldown..' rearm='..defaults.rearm
    ..' projectile='..defaults.bomb..' bombs_per_aircraft='..defaults.bomb_count)
local config={};for k,v in pairs(defaults) do config[k]=v end
S.config=config
local last_text
local config_values={}
local config_keys={'language','enabled','uses','cooldown','rearm','bomb','bomb_count','forward'}
local function atomic_config(text)
    local temporary=CFG..'.tmp'
    local f,reason=io.open(temporary,'wb')
    if not f then return false,reason end
    local written,write_reason=f:write(text)
    local flushed,flush_reason=f:flush()
    local closed,close_reason=f:close()
    if not written or not flushed or not closed then
        os.remove(temporary);return false,write_reason or flush_reason or close_reason
    end
    -- The sibling temporary file is on the same volume; replace without truncating CFG.
    if kernel.MoveFileExA(temporary,CFG,0x9)==0 then
        os.remove(temporary);return false,'atomic replace failed'
    end
    return true
end
local function read_config()
    local f=io.open(CFG,'rb')
    if not f then
        -- Once loaded, an inaccessible/deleted file must not reset running settings.
        if last_text~=nil then return false end
        local initial='# Native CarpetBomb. Save to reload. manager = deployed dropdown.\n'
          ..'# cooldown = interval between uses; rearm = return/reload cooldown for ALL carried Eagles.\n'
          ..'# rearm=-1 keeps the existing game setting.\n'
          ..'# bomb=170 (Airstrike), 192 (200 kg), 239 (Eagle 500 kg).\n'
          ..'# bomb_count is fixed at20; forward=0..300 metres along incoming flight direction.\n'
          ..'language=zh\nenabled=1\nuses=manager\ncooldown=manager\nrearm=manager\nbomb=manager\nbomb_count=manager\nforward=manager\n'
        atomic_config(initial);f=io.open(CFG,'rb')
    end
    local text='';if f then text=f:read('*a');f:close() end
    if not text then return false end
    if text==last_text then return false end
    local next_config={};for k,v in pairs(defaults) do next_config[k]=v end
    local next_values={language='zh',enabled=1,uses='manager',cooldown='manager',rearm='manager',
        bomb='manager',bomb_count='manager',forward='manager'}
    for line in text:gmatch('[^\r\n]+') do
        local key,value=line:gsub('^\239\187\191',''):gsub('#.*$',''):match('^%s*([%w_]+)%s*=%s*(.-)%s*$')
        if key=='language' then
            if not valid_value(key,value,true) then
                last_text=text;log('Config rejected: '..key..'='..value);return false
            end
            next_config.language=value;next_values.language=value
        elseif key=='bomb_count' then
            if value~='manager' and value~='20' then log('Quantity override ignored: fixed20; executable patch withdrawn') end
            next_config.bomb_count=20
        elseif SCHEMA[key] then
            local n=value=='manager' and defaults[key] or tonumber(value)
            if not valid_value(key,n,true) then
                last_text=text;log('Config rejected: '..key..'='..value);return false
            end
            next_config[key]=n
            next_values[key]=value=='manager' and (SCHEMA[key].manager and 'manager' or n) or n
        end
    end
    for k,v in pairs(next_config) do config[k]=v end
    config_values=next_values;last_text=text;return true
end
local function save_config()
    -- Retain comments and unknown keys; persist each axis's manager/custom source.
    local seen={};local lines={}
    for line in (last_text or ''):gmatch('[^\r\n]+') do
        local prefix,key,tail=line:match('^(%s*([%w_]+)%s*=%s*)[%w_%-%.]+(.*)$')
        if key and config_values[key]~=nil then
            line=prefix..tostring(config_values[key])..tail;seen[key]=true
        end
        lines[#lines+1]=line
    end
    for _,key in ipairs(config_keys) do
        if not seen[key] then lines[#lines+1]=key..'='..tostring(config_values[key]) end
    end
    local text=table.concat(lines,'\n')..'\n'
    local ok,reason=atomic_config(text)
    if not ok then log('Menu config save failed: '..tostring(reason));return false,reason end
    last_text=text;return true
end
local MENU_TEXT={
    zh={title='原生地毯轰炸',language_description='选择本模组语言；应用后关闭并重新打开 Esc 菜单刷新文字。',
        enabled='启用',enabled_description='默认携带地毯轰炸。关闭后沿用原版恢复逻辑，停止调整后续飞机。',
        manager='跟随管理器',custom='自定义',limited='有限次数',unlimited='无限',vanilla='保持原版',
        uses_mode='使用次数来源',uses_mode_description='跟随部署预设，或指定有限次数 / 无限。已有次数可能需要新任务更新。',
        uses='使用次数',uses_description='1–100 次；应用此滑块会切换为有限次数。已有次数可能需要新任务更新。',
        cooldown_source='调用冷却来源',cooldown_source_description='跟随部署预设，或使用自定义调用间隔。',
        cooldown='调用冷却（秒）',cooldown_description='0–1800 秒；应用此滑块会切换为自定义。已在进行的计时可能需要新任务更新。',
        rearm_mode='飞鹰装填来源',rearm_mode_description='跟随部署预设、保持原版，或自定义。全部携带的飞鹰战备共用；舰船升级仍由游戏计算。',
        rearm='飞鹰装填冷却（秒）',rearm_description='0–1800 秒；应用此滑块会切换为自定义。影响全部携带的飞鹰战备。',
        bomb='炸弹类型',bomb_description='跟随预设或选择弹体。更换后需重启并进入新任务载入资源；数量固定为每架 20 枚。',
        airstrike='原版飞鹰空袭炸弹',native_bomb='地毯轰炸 200 kg',heavy_bomb='飞鹰 500 kg',
        forward_source='目标前移来源',forward_source_description='跟随部署预设，或自定义沿飞鹰进场方向的前移距离。',
        forward='投弹目标前移（米）',forward_description='0–300 米；应用此滑块会切换为自定义。仅影响后续新出动飞机，0 米保留原落点。'},
    en={title='Native CarpetBomb',language_description='Select this mod\'s language. Apply, then close and reopen the Esc menu.',
        enabled='Enable',enabled_description='Carry CarpetBomb automatically. Disable restores owned settings and stops adjusting future aircraft.',
        manager='Manager preset',custom='Custom',limited='Limited charges',unlimited='Unlimited',vanilla='Vanilla',
        uses_mode='Charges source',uses_mode_description='Use the deployed preset, limited charges, or unlimited charges. Existing charges may require a new mission.',
        uses='Charges',uses_description='1–100 charges. Applying this slider selects limited charges. Existing charges may require a new mission.',
        cooldown_source='Call interval source',cooldown_source_description='Use the deployed preset or a custom interval between calls.',
        cooldown='Call interval (seconds)',cooldown_description='0–1800 seconds. Applying this slider selects Custom. Running timers may require a new mission.',
        rearm_mode='Eagle rearm source',rearm_mode_description='Use the deployed preset, Vanilla, or Custom. Shared by all carried Eagles; ship upgrades still apply.',
        rearm='Eagle rearm (seconds)',rearm_description='0–1800 seconds. Applying this slider selects Custom. Affects all carried Eagles.',
        bomb='Bomb type',bomb_description='Use the preset or select a projectile. Restart and enter a new mission to load its resources. Fixed at 20 bombs per aircraft.',
        airstrike='Airstrike bomb',native_bomb='CarpetBomb 200 kg',heavy_bomb='Eagle 500 kg',
        forward_source='Forward offset source',forward_source_description='Use the deployed preset or a custom offset along the incoming flight direction.',
        forward='Strike forward offset (metres)',forward_description='0–300 metres. Applying this slider selects Custom. Only future aircraft change; 0 retains the original target.'},
}
local menu_api,menu_blocked
local function menu_text(key)
    return function()return MENU_TEXT[config.language=='en' and 'en' or 'zh'][key]end
end
local menu_title=menu_text('title')
local function finite_uses()return config.uses>0 and config.uses or (defaults.uses>0 and defaults.uses or 2)end
local function finite_rearm()return config.rearm>=0 and config.rearm or (defaults.rearm>=0 and defaults.rearm or 150)end
local function menu_values()
    return {language=config.language=='en' and 2 or 1,enabled=config.enabled==1,
        uses_mode=config_values.uses=='manager' and 1 or config.uses==-1 and 3 or 2,uses=finite_uses(),
        cooldown_source=config_values.cooldown=='manager' and 1 or 2,cooldown=config.cooldown,
        rearm_mode=config_values.rearm=='manager' and 1 or config.rearm==-1 and 2 or 3,rearm=finite_rearm(),
        bomb=config_values.bomb=='manager' and 1 or config.bomb==170 and 2 or config.bomb==192 and 3 or 4,
        forward_source=config_values.forward=='manager' and 1 or 2,forward=config.forward}
end
local function menu_checked(ok,reason)
    if ok~=true then error(tostring(reason or 'Menu operation failed'),0)end
end
local function menu_sync()
    for key,value in pairs(menu_values()) do
        local id='carpet_bomb_native_'..key
        if menu_api.get(id)~=value then menu_checked(menu_api.set(id,value))end
    end
end
local function menu_change(key,value)
    if S.phase=='stopped' then return false,S.stop_reason or 'stopped' end
    local axis=key:gsub('_mode$',''):gsub('_source$','')
    local wanted
    if key=='language' then
        if value~=1 and value~=2 then return end;wanted=value==1 and 'zh' or 'en'
    elseif key=='enabled' then
        if type(value)~='boolean' then return end;wanted=value and 1 or 0
    elseif key=='uses_mode' then
        if value~=1 and value~=2 and value~=3 then return end
        wanted=value==1 and 'manager' or value==3 and -1 or finite_uses()
    elseif key=='rearm_mode' then
        if value~=1 and value~=2 and value~=3 then return end
        wanted=value==1 and 'manager' or value==2 and -1 or finite_rearm()
    elseif key=='cooldown_source' or key=='forward_source' then
        if value~=1 and value~=2 then return end
        wanted=value==1 and 'manager' or config[axis]
    elseif key=='bomb' then
        wanted=({[1]='manager',[2]=170,[3]=192,[4]=239})[value]
        if wanted==nil then return end
    else
        if not valid_value(key,value,false) then return false,'invalid value' end
        wanted=value
    end
    if config_values[axis]==wanted then return true end
    local old_value,old_config=config_values[axis],config[axis]
    config_values[axis]=wanted;config[axis]=wanted=='manager' and defaults[axis] or wanted
    local saved,reason=save_config()
    if not saved then config_values[axis]=old_value;config[axis]=old_config;return false,reason end
    if axis~='language' then S.menu_dirty=true;S.elapsed=1 end
    return true
end
local function menu_attach(menu)
    if (tonumber(menu.version) or 1)<2 then error('Requires ModOptionsMenu version2',0)end
    for _,method in ipairs{'register_option','on_change','get','set'}do
        if type(menu[method])~='function' then error('Missing menu API '..method,0)end
    end
    local values=menu_values()
    local rows={
        {'language','choice',{'简体汉字','English'}}, {'enabled','toggle'},
        {'uses_mode','choice',{'manager','limited','unlimited'}}, {'uses','slider'},
        {'cooldown_source','choice',{'manager','custom'}}, {'cooldown','slider'},
        {'rearm_mode','choice',{'manager','vanilla','custom'}}, {'rearm','slider'},
        {'bomb','choice',{'manager','airstrike','native_bomb','heavy_bomb'}},
        {'forward_source','choice',{'manager','custom'}}, {'forward','slider'},
    }
    for _,row in ipairs(rows)do
        local key,kind=row[1],row[2]
        local option={type=kind,mod=menu_title,label=key=='language' and 'Language' or menu_text(key),
            default=values[key],description=menu_text(key=='language' and 'language_description' or key..'_description')}
        if kind=='choice' then
            option.choices={}
            for _,choice in ipairs(row[3])do
                option.choices[#option.choices+1]=key=='language' and choice or menu_text(choice)
            end
        elseif kind=='slider' then option.min=SCHEMA[key].min;option.max=SCHEMA[key].max;option.step=1 end
        menu_checked(menu.register_option('carpet_bomb_native_'..key,option))
    end
    for _,row in ipairs(rows)do
        local key=row[1]
        menu_checked(menu.on_change('carpet_bomb_native_'..key,function(value)menu_change(key,value)end))
    end
    menu_api=menu;menu_sync();S.menu_registered=true
    log('MODS menu registered (11 options; fixed vanilla quantity)')
end
local function menu_step()
    if menu_blocked then return end
    local ok,reason=pcall(function()
        if menu_api then menu_sync();return end
        local menu=rawget(_G,'ModOptionsMenu')
        if type(menu)=='table' then menu_attach(menu)end
    end)
    if not ok then menu_blocked=tostring(reason);log('Optional MODS menu unavailable: '..menu_blocked)end
end
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
      {'VirtualFree','int','(void *, size_t, uint32_t)'},
      {'MoveFileExA','int','(const char *, const char *, uint32_t)'},
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
local function field(bytes,offset,size)return bytes:sub(offset+1,offset+size)end
local function unhex(s)return(s:gsub('..',function(x)return string.char(tonumber(x,16))end))end
local mbi=ffi.new('uint8_t[48]')
local old_protection=ffi.new('uint32_t[1]')
local function writable(p,n)
    if kernel.VirtualQuery(ffi.cast('const void *',p),mbi,48)~=48 then return false end
    local s=ffi.string(mbi,48)
    return u32(s,32)==0x1000 and (u32(s,36)==4 or u32(s,36)==2)
        and u32(s,40)==0x20000 and p+n<=u64(s,0)+u64(s,24)
end
local function write(p,bytes)
    if not writable(p,#bytes) then return false end
    local region=ffi.string(mbi,48)
    local protection=u32(region,36);local old=old_protection
    if protection==2 and kernel.VirtualProtect(ffi.cast('void *',p),#bytes,4,old)==0 then return false end
    local ok=kernel.WriteProcessMemory(process,ffi.cast('void *',p),bytes,#bytes,count)~=0
        and tonumber(count[0])==#bytes and read(p,#bytes)==bytes
    if protection==2 and kernel.VirtualProtect(ffi.cast('void *',p),#bytes,protection,old)==0 then
        S.protection_pending[p]={address=p,size=#bytes,start=u64(region,0),extent=u64(region,24),protection=protection}
        return false
    end
    if not ok then return false end
    S.writes=S.writes+1;return true
end
-- Verified layout for Steam build 25480438; all offsets are relative to game.dll.
local BUILD={steam=25480438,timestamp=0x6ab3b43f,image_size=0x4744000}
local ADDRESS={stratagems=0x37cb600,stratagem_names=0x21d4aa0,projectiles=0x37c7670,
    payload_root=0x346bf98,eagle_manager=0x3326650}
local STRATAGEM={size=0x190,title=0x10,category=0x3c,uses=0x50,cooldown=0x68,
    transport_kind=0x70,transport_secondary=0x94,payload=0x98,payload_count=0xa0,
    resource_package=0xa8,additional_stratagem=0xc8,identity_flag=0xcc,transport_flags=0x104}
local PROJECTILE_LAYOUT={size=272,identity_size=0xa0,mass=0x24,resource=0x80,impact=0x90,expire=0x9c}
local EAGLE={component_slot=0xf12e78,row_size=152,private_row=11,original_bytes=1992,
    mode=0x10,projectile=0x18,approach_height=0x3c,manager_size=0x60,count=0x20,
    objects=0x48,states=0x58,state_size=0xfc,target=0x54,position=0x78,velocity=0xd4,
    firing=0x70,attacked=0x71,max_count=64}
local TABLE=ADDRESS.stratagems
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
    local expected=PROJECTILES[t];local address=ptr(S.base+ADDRESS.projectiles+t*8)
    local cached=S.projectiles[t]
    if cached and address~=cached.addr then error('Projectile table changed: '..t) end
    -- Pin the first validated row; one compact read checks its identity thereafter.
    local bytes=address and read(address,cached and PROJECTILE_LAYOUT.identity_size or PROJECTILE_LAYOUT.size)
    if not bytes then return nil end
    if u32(bytes,0)~=t or field(bytes,PROJECTILE_LAYOUT.mass,4)~=pack_float(expected.mass)
        or field(bytes,PROJECTILE_LAYOUT.resource,8)~=unhex('36b33606802fe571')
        or u32(bytes,PROJECTILE_LAYOUT.impact)~=expected.impact or u32(bytes,PROJECTILE_LAYOUT.expire)~=expected.expire then
        error('Projectile identity differs: '..t)
    end
    if cached then return cached end
    local result={type=t,addr=address}
    S.projectiles[t]=result;return result
end
local function projectile_intact(t)
    return projectile(t)~=nil
end
local function check_build()
    local base=tonumber(ffi.cast('uintptr_t',kernel.GetModuleHandleA('game.dll')))
    if not base or base==0 then return nil end
    local dos=read(base,64)
    if not dos or dos:sub(1,2)~='MZ' then error('Module header differs') end
    local pe=read(base+u32(dos,60),96)
    if not pe or pe:sub(1,4)~='PE\0\0' or u32(pe,8)~=BUILD.timestamp or u32(pe,80)~=BUILD.image_size then error('Unsupported game build') end
    for _,a in ipairs(ANCHORS) do
        local bytes=unhex(a[2]);if read(base+a[1],#bytes)~=bytes then error(string.format('Code differs at +0x%X',a[1])) end
    end
    return base
end
local function record(t,name,title)
    local p=ptr(S.base+TABLE+t*8);local bytes=p and read(p,STRATAGEM.size)
    if not bytes then return nil end
    local np=ptr(S.base+ADDRESS.stratagem_names+t*8);local n=read(np,64)
    local text=read(u64(bytes,STRATAGEM.title),128)
    if u32(bytes,0)~=t or not n or n:match('^([^%z]+)')~=name
        or not text or text:match('^([^%z]+)')~=title then error('Stratagem identity differs: '..t) end
    return {type=t,addr=p,bytes=bytes}
end
local function same_record(r)return ptr(S.base+TABLE+r.type*8)==r.addr and read(r.addr,4)==pack_u32(r.type) end
local function entry_valid(e)
    if e.validate and not e.validate() then return false end
    if e.record and not same_record(e.record) then return false end
    if e.root and ptr(S.base+ADDRESS.payload_root)~=e.root then return false end
    if e.table_slot and ptr(e.table_slot)~=e.table_address then return false end
    return true
end
local function owned_prefix(current,before,wanted)
    if not current then return false end
    for n=0,#wanted do
        if current==wanted:sub(1,n)..before:sub(n+1) then return true end
    end
    return false
end
local function recover_entry(e)
    if not entry_valid(e) then e.failure='identity changed';return false end
    local now=read(e.address,#e.original)
    if now==e.original then e.failure=nil;return true end
    if now~=e.last then e.failure=now and 'another writer' or 'unreadable';return false end
    local ok=write(e.address,e.original)
    local after=read(e.address,#e.original)
    if owned_prefix(after,now,e.original) then e.last=after end
    if ok and after==e.original then e.failure=nil;return true end
    e.failure='restore failed';return false
end
local function queue_recovery(e,before,wanted)
    local current=read(e.address,#before)
    local recovery={address=e.address,original=before,last=current,record=e.record,root=e.root,
        table_slot=e.table_slot,table_address=e.table_address,validate=e.validate}
    if not owned_prefix(current,before,wanted) then
        recovery.failure=current and 'another writer' or 'unreadable'
        -- Do not claim an unreadable or foreign value as our last write.
        recovery.last=wanted
    end
    if not recover_entry(recovery) then S.recovery[#S.recovery+1]=recovery;return false end
    return true
end
local function rollback(done)
    for i=#done,1,-1 do local e=done[i];queue_recovery(e,e.before or e.original,e.wanted) end
    return #S.recovery==0
end
local function cached_record(t,name,title)
    local cache=S.initial_records
    if not cache then cache={};S.initial_records=cache end
    if cache[t] then
        if not same_record(cache[t]) then error('Prepared stratagem record changed: '..t) end
        return cache[t]
    end
    local r=record(t,name,title);cache[t]=r;return r
end
local DATA={ -- Verified current datalibrary headers, capacities and record strides.
    {name='Visibility',offset=0xf12478,hash=0xe96bca35,size=3344,capacity=152,rows=76,row_size=12},
    {name='Tag',offset=0xf12490,hash=0x6e8b3849,size=323136,capacity=1122,rows=561,row_size=544},
    {name='WeaponMagazine',offset=0xf124a0,hash=0xfb8d88a3,size=52000,capacity=540,rows=271,row_size=160},
    {name='LoadoutPackage',offset=0xf12558,hash=0x7a858691,size=34592,capacity=1080,rows=541,row_size=32},
    {name='EncyclopediaEntry',offset=0xf126d8,hash=0x8a40fe2f,size=58520,capacity=1330,rows=665,row_size=56},
    {name='Unit',offset=0xf12738,hash=0x4437574d,size=284224,capacity=3382,rows=1692,row_size=136},
    {name='Faction',offset=0xf12748,hash=0x5653ea91,size=97304,capacity=1056,rows=529,row_size=152},
    {name='EffectReference',offset=0xf127b8,hash=0x604434c9,size=2713472,capacity=1376,rows=688,row_size=3912},
    {name='Wieldable',offset=0xf127f0,hash=0x3bf780f6,size=32320,capacity=1010,rows=505,row_size=32},
    {name='Animation',offset=0xf12968,hash=0x4856d42d,size=109440,capacity=1520,rows=760,row_size=112},
    {name='OverlapDamage',offset=0xf12b70,hash=0xc4b6b405,size=99288,capacity=126,rows=63,row_size=1544},
    {name='Health',offset=0xf12b78,hash=0xb3915de3,size=11108224,capacity=1002,rows=502,row_size=22096},
    {name='WeaponWielder',offset=0xf12bd0,hash=0x1f5ab323,size=14896,capacity=438,rows=219,row_size=36},
    {name='WeaponData',offset=0xf12bd8,hash=0x88e4dbb1,size=462592,capacity=730,rows=366,row_size=1232},
    {name='Mount',offset=0xf12d50,hash=0x3845b1e0,size=24744,capacity=324,rows=163,row_size=120},
    {name='Eagle',offset=0xf12e78,hash=0x556ff68b,size=1992,capacity=20,rows=11,row_size=152},
    {name='ProjectileWeapon',offset=0xf12e80,hash=0x45171b68,size=176224,capacity=542,rows=272,row_size=616},
    {name='EntitySettings',offset=0xf12ea0,hash=0x80c1ca70,size=184452,capacity=4096,rows=0,row_size=32},
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
local EMPTY_HASH=string.rep('\0',8)
local function find_slot(address,hash,capacity,stride)
    local start=hash_slot(hash,capacity)
    for step=0,capacity-1 do
        local slot=(start+step)%capacity;local entry=read(address+slot*stride,stride)
        if not entry then return nil end
        local key=entry:sub(1,8)
        if key==hash then return slot,true,entry end
        if key==EMPTY_HASH then return slot,false,entry end
    end
    error('Component hash table is full')
end
local function release_unpublished()
    local draft=S.repair_draft
    -- A published pointer may already be cached by the engine, even after rollback.
    -- Its single process-lifetime allocation must remain valid until game exit.
    if not draft or not draft.allocation or draft.publication_attempted then return true end
    if kernel.VirtualFree(ffi.cast('void *',draft.allocation),0,0x8000)~=0 then
        for i=#S.allocations,1,-1 do
            if S.allocations[i]==draft.allocation then table.remove(S.allocations,i);break end
        end
        draft.allocation=nil
        return true
    end
    return false
end
local function repair_payload()
    if S.repair then return true end
    local root=ptr(S.base+ADDRESS.payload_root);if not root or root<0x10000 then return false end
    local draft=S.repair_draft
    if not draft then
        draft={root=root,plan={},tables={},next_table=1};S.repair_draft=draft
    end
    if root~=draft.root then error('Payload root changed during preparation') end
    for _,t in ipairs(draft.tables) do
        if ptr(t.slot)~=t.original then error('Prepared payload table changed') end
    end
    local plan,tables=draft.plan,draft.tables
    -- Every required alias is prepared and checked before any published data is changed.
    -- Resume at the missing table; resolved hash slots are never searched again.
    for i=draft.next_table,#DATA do
        local d=DATA[i]
        local slot=root+d.offset;local p=ptr(slot);local header=p and read(p-28,28)
        if not header then return false end
        if header:sub(5,8)~='LDLD' or u32(header,0)~=d.hash or u32(header,12)~=d.hash
            or u32(header,8)~=1 or u32(header,16)~=d.size or u32(header,20)~=1 then error('Payload datalibrary header differs') end
        local stride=d.rows==0 and 32 or 16
        local source,found,donor=find_slot(p,DONOR,d.capacity,stride)
        if source==nil then return false end
        if not found then error('Donor payload component missing') end
        local target,exists,original=find_slot(p,NATIVE,d.capacity,stride)
        if target==nil then return false end
        if exists then error('Native payload component already exists; refusing to overwrite') end
        if d.rows>0 and u32(donor,8)>=d.rows then error('Donor component index differs') end
        if d.offset==EAGLE.component_slot then
            local bytes=read_large(p,d.size);if not bytes then return false end
            local ri=u32(donor,8)
            local row=bytes:sub(d.capacity*stride+ri*d.row_size+1,d.capacity*stride+(ri+1)*d.row_size)
            if u32(row,EAGLE.mode)~=5 or u32(row,20)~=0 or u32(row,EAGLE.projectile)~=170 then error('Eagle donor differs') end
            local native=row:sub(1,EAGLE.mode)..pack_u32(6)..row:sub(EAGLE.mode+5)
            -- CarpetBomb predicts a horizontal release. The Airstrike donor approaches
            -- from 1000 m and starts within that range, causing immediate, distant drops.
            -- Use a low approach for this private record so the plane enters release range.
            native=native:sub(1,EAGLE.approach_height)..pack_float(120)..native:sub(EAGLE.approach_height+5)
            -- Extra record 11 keeps the native bombing mode and vanilla rows intact.
            local shadow=bytes:sub(1,target*stride)..NATIVE..pack_u32(EAGLE.private_row)..donor:sub(13,16)..bytes:sub(target*stride+stride+1)..native
            local h=header:sub(1,16)..pack_u32(#shadow)..header:sub(21)
            draft.complete=h..shadow
            draft.eagle_original=bytes
            draft.eagle={slot=slot,address=slot,original=pack_ptr(p),root=root}
        else
            if d.rows==0 and (u64(donor,16)~=22 or u32(donor,24)~=3547464239) then error('Eagle entity component list differs') end
            plan[#plan+1]={address=p+target*stride,original=original,wanted=NATIVE..donor:sub(9),
                root=root,table_slot=slot,table_address=p}
        end
        tables[#tables+1]={slot=slot,original=p}
        draft.next_table=i+1
    end
    if read_large(u64(draft.eagle.original,0),#draft.eagle_original)~=draft.eagle_original then
        error('Eagle donor table changed during preparation')
    end
    -- Allocate only after every table is available. Waiting cannot accumulate copies.
    local allocation=tonumber(ffi.cast('uintptr_t',kernel.VirtualAlloc(nil,#draft.complete,0x3000,4)))
    if not allocation or allocation<0x10000 then error('Payload allocation failed') end
    draft.allocation=allocation;S.allocations[#S.allocations+1]=allocation
    for o=0,#draft.complete-1,512 do
        if not write(allocation+o,draft.complete:sub(o+1,o+512)) then error('Private payload copy failed') end
    end
    local eagle=draft.eagle;eagle.wanted=pack_ptr(allocation+28);eagle.table=allocation+28
    plan[#plan+1]=eagle
    for _,e in ipairs(plan) do if read(e.address,#e.original)~=e.original or not writable(e.address,#e.wanted) then error('Payload alias conflict or non-writable data') end end
    if ptr(S.base+ADDRESS.payload_root)~=root then error('Payload root changed before publication') end
    for _,t in ipairs(tables) do if ptr(t.slot)~=t.original then error('Payload table changed before publication') end end
    local done={}
    for _,e in ipairs(plan) do
        done[#done+1]=e
        if e==eagle then draft.publication_attempted=true end
        if not write(e.address,e.wanted) then
            local clean=rollback(done)
            error('Payload publication failed; '..(clean and 'rolled back' or 'rollback pending'))
        end
    end
    S.repair={root=root,plan=plan,tables=tables,eagle=eagle}
    S.repair_draft=nil
    log('Missing native payload reconstructed: 17 component/entity aliases; private Eagle payload 6, approach height 120 m; vanilla Eagles preserved')
    return true
end
local function repair_intact()
    local r=S.repair;if not r then return true end
    if ptr(S.base+ADDRESS.payload_root)~=r.root then return false end
    for _,t in ipairs(r.tables) do
        local expected=t.slot==r.eagle.slot and u64(r.eagle.wanted,0) or t.original
        if ptr(t.slot)~=expected then return false end
    end
    for _,e in ipairs(r.plan) do if read(e.address,#e.wanted)~=e.wanted then return false end end
    return true
end
local function restore()
    local pending={}
    for i=#S.owned,1,-1 do
        local e=S.owned[i]
        if not recover_entry(e) then pending[#pending+1]=e end
    end
    S.owned=pending;return #pending==0
end
local function cleanup()
    if S.cleanup_attempts>=3 then return end
    S.cleanup_attempts=S.cleanup_attempts+1
    local pending={}
    for _,e in ipairs(S.recovery) do if not recover_entry(e) then pending[#pending+1]=e end end
    S.recovery=pending
    restore()
    for p,e in pairs(S.protection_pending) do
        if kernel.VirtualQuery(ffi.cast('const void *',p),mbi,48)==48 then
            local region=ffi.string(mbi,48);local protection=u32(region,36)
            if u32(region,32)==0x1000 and u32(region,40)==0x20000
                and u64(region,0)==e.start and u64(region,24)==e.extent then
                if protection==e.protection or (protection==4
                    and kernel.VirtualProtect(ffi.cast('void *',p),e.size,e.protection,old_protection)~=0) then
                    S.protection_pending[p]=nil
                end
            end
        end
    end
    local freed=release_unpublished()
    local protections=0;for _ in pairs(S.protection_pending) do protections=protections+1 end
    S.cleanup_pending=#S.owned+#S.recovery+protections+(freed and 0 or 1)
    S.cleanup_complete=S.cleanup_pending==0
    if S.repair_draft and not S.repair_draft.allocation then S.repair_draft=nil end
end
local function stop(reason)
    if S.phase=='stopped' then return end
    S.phase='stopped';S.stop_reason=reason;S.elapsed=0;cleanup()
    S.plan=nil;S.forward_seen=nil
    S.initial_records=nil
    if S.repair_draft then
        S.repair_draft.complete=nil;S.repair_draft.eagle_original=nil
        if not S.repair_draft.allocation then S.repair_draft=nil end
    end
    log('STOPPED: '..reason..(S.cleanup_complete and '; cleanup complete' or '; cleanup pending='..S.cleanup_pending))
end
local function apply()
    if S.phase=='stopped' then return end
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
    add(S.native,STRATAGEM.uses,active and pack_u32(config.uses==-1 and 0xffffffff or config.uses) or field(S.native.bytes,STRATAGEM.uses,4))
    add(S.native,STRATAGEM.cooldown,active and pack_float(config.cooldown) or field(S.native.bytes,STRATAGEM.cooldown,4))
    for _,field in ipairs({{STRATAGEM.transport_kind,4},{STRATAGEM.transport_secondary,4},{STRATAGEM.additional_stratagem,4},{STRATAGEM.transport_flags,4}}) do
        local offset,n=field[1],field[2]
        add(S.native,offset,active and S.donor.bytes:sub(offset+1,offset+n) or S.native.bytes:sub(offset+1,offset+n))
    end
    -- 200 kg uses the same bomb unit and impact effect already in Airstrike's
    -- package. 500 kg uses EagleBomb's package, including its delayed explosion.
    local package=active and field((config.bomb==239 and S.heavy or S.donor).bytes,STRATAGEM.resource_package,8)
        or field(S.native.bytes,STRATAGEM.resource_package,8)
    add(S.native,STRATAGEM.resource_package,package)
    if S.repair then
        plan[#plan+1]={record=S.native,address=S.repair.eagle.table+EAGLE.original_bytes+EAGLE.projectile,
            original=pack_u32(170),wanted=pack_u32(active and config.bomb or 170),
            root=S.repair.root,table_slot=S.repair.eagle.slot,table_address=S.repair.eagle.table}
    end
    -- Type 49 is shared by every carried Eagle. The vanilla choice neither
    -- writes nor monitors this field unless returning a value we previously owned.
    if custom_rearm or S.rearm_owned then
        add(S.rearm,STRATAGEM.cooldown,custom_rearm and pack_float(config.rearm) or field(S.rearm.bytes,STRATAGEM.cooldown,4))
    end
    -- Publish automatic carrying last, after the native payload and transport are valid.
    add(S.carrier,STRATAGEM.additional_stratagem,active and pack_u32(103) or field(S.carrier.bytes,STRATAGEM.additional_stratagem,4))
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
                local clean=rollback(done)
                stop('Write failed; '..(clean and 'transaction rolled back' or 'rollback pending'));return
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
local vector_buffer=ffi.new('float[3]')
local function vector(bytes,offset)
    local values=vector_buffer;ffi.copy(values,bytes:sub(offset+1,offset+12),12)
    local out={tonumber(values[0]),tonumber(values[1]),tonumber(values[2])}
    for _,v in ipairs(out) do if v~=v or math.abs(v)>10000000 then return nil end end
    return out
end
local function shift_incoming_targets(dt)
    if S.phase~='active' or S.forward_fault then return end
    S.forward_elapsed=(S.forward_elapsed or 0)+((type(dt)=='number' and dt>0 and dt<5) and dt or 1/60)
    if S.forward_elapsed<0.1 then return end;S.forward_elapsed=0
    local manager=ptr(S.base+ADDRESS.eagle_manager)
    local header=manager and read(manager,EAGLE.manager_size);if not header then return end
    local n=u32(header,EAGLE.count);if n==0 then S.forward_seen={};return end
    if n>EAGLE.max_count then error('Eagle state count differs; forward adjustment disabled') end
    local objects,states=u64(header,EAGLE.objects),u64(header,EAGLE.states)
    if objects<0x10000 or states<0x10000 then return end
    local object_index=read(objects,n*8);if not object_index then return end
    local previous=S.forward_seen or {};local present={}
    for i=0,n-1 do
        local descriptor=u64(object_index,i*8);local identity=read(descriptor,16)
        if identity and identity:sub(1,8)==NATIVE then
            local key=tostring(descriptor)..':'..u32(identity,8)..':'..u32(identity,12)
            present[key]=previous[key]
            if not present[key] then
                local address=states+i*EAGLE.state_size;local state=read(address,EAGLE.state_size)
                if state then
                    if config.forward==0 or state:byte(EAGLE.firing+1)~=0 or state:byte(EAGLE.attacked+1)~=0 then
                        present[key]=true
                    else
                        local target,current,velocity=vector(state,EAGLE.target),vector(state,EAGLE.position),vector(state,EAGLE.velocity)
                        if target and current and velocity then
                            local dx,dy=target[1]-current[1],target[2]-current[2]
                            local distance=math.sqrt(dx*dx+dy*dy)
                            local vx,vy=velocity[1],velocity[2];local speed=math.sqrt(vx*vx+vy*vy)
                            if distance>=50 and (speed<=1 or vx*dx+vy*dy>0) then
                                if speed>1 then dx,dy,distance=vx,vy,speed end
                                local x=target[1]+dx/distance*config.forward
                                local y=target[2]+dy/distance*config.forward
                                local before=state:sub(EAGLE.target+1,EAGLE.target+8);local wanted=pack_float(x)..pack_float(y)
                                -- Recheck the native descriptor and current state allocation.
                                -- Only its horizontal target moves; beacon and altitude stay intact.
                                if read(descriptor,16)==identity and ptr(manager+EAGLE.objects)==objects
                                    and ptr(manager+EAGLE.states)==states and ptr(objects+i*8)==descriptor
                                    and read(address+EAGLE.target,8)==before then
                                    if not write(address+EAGLE.target,wanted) then
                                        local recovered=queue_recovery({address=address+EAGLE.target,validate=function()
                                            return ptr(S.base+ADDRESS.eagle_manager)==manager and read(descriptor,16)==identity
                                                and ptr(manager+EAGLE.objects)==objects and ptr(objects+i*8)==descriptor
                                                and ptr(manager+EAGLE.states)==states
                                        end},before,wanted)
                                        if not recovered then stop('Forward target write failed; restoration pending') end
                                        error('Forward target write failed; '..(recovered and 'target restored' or 'restoration pending'))
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
    if not S.base then S.base=check_build();if not S.base then return end end
    local carrier=cached_record(33,'AmmoRack','CONSUMABLES. RESUPPLY')
    local native=cached_record(103,'CarpetBomb','MISSIONS CLAN STATION. Carpet Bombing Run')
    local donor=cached_record(18,'EagleAirstrike','EAGLE. AIRSTRIKE')
    local rearm=cached_record(49,'EagleRearm','EAGLE. REARM')
    local heavy=cached_record(3,'EagleBomb','EAGLE. 500KG BOMB')
    if not carrier or not native or not donor or not rearm or not heavy then return end
    if not projectile(config.bomb) then return end
    if field(heavy.bytes,STRATAGEM.resource_package,8)~=unhex('5abda258703bc39b') then error('Eagle 500 kg package differs') end
    if u32(rearm.bytes,STRATAGEM.category)~=7 then error('Eagle rearm category differs') end
    if u32(carrier.bytes,STRATAGEM.category)~=2 or u32(carrier.bytes,STRATAGEM.additional_stratagem)~=0 or u32(native.bytes,STRATAGEM.category)~=0
        or u32(native.bytes,STRATAGEM.transport_kind)~=2 or u32(native.bytes,STRATAGEM.transport_secondary)~=2 or u32(native.bytes,STRATAGEM.identity_flag)~=1
        or u64(native.bytes,STRATAGEM.payload_count)~=1 or read(u64(native.bytes,STRATAGEM.payload),8)~=unhex('c66cef766697cb6c') then
        error('Native/carrier fields differ from verified records')
    end
    if u32(donor.bytes,STRATAGEM.transport_kind)~=0 or u32(donor.bytes,STRATAGEM.transport_secondary)~=0 or u32(donor.bytes,STRATAGEM.additional_stratagem)~=49
        or field(donor.bytes,STRATAGEM.resource_package,8)~=unhex('f338ff0016cc331e') or u32(donor.bytes,STRATAGEM.transport_flags)~=0x1084 then error('Eagle transport settings differ') end
    S.carrier=carrier;S.native=native;S.donor=donor;S.rearm=rearm;S.heavy=heavy
    S.initial_records=nil;apply()
end
local function tick(dt)
    S.elapsed=S.elapsed+((type(dt)=='number' and dt>0 and dt<5) and dt or 1/60)
    if S.elapsed<1 then return end;S.elapsed=0
    if S.phase=='stopped' then
        if not S.cleanup_complete and S.cleanup_attempts<3 then
            cleanup()
            log('STOPPED cleanup: pending='..S.cleanup_pending..'; attempt='..S.cleanup_attempts..'/3')
        end
        return
    end
    local changed=read_config()
    menu_step()
    if S.menu_dirty then changed=true;S.menu_dirty=false end
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
S.disable=function()
    if S.phase=='stopped' then return false,S.stop_reason or 'stopped' end
    -- Use the same validation/persistence/scheduled apply path as the menu.
    return menu_change('enabled',false)
end
read_config();menu_step();log('Loaded v'..S.version..'; native grant experiment, Bingus Shared Loader v18 / API 1')
local old_update=rawget(_G,'update')
if type(old_update)~='function' then S.phase='stopped';log('Global update callback unavailable');return S end
function update(dt,...)
    local ok,err=pcall(tick,dt);if not ok then stop(tostring(err)) end
    local shifted,shift_error=pcall(shift_incoming_targets,dt)
    if not shifted then S.forward_fault=true;log('Forward adjustment stopped: '..tostring(shift_error)) end
    return old_update(dt,...)
end
return S
