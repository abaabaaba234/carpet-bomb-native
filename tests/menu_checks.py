"""Test the menu contract, optionally against the external version2 provider."""
import os,struct
from pathlib import Path

PREFIX=b'carpet_bomb_native_'
ORDER=['language','enabled','uses_mode','uses','cooldown_source','cooldown',
       'rearm_mode','rearm','bomb','forward_source','forward']

def run(Scenario,SOURCE,ROOT):
    provider=Path(os.environ['HD2_MOD_OPTIONS_MENU_SOURCE']) if os.environ.get('HD2_MOD_OPTIONS_MENU_SOURCE') else None
    if provider is not None and not provider.is_file():
        raise FileNotFoundError('HD2_MOD_OPTIONS_MENU_SOURCE must point to the ModOptionsMenu Lua source')
    def load_menu(s):
        if provider is not None:
            source=provider.read_bytes()
            prefix=source.split(b'_G.ModOptionsMenu = api',1)[0]
            assert len(prefix)>50000
            return s.lua.execute(prefix+b'''\n_G.ModOptionsMenu=api
              return {api=api,state=state,translation=translation,
                set_pending=set_pending,apply_pending=apply_pending}''')
        # Minimal public-API contract fixture: applied values and pending values
        # stay distinct, and Apply calls callbacks in registration order.
        return s.lua.execute(b'''
          local state={options={},mods={},callbacks={},values={},saved={},pending={},order={}}
          local function text(source)return type(source)=='function' and source() or source end
          local function refresh_option(option)
            option.label=text(option.sources.label);option.description=text(option.sources.description)
            if option.kind=='choice' then
              option.choices={}
              for i,value in ipairs(option.sources.choices)do option.choices[i]=string.upper(text(value))end
            end
          end
          local api={api=1,version=2}
          local function valid(option,value)
            if option.kind=='toggle' then return type(value)=='boolean' end
            if type(value)~='number' or value~=value or value%1~=0 then return false end
            if option.kind=='choice' then return value>=1 and value<=#option.choices end
            return value>=option.min and value<=option.max
          end
          function api.register_option(id,spec)
            if state.options[id] then return false,'duplicate option' end
            local title=string.upper(text(spec.mod))
            local mod=state.mods[title]
            if not mod then mod={title=title,source=spec.mod,order={}};state.mods[title]=mod end
            local option={id=id,kind=spec.type,default=spec.default,min=spec.min,max=spec.max,
              step=spec.step,mod=title,sources={label=spec.label,description=spec.description,choices=spec.choices}}
            refresh_option(option)
            state.options[id]=option;state.order[#state.order+1]=id;mod.order[#mod.order+1]=option
            local saved=state.saved[id];local value
            if saved~=nil then
              if option.kind=='toggle' then value=saved=='true' else value=tonumber(saved) end
            end
            if not valid(option,value) then value=spec.default end
            assert(valid(option,value));state.values[id]=value;return true
          end
          function api.get(id)return state.values[id]end
          function api.set(id,value)
            if not state.options[id] or not valid(state.options[id],value) then return false,'invalid value' end
            state.values[id]=value;state.pending[id]=nil;state.saved[id]=tostring(value);return true
          end
          function api.on_change(id,callback)
            local list=state.callbacks[id] or {};list[#list+1]=callback;state.callbacks[id]=list;return true
          end
          local function set_pending(id,value)
            assert(valid(state.options[id],value));state.pending[id]=value
          end
          local function apply_pending()
            local count=0
            for _,id in ipairs(state.order)do
              local value=state.pending[id]
              if value~=nil and value~=state.values[id] then
                state.values[id]=value;state.saved[id]=tostring(value);count=count+1
                for _,callback in ipairs(state.callbacks[id] or {})do callback(value,id)end
              end
              state.pending[id]=nil
            end
            return count
          end
          local translation={refresh=function()
            for _,mod in pairs(state.mods)do mod.title=string.upper(text(mod.source))end
            for _,option in pairs(state.options)do refresh_option(option)end
          end}
          ModOptionsMenu=api
          return {api=api,state=state,translation=translation,set_pending=set_pending,apply_pending=apply_pending}
        ''')

    def get(m,key):return m[b'api'][b'get'](PREFIX+key.encode())
    def pending(m,key,value):m[b'set_pending'](PREFIX+key.encode(),value)
    def apply(s,m,**values):
        for key,value in values.items():pending(m,key,value)
        m[b'apply_pending']();s.tick()
    def file(s):return (s.logs/'CarpetBombNative.cfg').read_text(encoding='utf-8')
    def snapshot(s):return {k:v for k,v in s.state[b'config'].items() if k!=b'language'}

    def language_cache_pending_and_restart():
        old='# keep comment\nunknown_future_key=preserved\nenabled=1\nuses=manager\ncooldown=17\nrearm=-1\nbomb=192\nforward=43\n'
        s=Scenario({'uses':4,'cooldown':15},cfg=old)
        try:
            assert s.state[b'config'][b'language']==b'zh'
            m=load_menu(s);s.lua.globals()[b'menu_state']=m[b'state']
            s.lua.execute(b'''menu_state.saved={carpet_bomb_native_language='2',
                carpet_bomb_native_enabled='false',carpet_bomb_native_cooldown='900'}''')
            assert s.tick()==(1.1,b'preserved',42)
            assert s.state[b'phase']==b'active' and s.state[b'menu_registered']
            state=m[b'state'];options=state[b'options'];mod=state[b'mods'][options[PREFIX+b'language'][b'mod']]
            assert [mod[b'order'][i][b'id'] for i in range(1,12)]==[PREFIX+k.encode() for k in ORDER]
            assert options[PREFIX+b'language'][b'label']==b'Language'
            assert options[PREFIX+b'language'][b'choices'][1]=='简体汉字'.encode()
            assert options[PREFIX+b'language'][b'choices'][2]==b'ENGLISH'
            assert get(m,'language')==1 and get(m,'enabled') is True and get(m,'cooldown')==17
            assert get(m,'uses_mode')==1 and get(m,'uses')==4 and get(m,'rearm_mode')==2
            for _ in range(4):s.tick()
            assert all(len(state[b'callbacks'][PREFIX+k.encode()])==1 for k in ORDER)
            pending(m,'cooldown',33)
            for _ in range(3):s.tick()
            assert state[b'pending'][PREFIX+b'cooldown']==33 and get(m,'cooldown')==17
            pending(m,'language',2)
            before=snapshot(s);writes=len(s.mem.writes)
            assert m[b'apply_pending']()==2
            s.tick();m[b'translation'][b'refresh']()
            assert get(m,'language')==2 and get(m,'cooldown')==33 and get(m,'cooldown_source')==2
            assert options[PREFIX+b'enabled'][b'label']==b'Enable' and mod[b'title']==b'NATIVE CARPETBOMB'
            assert len(s.mem.writes)==writes+1 and s.state[b'config'][b'uses']==4
            assert '# keep comment' in file(s) and 'unknown_future_key=preserved' in file(s)
            assert 'uses=manager' in file(s) and 'language=en' in file(s)
            before=snapshot(s);writes=len(s.mem.writes)
            apply(s,m,language=1);m[b'translation'][b'refresh']()
            assert snapshot(s)==before and len(s.mem.writes)==writes
            assert mod[b'title']=='原生地毯轰炸'.encode()
            apply(s,m,language=2)
            saved=file(s)
            # Invalid old/new fields reject the complete edit, retaining valid config.
            s.cfg('language=invalid\nuses=7\n');assert s.state[b'config'][b'uses']==4
            s.cfg('language=zh\ncooldown=1801\n');assert get(m,'language')==2 and get(m,'cooldown')==33
        finally:s.close()
        s=Scenario({'uses':4},cfg=saved)
        try:
            m=load_menu(s);s.tick()
            assert get(m,'language')==2 and get(m,'uses_mode')==1 and get(m,'uses')==4
            assert get(m,'cooldown')==33 and s.state[b'config'][b'bomb_count']==20
            s.cfg('language=zh\nenabled=0\nuses=7\ncooldown=0\nrearm=1800\nbomb=239\nforward=300\n')
            assert get(m,'enabled') is False and get(m,'uses')==7 and get(m,'cooldown')==0
            assert get(m,'rearm')==1800 and get(m,'bomb')==4 and get(m,'forward')==300
            assert s.state[b'phase']==b'disabled'
        finally:s.close()

    def parameters_manager_restore_and_disable():
        s=Scenario({'uses':8,'cooldown':30,'rearm':60,'bomb':192,'forward':120})
        try:
            m=load_menu(s);s.tick()
            apply(s,m,uses_mode=3,cooldown=1800,rearm_mode=2,bomb=4,forward=300)
            c=s.state[b'config'];assert c[b'uses']==-1 and c[b'cooldown']==1800 and c[b'rearm']==-1
            assert c[b'bomb']==239 and c[b'forward']==300 and c[b'bomb_count']==20
            assert s.r(103,0x50,4)==struct.pack('<I',0xffffffff)
            apply(s,m,uses=100,rearm=1800)
            assert c[b'uses']==100 and get(m,'uses_mode')==2 and c[b'rearm']==1800 and get(m,'rearm_mode')==3
            apply(s,m,uses=1,cooldown=0,rearm=0,forward=0,bomb=2)
            assert c[b'uses']==1 and c[b'cooldown']==0 and c[b'rearm']==0 and c[b'forward']==0 and c[b'bomb']==170
            # Directly exercise validation even if a provider invokes an invalid callback.
            callbacks=m[b'state'][b'callbacks'];before=snapshot(s);saved=file(s)
            for key,value in [('uses',0),('uses',101),('uses',1.5),('cooldown',float('nan')),
                ('cooldown',1801),('rearm',-1),('rearm',1801),('forward',-1),('forward',301),
                ('bomb',0),('bomb',5),('language',3),('enabled',0),('uses_mode',0),('rearm_mode',4)]:
                callbacks[PREFIX+key.encode()][1](value)
            s.tick();assert snapshot(s)==before and file(s)==saved
            apply(s,m,uses_mode=1,cooldown_source=1,rearm_mode=1,bomb=1,forward_source=1)
            assert (c[b'uses'],c[b'cooldown'],c[b'rearm'],c[b'bomb'],c[b'forward'])==(8,30,60,192,120)
            assert all(f'{key}=manager' in file(s) for key in ('uses','cooldown','rearm','bomb','forward'))
            apply(s,m,enabled=False)
            assert s.state[b'phase']==b'disabled' and s.r(33,0,400)==s.originals[33]
            assert s.r(103,0,400)==s.originals[103] and s.r(49,0,400)==s.originals[49]
            apply(s,m,enabled=True);assert s.state[b'phase']==b'active'
            calls=s.lua.globals()[b'calls'];s.lua.eval(b'function(src)return assert(loadstring(src))()end')(SOURCE)
            s.tick();assert s.lua.globals()[b'calls']==calls+1
            assert all(len(callbacks[PREFIX+k.encode()])==1 for k in ORDER)
        finally:s.close()

    def source_modes_and_simultaneous_changes():
        s=Scenario({'uses':-1,'rearm':-1})
        try:
            m=load_menu(s);s.tick()
            assert get(m,'uses')==2 and get(m,'rearm')==150
            apply(s,m,uses_mode=2,rearm_mode=3,cooldown_source=2,forward_source=2)
            c=s.state[b'config'];assert c[b'uses']==2 and c[b'rearm']==150
            assert get(m,'cooldown_source')==2 and get(m,'forward_source')==2
            apply(s,m,uses_mode=3,uses=9,rearm_mode=2,rearm=35,cooldown_source=1,cooldown=31,
                forward_source=1,forward=41,language=2)
            assert c[b'uses']==9 and c[b'rearm']==35 and c[b'cooldown']==31 and c[b'forward']==41
            assert get(m,'uses_mode')==2 and get(m,'rearm_mode')==3
            assert get(m,'cooldown_source')==2 and get(m,'forward_source')==2
        finally:s.close()

    def menu_failures_and_save_failures():
        failures=[b'ModOptionsMenu={version=1}',b'ModOptionsMenu={version=2}',
            b'''ModOptionsMenu={version=2,register_option=function()return false,'registration rejected'end,
            on_change=function()return true end,get=function()end,set=function()return true end}''',
            b'''ModOptionsMenu={version=2,register_option=function()return true end,
            on_change=function()return false,'callback rejected'end,get=function()end,set=function()return true end}''',
            b'''ModOptionsMenu={version=2,register_option=function()return true end,
            on_change=function()return true end,get=function()end,set=function()return false,'sync rejected'end}''']
        for source in failures:
            s=Scenario()
            try:
                s.lua.execute(source);s.tick();assert s.state[b'phase']==b'active'
                log=s.state[b'status'];s.tick();assert s.state[b'status']==log
                s.cfg('enabled=0\nuses=3\n');assert s.state[b'phase']==b'disabled'
            finally:s.close()
        s=Scenario()
        try:
            m=load_menu(s);s.tick();saved=file(s);writes=len(s.mem.writes)
            s.lua.execute(b'''original_io_open=io.open
                io.open=function(path,mode)if path:match('CarpetBombNative%.cfg$') and mode=='wb' then
                    return nil,'simulated save failure' end;return original_io_open(path,mode)end''')
            apply(s,m,enabled=False,cooldown=45)
            assert s.state[b'phase']==b'active' and get(m,'enabled') is True and get(m,'cooldown')==15
            assert file(s)==saved and len(s.mem.writes)==writes
        finally:s.close()

    passed=[]
    for name,fn in [
        ('real menu: order, language migration/refresh, cache authority, pending edits and restart',language_cache_pending_and_restart),
        ('real menu: valid ranges, invalid callback rejection, manager restoration and disable restoration',parameters_manager_restore_and_disable),
        ('real menu: sentinel sources and simultaneous language/parameter changes',source_modes_and_simultaneous_changes),
        ('optional menu version/registration/callback/sync failures and config save failure',menu_failures_and_save_failures)]:
        name=name if provider is not None else name.replace('real menu:', 'menu contract:')
        fn();passed.append(name);print('PASS',name)
    return passed
