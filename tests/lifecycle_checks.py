"""Ship-idle, incremental initialization and recoverable lifecycle regressions."""
import struct

U=lambda n:struct.pack('<I',n)
Q=lambda n:struct.pack('<Q',n)
F=lambda n:struct.pack('<f',n)

def run(Scenario,BASE,SOURCE,eagle_state,metrics):
    def resume(s,limit=40):
        for _ in range(limit):
            s.tick()
            if s.state[b'phase']==b'active':return
        raise AssertionError(('did not resume',s.state[b'phase'],s.state[b'status']))

    def metadata_and_boundaries():
        s=Scenario(bad_build=True)
        try:
            s.mem.put(BASE+0x150,U(0x5000000));s.tick()
            assert s.state[b'phase']==b'active' and s.r(33,0xc8,4)==U(103)
        finally:s.close()
        for address,data in ((BASE+0x104,b'\x4c\x01'),(BASE+0x150,U(0x1000000)),(BASE+0x89f1a6,b'\x90')):
            s=Scenario()
            try:
                s.mem.put(address,data);s.tick()
                assert s.state[b'phase']==b'suspended' and not s.mem.writes
            finally:s.close()

    def preparation_frame_budget():
        s=Scenario();per_frame=[]
        try:
            headers={t['p']-28 for t in s.tables};s.mem.reads.clear();s.mem.read_bytes=0
            for frame in range(100):
                before=sum(s.mem.reads.values());old={p:s.mem.reads.get((p,28),0) for p in headers}
                s.frame(1.1 if frame==0 else 1/60)
                per_frame.append(sum(s.mem.reads.values())-before)
                assert sum(s.mem.reads.get((p,28),0)-old[p] for p in headers)<=2
                if s.state[b'phase']==b'active':break
                assert not s.mem.allocations and s.r(33,0xc8,4)==U(0)
            else:raise AssertionError('incremental initialization never completed')
            assert frame>=8 and max(per_frame)<250
            assert len(s.mem.allocations)==1 and s.r(33,0xc8,4)==U(103)
            metrics['preparation_frames']={'frames':frame+1,'maximum_rpm_per_frame':max(per_frame),'rpm_by_frame':per_frame}
        finally:s.close()
        s=Scenario()
        try:
            t=s.tables[0];p=t['p'];capacity=t['row']['nidx']
            donor=bytes.fromhex('29ca6a67b11ca02e')
            source=t['original'].index(donor);entry=t['original'][source:source+16]
            start=int.from_bytes(donor,'little')%capacity
            for i in range(129):s.mem.put(p+((start+i)%capacity)*16,Q(0x12340000+i)+U(0)+U(0))
            s.mem.put(p+((start+129)%capacity)*16,entry)
            s.frame();assert s.state[b'phase']==b'preparing'
            assert s.state[b'repair_draft'][b'next_table']==1 and not s.mem.allocations
            first=s.state[b'repair_draft'][b'probes'][1][b'donor'][b'next']
            assert first==64
            s.frame(1/60)
            assert s.state[b'repair_draft'][b'probes'][1][b'donor'][b'next']==128
            resume(s);assert len(s.mem.allocations)==1 and s.r(33,0xc8,4)==U(103)
        finally:s.close()

    def ship_idle_and_exit():
        for diagnostics in (False,True):
            s=Scenario({'bomb':286},diagnostics=diagnostics)
            try:
                s.mem.put(s.scene+0xac21c,U(1));s.tick()
                assert s.r(33,0xc8,4)==U(103) and s.state[b'phase']==b'active'
                s.mem.reads.clear();s.mem.read_bytes=0;writes=len(s.mem.writes)
                s.lua.execute(b'''config_reads=0;local open=io.open
                    io.open=function(path,mode)
                        if path:match('CarpetBombNative%.cfg$') and mode=='rb' then config_reads=config_reads+1 end
                        return open(path,mode)
                    end''')
                for _ in range(120):s.frame(.05)
                assert (BASE+0x3326650,8) not in s.mem.reads
                assert (BASE+0x347cea8,8) not in s.mem.reads
                assert not s.state[b'cluster_trace'] and not s.state[b'cluster_pending']
                assert len(s.mem.writes)==writes and s.lua.globals()[b'config_reads']<=2
                metrics['ship_idle_6_seconds']={'rpm_calls':sum(s.mem.reads.values()),'bytes':s.mem.read_bytes,
                    'eagle_manager_reads':0,'projectile_system_reads':0,'config_file_reads':s.lua.globals()[b'config_reads']}
                s.mem.put(s.scene+0xac21c,U(4));eagle_state(s);s.tick()
                assert s.state[b'in_mission'] and s.state[b'forward_adjustments']==1
                s.state[b'cluster_pending']=s.lua.table_from({1:s.lua.table()})
                s.mem.put(s.scene+0xac21c,U(1));s.frame(.3)
                assert not s.state[b'in_mission'] and s.state[b'cluster_pending'] is None and s.state[b'cluster_trace'] is None
            finally:s.close()

    def diagnostics_default_off():
        s=Scenario({'bomb':286})
        try:
            s.tick();eagle_state(s);s.tick()
            assert s.state[b'config'][b'diagnostics']==0
            assert not s.state[b'cluster_trace_count'] and not s.state[b'flight_observation_count']
            text=(s.logs/'CarpetBombNative.log').read_text()
            assert 'Cluster trace start' not in text and 'Flight first observation' not in text
            assert s.state[b'forward_adjustments']==1
        finally:s.close()

    def transient_and_competing_writers():
        s=Scenario(carrier_conflict=True)
        try:
            s.tick();assert not s.mem.writes
            s.mem.put(s.address[33]+0xc8,U(0));resume(s)
            assert s.r(33,0xc8,4)==U(103)
            s.mem.put(s.address[103]+0x68,F(77));s.tick();writes=len(s.mem.writes)
            for _ in range(10):s.tick()
            assert len(s.mem.writes)==writes and s.r(103,0x68,4)==F(77)
            assert s.state[b'cleanup_pending']>0
            s.mem.put(s.address[103]+0x68,s.originals[103][0x68:0x6c]);resume(s)
            assert s.r(103,0x68,4)==F(15) and len(s.mem.allocations)==1
        finally:s.close()

    def moved_record_and_projectile():
        for kind in ('record','projectile'):
            s=Scenario()
            try:
                s.tick()
                if kind=='record':
                    old=s.address[103];new=0xc0000000;s.mem.put(new,s.originals[103])
                    s.mem.put(BASE+0x37cb600+103*8,Q(new))
                else:
                    old,raw=s.projectiles[170];new=0xc0000000;s.mem.put(new,raw)
                    s.mem.put(BASE+0x37c7670+170*8,Q(new))
                writes=len(s.mem.writes);resume(s)
                assert not any(old<=p<old+0x190 for p,_ in s.mem.writes[writes:])
                assert s.r(33,0xc8,4)==U(103) and len(s.mem.allocations)==1
                if kind=='record':assert s.mem.read(new+0x50,4)==U(2)
                else:assert s.state[b'projectiles'][170][b'addr']==new
            finally:s.close()

    def moved_component_table():
        s=Scenario()
        try:
            s.tick();t=s.tables[0];new=0xc0000000
            s.mem.put(new-28,s.mem.read(t['p']-28,28));s.mem.put(new,t['original']);s.mem.put(t['slot'],Q(new))
            writes=len(s.mem.writes);resume(s)
            assert s.state[b'phase']==b'active' and len(s.mem.allocations)==1
            assert any(new<=p<new+len(t['original']) for p,_ in s.mem.writes[writes:])
            assert s.r(33,0xc8,4)==U(103)
        finally:s.close()

    def moved_payload_root():
        s=Scenario()
        try:
            s.tick();root=0xc0000000
            for i,t in enumerate(s.tables):
                new=0xd0000000+i*0x100000
                s.mem.put(new-28,s.mem.read(t['p']-28,28));s.mem.put(new,t['original'])
                s.mem.put(root+int(t['row']['root_offset'],16),Q(new))
            s.mem.put(BASE+0x346bf98,Q(root));resume(s)
            assert s.state[b'repair'][b'root']==root and len(s.mem.allocations)==2
            assert s.r(33,0xc8,4)==U(103)
        finally:s.close()

    def menu_retry_without_duplicate_callbacks():
        for failed_step in ('register','callback','set'):
            s=Scenario()
            try:
                s.lua.globals()[b'failed_step']=failed_step.encode()
                s.lua.execute(b'''local options,callbacks,values={},{},{};local failed=false
                    ModOptionsMenu={api=1,version=2};menu_counts={register=0,callback=0}
                    function ModOptionsMenu.register_option(id,spec)
                        if not failed and failed_step=='register' and id=='carpet_bomb_native_uses' then failed=true;return false,'temporary' end
                        assert(not options[id]);options[id]=spec;values[id]=spec.default;menu_counts.register=menu_counts.register+1;return true
                    end
                    function ModOptionsMenu.on_change(id,fn)
                        if not failed and failed_step=='callback' and id=='carpet_bomb_native_uses' then failed=true;return false,'temporary' end
                        assert(not callbacks[id]);callbacks[id]=fn;menu_counts.callback=menu_counts.callback+1;return true
                    end
                    function ModOptionsMenu.get(id)if failed_step=='set' and not failed then return nil end;return values[id]end
                    function ModOptionsMenu.set(id,value)
                        if failed_step=='set' and not failed then failed=true;return false,'temporary' end
                        values[id]=value;return true
                    end''')
                s.tick()
                for _ in range(35):s.tick()
                assert s.state[b'menu_registered'] is True and s.state[b'menu_error'] is None
                assert s.lua.globals()[b'menu_counts'][b'register']==14
                assert s.lua.globals()[b'menu_counts'][b'callback']==14
            finally:s.close()

    def late_loader_and_update():
        s=Scenario(loader=False)
        try:
            s.tick();assert not s.mem.writes and s.state[b'phase']==b'waiting'
            s.lua.execute(b'CowboyBingusModLoader={api=1,open_log=function()end}')
            for _ in range(125):s.tick()
            assert s.state[b'phase']==b'active' and s.r(33,0xc8,4)==U(103)
        finally:s.close()
        s=Scenario(loader=False)
        try:
            s.lua.execute(b'CarpetBombNative=nil;update=nil;CowboyBingusModLoader={api=1,open_log=function()end}')
            state=s.lua.execute(SOURCE);assert state[b'phase']==b'waiting'
            assert s.lua.globals()[b'CarpetBombNative'] is None
            s.lua.execute(b'update=function(dt,marker)return dt,marker,nil,42,nil end')
            s.state=s.lua.execute(SOURCE)
            assert s.tick()==(1.1,b'preserved',None,42,None)
            assert s.state[b'phase']==b'active'
        finally:s.close()

    passed=[]
    for name,fn in [
        ('lifecycle: changed version metadata accepted; wrong architecture, bounds and code rejected',metadata_and_boundaries),
        ('lifecycle: at most two tables and bounded memory reads per preparation frame; publication last',preparation_frame_budget),
        ('lifecycle: ship grant retained with zero aircraft/projectile polling; mission exit drops tracking',ship_idle_and_exit),
        ('lifecycle: production diagnostics default off without disabling forward adjustment',diagnostics_default_off),
        ('lifecycle: transient startup recovers; competing values retained until ownership is safe',transient_and_competing_writers),
        ('lifecycle: moved stratagem/projectile rows revalidate without dereferencing retired records',moved_record_and_projectile),
        ('lifecycle: moved component table repairs missing alias and reuses published private Eagle',moved_component_table),
        ('lifecycle: replaced payload root rebuilds one bounded generation',moved_payload_root),
        ('lifecycle: partial menu registration/binding/sync retries without duplicate callbacks',menu_retry_without_duplicate_callbacks),
        ('lifecycle: late loader/update, retryable marker and callback trailing nil results',late_loader_and_update)]:
        fn();passed.append(name);print('PASS',name)
    return passed
