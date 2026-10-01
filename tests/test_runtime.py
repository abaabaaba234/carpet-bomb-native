"""Run the shipped Lua against sanitized real StratagemInfo records in LuaJIT."""
from pathlib import Path
import json,struct,tempfile,re,zipfile,sys
from lupa import luajit21
ROOT=Path(__file__).resolve().parents[1];SOURCE=(ROOT/'src/core.lua').read_bytes();BASE=0x180000000
Q=lambda x:struct.pack('<Q',x);U=lambda x:struct.pack('<I',x);F=lambda x:struct.pack('<f',x)
class Memory:
    def __init__(self):self.pages={};self.writes=[];self.denied=False;self.fail_once=False;self.protection={};self.fail_alias=None;self.fail_address=None;self.cursor=0x80000000
    def put(self,p,b):
        for i,v in enumerate(b):self.pages.setdefault((p+i)>>12,bytearray(4096))[(p+i)&4095]=v
    def read(self,p,n):
        b=bytearray()
        for i in range(n):
            page=self.pages.get((p+i)>>12)
            if page is None:return None
            b.append(page[(p+i)&4095])
        return bytes(b)
    def write(self,p,b):
        self.writes.append((p,b))
        if self.fail_address==p:
            self.fail_address=None;self.put(p,b[:max(1,len(b)-1)]);return False
        if self.fail_alias is not None and 0x61000000<=p<0x70000000:
            self.fail_alias-=1
            if self.fail_alias==0:self.fail_alias=None;self.put(p,b[:max(1,len(b)//2)]);return False
        if self.fail_once:self.fail_once=False;self.put(p,b[:max(1,len(b)//2)]);return False
        self.put(p,b);return True
    def alloc(self,n):
        p=self.cursor;self.cursor+=(n+4095)&~4095;self.put(p,bytes((n+4095)&~4095));return p
    def protect(self,p,n,protection):
        for page in range(p>>12,((p+n-1)>>12)+1):self.protection[page]=protection
        return 1
class Scenario:
    def __init__(self,options=None,bad_build=False,carrier_conflict=False):
        self.temp=tempfile.TemporaryDirectory(prefix='.run-',dir=ROOT/'tests');self.local=Path(self.temp.name)
        self.logs=self.local/'CowboyBingus/Helldivers2/Logs';self.logs.mkdir(parents=True)
        self.mem=Memory();self.lua=luajit21.LuaRuntime(encoding=None);self.address={};self.originals={}
        dos=bytearray(0x1000);dos[:2]=b'MZ';struct.pack_into('<I',dos,60,0x100);dos[0x100:0x104]=b'PE\0\0'
        struct.pack_into('<I',dos,0x108,0 if bad_build else 0x6ab3b43f);struct.pack_into('<I',dos,0x150,0x4744000)
        self.mem.put(BASE,dos)
        for r,h in re.findall(rb"\{(0x[0-9a-f]+),'([0-9a-f]+)'\}",SOURCE):self.mem.put(BASE+int(r,16),bytes.fromhex(h.decode()))
        for row in json.loads((ROOT/'tests/fixtures/stratagems_build25480438.json').read_text()):
            t=row['type'];a=0x20000000+t*0x1000;raw=bytes.fromhex(row['record_hex'])
            self.mem.put(struct.unpack_from('<Q',raw,0x10)[0],row['title'].encode()+b'\0'*160)
            payload=struct.unpack_from('<Q',raw,0x98)[0]
            if row['payload']:self.mem.put(payload,b''.join(Q(int(h,16)) for h in row['payload']))
            np=0x40000000+t*0x1000;self.mem.put(np,row['internal_name'].encode()+b'\0'*64)
            self.mem.put(BASE+0x21d4aa0+t*8,Q(np));self.mem.put(BASE+0x37cb600+t*8,Q(a))
            self.mem.put(a,raw);self.address[t]=a;self.originals[t]=raw
        if carrier_conflict:self.mem.put(self.address[33]+0xc8,U(18))
        self.root=0x60000000;self.tables=[];self.mem.put(BASE+0x346bf98,Q(self.root))
        for i,row in enumerate(json.loads((ROOT/'tests/fixtures/payload_tables_build25480438.json').read_text())):
            p=0x61000000+i*0x100000;slot=self.root+int(row['root_offset'],16)
            header=struct.pack('<I4sIIIII',row['type_hash'],b'LDLD',1,row['type_hash'],row['size'],1,0)
            index=bytes.fromhex(row['index_hex']);raw=bytes.fromhex(row['eagle_data_hex']) or index
            self.mem.put(p-28,header);self.mem.put(p,raw);self.mem.put(slot,Q(p))
            self.tables.append({'slot':slot,'p':p,'row':row,'original':raw})
        g=self.lua.globals();g[b'pyread']=lambda p,n:self.mem.read(int(p),int(n));g[b'pywrite']=lambda p,b:self.mem.write(int(p),bytes(b))
        g[b'pydenied']=lambda:self.mem.denied;g[b'localpath']=str(self.local).encode()
        g[b'pyalloc']=lambda n:self.mem.alloc(int(n));g[b'pyprotection']=lambda p:self.mem.protection.get(int(p)>>12,4)
        g[b'pyprotect']=lambda p,n,v:self.mem.protect(int(p),int(n),int(v))
        g[b'preset']=self.lua.table_from({k.encode():v for k,v in (options or {}).items()})
        self.lua.execute(b'''
          local real=require('ffi');local ffi={};for k,v in pairs(real)do ffi[k]=v end
          ffi.cast=function(t,v)if type(v)=='function' then return v end;return real.cast(t,v)end
          local kernel={GetCurrentProcess=function()return real.cast('void *',1)end,
            GetModuleHandleA=function()return real.cast('void *',0x180000000)end}
          kernel.ReadProcessMemory=function(_,p,b,n,count)
            local s=pyread(tonumber(real.cast('uintptr_t',p)),n)
            if not s then count[0]=0;return 0 end;real.copy(b,s,n);count[0]=n;return 1 end
          kernel.WriteProcessMemory=function(_,p,b,n,count)
            local ok=pywrite(tonumber(real.cast('uintptr_t',p)),real.string(b,n));count[0]=ok and n or 0;return ok and 1 or 0 end
          kernel.VirtualQuery=function(p,b,n)
            real.fill(b,n,0);real.cast('uint64_t *',b)[0]=0x10000;real.cast('uint64_t *',b+24)[0]=0x7fffffff0000
            real.cast('uint32_t *',b+32)[0]=0x1000;real.cast('uint32_t *',b+36)[0]=pydenied() and 32 or pyprotection(tonumber(real.cast('uintptr_t',p)))
            real.cast('uint32_t *',b+40)[0]=0x20000;return n end
          kernel.VirtualProtect=function(p,n,v,old)
            local a=tonumber(real.cast('uintptr_t',p));old[0]=pyprotection(a);return pyprotect(a,n,v) end
          kernel.VirtualAlloc=function(_,n,kind,protection)return real.cast('void *',pyalloc(n))end
          ffi.load=function()return kernel end
          local old=require
          require=function(name)
            if name=='ffi' then return ffi end
            local axis=name:match('^mods/carpet_bomb_native/(.+)$')
            if axis then if preset[axis]~=nil then return {value=preset[axis]} end;error('not installed')end
            return old(name)
          end
          local getenv=os.getenv;os.getenv=function(k)if k=='LOCALAPPDATA' then return localpath end;return getenv(k)end
          print=function()end;calls=0;update=function(dt,extra)calls=calls+1;return dt,extra,42 end
        ''')
        self.state=self.lua.eval(b'function(s)return assert(loadstring(s,"@core"))()end')(SOURCE)
    def tick(self):return self.lua.eval(b'function()return update(1.1,"preserved")end')()
    def cfg(self,text):(self.logs/'CarpetBombNative.cfg').write_text(text);self.tick()
    def r(self,t,o,n):return self.mem.read(self.address[t]+o,n)
    def close(self):self.lua=None;self.temp.cleanup()
def defaults():
    s=Scenario()
    try:
        assert s.tick()==(1.1,b'preserved',42) and s.state[b'phase']==b'active'
        assert s.r(33,0xc8,4)==U(103)
        expected=s.originals[33][:0xc8]+U(103)+s.originals[33][0xcc:]
        assert s.r(33,0,0x190)==expected
        assert s.r(103,0x50,4)==U(2) and s.r(103,0x68,4)==F(15)
        assert s.r(49,0,0x190)==s.originals[49]
        assert not any(s.address[49]<=p<s.address[49]+0x190 for p,_ in s.mem.writes)
        for off,n in ((0,16),(0x40,16),(0x98,16),(0xcc,4)):
            assert s.r(103,off,n)==s.originals[103][off:off+n]
        for off,n in ((0x70,4),(0x94,4),(0xa8,8),(0xc8,4),(0x104,4)):
            assert s.r(103,off,n)==s.originals[18][off:off+n]
        repair=s.state[b'repair'];assert repair and len(repair[b'plan'])==18
        eagle=next(t for t in s.tables if t['row']['name']=='EagleComponentData')
        shadow=struct.unpack('<Q',s.mem.read(eagle['slot'],8))[0]
        assert shadow!=eagle['p']
        assert s.mem.read(shadow+320,1672)==eagle['original'][320:]
        assert s.mem.read(shadow+1992+16,4)==U(6) and s.mem.read(shadow+1992+24,4)==U(170)
        assert s.mem.read(shadow+1992+0x3c,4)==F(120)
        n=len(s.mem.writes);s.tick();assert len(s.mem.writes)==n
        s.cfg('enabled=0\n');assert s.state[b'phase']==b'disabled'
        assert s.r(33,0,0x190)==s.originals[33] and s.r(103,0,0x190)==s.originals[103]
        assert struct.unpack('<Q',s.mem.read(eagle['slot'],8))[0]==shadow # Live aliases remain safe until restart.
    finally:s.close()
def settings():
    s=Scenario({'uses':-1,'cooldown':15})
    try:
        s.tick();assert s.r(103,0x50,4)==U(0xffffffff) and s.r(103,0x68,4)==F(15)
        for off,n in ((0,16),(0x40,16),(0x98,16),(0xcc,4)):
            assert s.r(103,off,n)==s.originals[103][off:off+n]
        s.cfg('uses=3\ncooldown=30\n');assert s.r(103,0x50,4)==U(3) and s.r(103,0x68,4)==F(30)
        s.cfg('uses=999\n');assert s.r(103,0x50,4)==U(3)
        s.cfg('enabled=0\n');assert s.r(103,0,0x190)==s.originals[103] and s.r(33,0,0x190)==s.originals[33]
    finally:s.close()
def refusal():
    for kwargs,deny in (({'bad_build':True},False),({'carrier_conflict':True},False),({},True)):
        s=Scenario(**kwargs);s.mem.denied=deny
        try:s.tick();assert s.state[b'phase']==b'stopped' and not s.mem.writes
        finally:s.close()
def rearm_settings():
    s=Scenario({'uses':4,'cooldown':10,'rearm':30})
    try:
        s.tick();assert s.state[b'phase']==b'active'
        assert s.r(103,0x50,4)==U(4) and s.r(103,0x68,4)==F(10)
        original=s.originals[49]
        assert s.r(49,0,0x190)==original[:0x68]+F(30)+original[0x6c:]
        assert s.r(18,0,0x190)==s.originals[18]
        s.cfg('rearm=-1\n');assert s.r(49,0,0x190)==original
        # Relinquish rearm after restoring it, then tolerate another mod's value.
        s.mem.put(s.address[49]+0x68,F(77));s.tick()
        assert s.state[b'phase']==b'active' and s.r(49,0x68,4)==F(77)
        s.mem.put(s.address[49]+0x68,original[0x68:0x6c])
        s.cfg('rearm=0\n');assert s.r(49,0x68,4)==F(0)
        s.cfg('rearm=-2\n');assert s.r(49,0x68,4)==F(0)
        s.cfg('rearm=1801\n');assert s.r(49,0x68,4)==F(0)
        s.cfg('rearm=1800\n');assert s.r(49,0x68,4)==F(1800)
        s.cfg('enabled=0\n')
        assert s.r(49,0,0x190)==original
        assert s.r(103,0,0x190)==s.originals[103] and s.r(33,0,0x190)==s.originals[33]
    finally:s.close()
def rearm_conflicts():
    for mode in ('default','custom','stale'):
        s=Scenario({'rearm':-1 if mode=='default' else 30})
        try:
            s.tick();n=len(s.mem.writes)
            if mode=='stale':s.mem.put(BASE+0x37cb600+49*8,Q(0x77770000))
            else:s.mem.put(s.address[49]+0x68,F(77))
            s.tick()
            if mode=='default':
                assert s.state[b'phase']==b'active' and s.r(49,0x68,4)==F(77)
                s.cfg('rearm=30\n')
                assert s.state[b'phase']==b'stopped' and s.r(49,0x68,4)==F(77)
            else:
                assert s.state[b'phase']==b'stopped'
                assert s.r(33,0,0x190)==s.originals[33] and s.r(103,0,0x190)==s.originals[103]
                if mode=='custom':assert s.r(49,0x68,4)==F(77)
                else:assert not any(s.address[49]<=p<s.address[49]+0x190 for p,_ in s.mem.writes[n:])
        finally:s.close()
def rearm_partial():
    s=Scenario({'rearm':30});s.mem.fail_address=s.address[49]+0x68
    try:
        s.tick();assert s.state[b'phase']==b'stopped'
        assert s.r(49,0,0x190)==s.originals[49]
        assert s.r(103,0,0x190)==s.originals[103] and s.r(33,0,0x190)==s.originals[33]
    finally:s.close()
def partial():
    s=Scenario({'uses':3,'cooldown':15});s.mem.fail_alias=3
    try:
        s.tick();assert s.state[b'phase']==b'stopped'
        assert s.r(33,0,0x190)==s.originals[33] and s.r(103,0,0x190)==s.originals[103]
        for t in s.tables:
            assert s.mem.read(t['p'],len(t['original']))==t['original'] and s.mem.read(t['slot'],8)==Q(t['p'])
    finally:s.close()
def conflict():
    s=Scenario({'uses':3,'cooldown':15})
    try:
        s.tick();s.mem.put(s.address[103]+0x68,F(77));s.tick()
        assert s.state[b'phase']==b'stopped' and s.r(103,0x68,4)==F(77)
        assert s.r(33,0,0x190)==s.originals[33] and s.r(103,0x50,4)==s.originals[103][0x50:0x54]
    finally:s.close()
def stale():
    s=Scenario()
    try:
        s.tick();s.mem.put(BASE+0x37cb600+33*8,Q(0x77770000));n=len(s.mem.writes);s.tick()
        assert s.state[b'phase']==b'stopped'
        assert not any(s.address[33]<=p<s.address[33]+0x190 for p,_ in s.mem.writes[n:])
        assert s.r(103,0,0x190)==s.originals[103]
    finally:s.close()
def aliases():
    for kind in ('header','donor','existing','readonly'):
        s=Scenario()
        try:
            t=s.tables[0];capacity=t['row']['nidx'];native=0x6ccb976676ef6cc6;donor=0x2ea01cb1676aca29
            if kind=='header':s.mem.put(t['p']-28,U(0))
            elif kind=='donor':
                o=t['original'].find(Q(donor));s.mem.put(t['p']+o,bytes(16))
            elif kind=='existing':
                o=(native%capacity)*16
                while s.mem.read(t['p']+o,8)!=bytes(8):o=(o+16)%(capacity*16)
                s.mem.put(t['p']+o,Q(native)+bytes(8))
            else:
                for table in s.tables:s.mem.protect(table['p'],len(table['original']),2)
            s.tick()
            if kind=='readonly':
                assert s.state[b'phase']==b'active'
                for table in s.tables:assert s.mem.protection[table['p']>>12]==2
                for entry in s.state[b'repair'][b'plan'].values():
                    if entry[b'address']==entry[b'slot']:continue
                    assert s.mem.read(int(entry[b'address']),8)==Q(native)
                s.mem.put(s.tables[1]['slot'],Q(0x77770000));s.tick()
                assert s.state[b'phase']==b'stopped' and s.r(33,0xc8,4)==U(0)
            else:assert s.state[b'phase']==b'stopped' and s.r(33,0xc8,4)==U(0)
        finally:s.close()
def late_tables():
    s=Scenario();t=s.tables[-1]
    try:
        s.mem.put(t['slot'],Q(0));s.tick()
        assert s.state[b'phase']==b'waiting' and s.r(33,0xc8,4)==U(0)
        s.mem.put(t['slot'],Q(t['p']));s.tick()
        assert s.state[b'phase']==b'active' and s.r(33,0xc8,4)==U(103)
    finally:s.close()
def package():
    sys.path.insert(0,str(ROOT/'tools'));from build import build,murmur64
    from preset_bytecode import validate_with_lupa
    path=build();counts={}
    with zipfile.ZipFile(path) as z:
        manifest=json.loads(z.read('manifest.json').decode('ascii'));assert len(manifest['Options'])==4
        assert '每次使用之间' in manifest['Options'][2]['Name']
        assert '所有携带的飞鹰战备共用' in manifest['Options'][3]['Description']
        for name in z.namelist():
            if not re.search(r'\.patch_\d+$',name):continue
            b=z.read(name);assert struct.unpack_from('<4I',b)==(0xf0000011,1,1,0)
            assert len(b)>=4096 and len(b)%16==0
            assert struct.unpack_from('<Q',b,32)[0]==len(b)
            h,kind,off,*_=struct.unpack_from('<7Q6I',b,104);size,version=struct.unpack_from('<II',b,off)
            source=b[off+8:off+8+size];assert kind==0xa14e8dfa2cd117e2 and version==2
            if name.startswith('Core/'):
                assert source==SOURCE and h==murmur64(b'mods/carpet_bomb_native/core')
            else:
                axis=name.split('/')[1];assert h==murmur64(('mods/carpet_bomb_native/'+axis).encode())
                choice=name.split('/')[2];value=-1 if choice in ('unlimited','vanilla') else int(choice)
                assert source.startswith(b'\x1bLJ\x02\x02')
                validate_with_lupa(value,source)
                counts[axis]=counts.get(axis,0)+1
        assert counts=={'uses':9,'cooldown':10,'rearm':13}
        assert len({murmur64(('mods/carpet_bomb_native/'+a).encode()) for a in counts})==3
        for option in manifest['Options']:
            for item in option.get('SubOptions',[option]):
                assert all(any(name.startswith(folder+'/') for name in z.namelist()) for folder in item['Include'])
    print('Validated 32 independent preset modules; 1170 selectable combinations and native grant archive.')
passed=[]
for name,fn in [('default carrying, repaired payload, original Eagle rows preserved and disable restoration',defaults),
    ('independent charges/cooldown, preserved native identity and configuration validation',settings),
    ('unsupported build, existing carrier link and executable pages refused',refusal),
    ('partial write rollback',partial),('competing writer preservation and restoration',conflict),
    ('stale carrier identity refused',stale),('payload alias refusal, read-only protection restoration and competing table writer',aliases),
    ('late game datalibrary initialization retries without configuration edits',late_tables),
    ('independent rearm setting, vanilla restoration, zero/max values and disable restoration',rearm_settings),
    ('default rearm non-interference, competing rearm writer and stale rearm record refusal',rearm_conflicts),
    ('partial rearm write rolls back native grant transaction',rearm_partial),
    ('manager archives and 32 presets with 1170 selectable combinations',package)]:
    fn();passed.append(name);print('PASS',name)
result_path=ROOT/'validation/offline_report.json'
result_path.write_text(json.dumps({'version':'0.4.0','game_build':25480438,'tests_passed':passed,
  'preset_combinations':1170,'preset_modules_checked':32,'in_game_loader_verified':False,'default_carry_verified':False,
  'in_game_bombing_verified':False,'multiplayer_verified':False,'status':'OFFLINE_PASSED',
  'previous_version':{'version':'0.1.0','default_carry_verified':True,'battlefield_test':'CRASHED: missing EagleComponent for native payload; removed'}},indent=2))
