"""Run the shipped Lua against sanitized real StratagemInfo records in LuaJIT."""
from pathlib import Path
import json,struct,tempfile,re,zipfile,sys
from lupa import luajit21
ROOT=Path(__file__).resolve().parents[1];SOURCE=(ROOT/'src/core.lua').read_bytes();BASE=0x180000000
Q=lambda x:struct.pack('<Q',x);U=lambda x:struct.pack('<I',x);F=lambda x:struct.pack('<f',x)
class Memory:
    def __init__(self):self.pages={};self.writes=[];self.denied=False;self.fail_once=False;self.protection={};self.fail_alias=None;self.fail_address=None;self.cursor=0x80000000;self.flushes=[];self.fail_flush_once=False;self.fail_protect_once=None;self.fail_restore_once=None;self.allocations=[];self.near_regions=[];self.alloc_attempts=[];self.fail_hint_once=None
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
    def alloc(self,n,hint=0):
        p=int(hint) if hint else self.cursor
        if hint:
            self.alloc_attempts.append(p)
            if self.fail_hint_once==p:self.fail_hint_once=None;return 0
        if not hint:self.cursor+=(n+4095)&~4095
        size=(n+4095)&~4095;self.allocations.append((p,size));self.put(p,bytes(size));return p
    def query(self,p):
        for start,size in self.allocations:
            if start<=p<start+size:return struct.pack('<QQIIQIIII',start,start,4,0,size,0x1000,self.page_protection(p),0x20000,0)
        for start,end,state in self.near_regions:
            if start<=p<end:return struct.pack('<QQIIQIIII',start,0,0,0,end-start,state,0,0,0)
        if p>=BASE+0x4744000:start,end,state=BASE+0x4744000,0x7fffffff0000,0x10000
        elif 0x100000000<=p<BASE:start,end,state=0x100000000,BASE,0x10000
        else:start,end,state=0x10000,0x7fffffff0000,0x1000
        return struct.pack('<QQIIQIIII',start,start,4,0,end-start,state,self.page_protection(p),self.page_kind(p),0)
    def protect(self,p,n,protection):
        if self.fail_protect_once==p:self.fail_protect_once=None;return 0
        if self.fail_restore_once==p and protection==0x20:self.fail_restore_once=None;return 0
        for page in range(p>>12,((p+n-1)>>12)+1):self.protection[page]=protection
        return 1
    def page_protection(self,p):return self.protection.get(int(p)>>12,0x20 if BASE<=p<BASE+0x4744000 else 4)
    def page_kind(self,p):return 0x1000000 if BASE<=p<BASE+0x4744000 else 0x20000
    def flush(self,p,n):
        self.flushes.append((p,n))
        if self.fail_flush_once:self.fail_flush_once=False;return 0
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
        self.projectiles={}
        for row in json.loads((ROOT/'tests/fixtures/projectiles_build25480438.json').read_text())['records']:
            t=row['type'];address=0x58000000+t*0x1000;raw=bytes.fromhex(row['record_hex'])
            self.mem.put(address,raw);self.mem.put(BASE+0x37c7670+t*8,Q(address));self.projectiles[t]=(address,raw)
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
        g[b'pyalloc']=lambda n,hint:self.mem.alloc(int(n),int(hint));g[b'pyprotection']=lambda p:self.mem.page_protection(int(p))
        g[b'pyprotect']=lambda p,n,v:self.mem.protect(int(p),int(n),int(v))
        g[b'pykind']=lambda p:self.mem.page_kind(int(p));g[b'pyflush']=lambda p,n:self.mem.flush(int(p),int(n))
        g[b'pyquery']=lambda p:self.mem.query(int(p))
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
            local s=pyquery(tonumber(real.cast('uintptr_t',p)));if not s then return 0 end
            real.copy(b,s,n);if pydenied() then real.cast('uint32_t *',b+36)[0]=32 end;return n end
          kernel.VirtualProtect=function(p,n,v,old)
            local a=tonumber(real.cast('uintptr_t',p));old[0]=pyprotection(a);return pyprotect(a,n,v) end
          kernel.VirtualAlloc=function(p,n,kind,protection)return real.cast('void *',pyalloc(n,tonumber(real.cast('uintptr_t',p))))end
          kernel.FlushInstructionCache=function(_,p,n)return pyflush(tonumber(real.cast('uintptr_t',p)),n)end
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
        assert s.r(3,0,0x190)==s.originals[3]
        assert not s.mem.flushes and s.state[b'quantity'] is None
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

def bomb_settings():
    for bomb in (170,192,239):
        s=Scenario({'bomb':bomb,'uses':4,'cooldown':10,'rearm':30})
        try:
            s.tick();assert s.state[b'phase']==b'active'
            shadow=int(s.state[b'repair'][b'eagle'][b'table'])
            assert s.mem.read(shadow+1992+24,4)==U(bomb)
            assert s.mem.read(shadow+1992+16,4)==U(6) and s.mem.read(shadow+1992+0x3c,4)==F(120)
            assert s.r(103,0xa8,8)==s.originals[3 if bomb==239 else 18][0xa8:0xb0]
            assert s.r(103,0x50,4)==U(4) and s.r(103,0x68,4)==F(10) and s.r(49,0x68,4)==F(30)
            for t in (3,18,38):assert s.r(t,0,400)==s.originals[t]
            for address,raw in s.projectiles.values():assert s.mem.read(address,272)==raw
            eagle=next(t for t in s.tables if t['row']['name']=='EagleComponentData')
            assert s.mem.read(shadow+320,1672)==eagle['original'][320:]
            assert not any(BASE<=address<BASE+0x4744000 for address,_ in s.mem.writes)
            s.cfg('enabled=0\n')
            assert s.r(33,0,400)==s.originals[33] and s.r(103,0,400)==s.originals[103]
            assert s.mem.read(shadow+1992+24,4)==U(170)
        finally:s.close()

def bomb_reload_and_fixed_quantity():
    for count in (5,10,20,30,40,80):
        s=Scenario({'bomb':192,'bomb_count':count})
        try:
            s.tick();assert s.state[b'config'][b'bomb_count']==20
            s.cfg(f'bomb=239\nbomb_count={count}\nuses=3\ncooldown=60\nforward=120\n')
            shadow=int(s.state[b'repair'][b'eagle'][b'table'])
            assert s.state[b'phase']==b'active' and s.mem.read(shadow+1992+24,4)==U(239)
            assert s.state[b'config'][b'bomb_count']==20
            assert s.mem.read(BASE+0x8a4d88,11)==bytes.fromhex('ffc383fb140f82adfdffff')
            assert s.mem.read(BASE+0x8a4b25,9)==bytes.fromhex('f3440f1035ae2ab201')
            assert not s.mem.flushes and not s.mem.alloc_attempts
            assert not any(BASE<=address<BASE+0x4744000 for address,_ in s.mem.writes)
            for config in ('bomb=999\n',):
                s.cfg(config);assert s.mem.read(shadow+1992+24,4)==U(239)
            s.cfg('enabled=0\nbomb_count=10\n')
            assert s.state[b'phase']==b'disabled' and s.r(33,0xc8,4)==U(0)
        finally:s.close()
    assert b'FlushInstructionCache' not in SOURCE and b'prepare_quantity' not in SOURCE

def eagle_state(s,current=(-400,0,120),velocity=(200,0,-20),resource=0x6ccb976676ef6cc6,firing=0,attacked=0):
    manager,objects,states,descriptor=0x90000000,0x90001000,0x90002000,0x90003000
    header=bytearray(0x60);struct.pack_into('<I',header,0x20,1);struct.pack_into('<Q',header,0x48,objects);struct.pack_into('<Q',header,0x58,states)
    state=bytearray(0xfc);struct.pack_into('<3f',state,0x54,0,0,6);struct.pack_into('<3f',state,0x78,*current);struct.pack_into('<3f',state,0xd4,*velocity);state[0x70]=firing;state[0x71]=attacked
    s.mem.put(BASE+0x3326650,Q(manager));s.mem.put(manager,header);s.mem.put(objects,Q(descriptor));s.mem.put(descriptor,Q(resource)+U(901)+U(902));s.mem.put(states,state)
    return manager,objects,states,descriptor

def original_targets_preserved():
    # Old presets/configurations must not reactivate the removed target adjustment.
    for bomb in (170,192,239):
        s=Scenario({'bomb':bomb,'forward':160})
        try:
            manager,objects,states,descriptor=eagle_state(s)
            original=s.mem.read(states,0xfc)
            s.tick();assert s.state[b'phase']==b'active'
            for value in ('120','-1','301','10.5','manager'):
                s.cfg(f'forward={value}\nuses=5\ncooldown=15\n')
                assert s.state[b'config'][b'forward'] is None
                assert s.mem.read(states,0xfc)==original
                assert s.r(103,0x50,4)==U(5) and s.r(103,0x68,4)==F(15)
            for _ in range(5):s.tick()
            assert s.mem.read(states,0xfc)==original
            assert not any(states<=address<states+0xfc for address,_ in s.mem.writes)
            assert s.tick()==(1.1,b'preserved',42)
        finally:s.close()
    assert b'forward' not in SOURCE and b'0x3326650' not in SOURCE

def package():
    sys.path.insert(0,str(ROOT/'tools'));from build import build,murmur64
    from preset_bytecode import validate_with_lupa
    path=build();counts={}
    with zipfile.ZipFile(path) as z:
        manifest=json.loads(z.read('manifest.json').decode('ascii'));assert len(manifest['Options'])==6
        assert '每次使用之间' in manifest['Options'][2]['Name']
        assert '所有携带的飞鹰战备共用' in manifest['Options'][3]['Description']
        assert '200 kg' in manifest['Options'][4]['SubOptions'][1]['Name'] and '500 kg' in manifest['Options'][4]['SubOptions'][2]['Name']
        assert [x['Name'] for x in manifest['Options'][5]['SubOptions']]==['1x（每架 20 枚）']
        assert not any(name.startswith('Options/forward/') for name in z.namelist())
        assert all('前移' not in option['Name'] for option in manifest['Options'])
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
        assert counts=={'uses':9,'cooldown':10,'rearm':13,'bomb':3,'bomb_count':1}
        assert len({murmur64(('mods/carpet_bomb_native/'+a).encode()) for a in counts})==5
        for option in manifest['Options']:
            for item in option.get('SubOptions',[option]):
                assert all(any(name.startswith(folder+'/') for name in z.namelist()) for folder in item['Include'])
    print('Validated 36 independent preset modules; 3510 selectable combinations and native grant archive.')
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
    ('all three bomb identities/resources, unchanged original Eagles/projectiles and disable restoration',bomb_settings),
    ('bomb reload, fixed original quantity, ignored legacy ratios and no executable writes',bomb_reload_and_fixed_quantity),
    ('original aircraft targets preserved and legacy forward options ignored',original_targets_preserved),
    ('manager archives and 36 presets with 3510 selectable combinations',package)]:
    fn();passed.append(name);print('PASS',name)
result_path=ROOT/'validation/offline_report.json'
result_path.write_text(json.dumps({'version':'0.5.2','game_build':25480438,'tests_passed':passed,
  'preset_combinations':3510,'preset_modules_checked':36,'in_game_loader_verified':False,'default_carry_verified':False,
  'in_game_bombing_verified':False,'multiplayer_verified':False,'status':'OFFLINE_PASSED',
  'previous_version':{'version':'0.1.0','default_carry_verified':True,'battlefield_test':'CRASHED: missing EagleComponent for native payload; removed'}},indent=2),encoding='utf-8',newline='\n')
