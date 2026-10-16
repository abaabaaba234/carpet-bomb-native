"""Source-scoped, one-shot fuse adaptation; numerical checks are not gameplay proof."""
import json,math,struct

def run(Scenario,BASE,ROOT,eagle_state):
    U=lambda n:struct.pack('<I',n)
    Q=lambda n:struct.pack('<Q',n)
    F=lambda n:struct.pack('<f',n)
    system=0xa0000000;owners=0xb0000000;owner_index=0xb0001000;owner_rows=0xb0002000
    source=0xc0000000
    fixture=json.loads((ROOT/'tests/fixtures/cluster_ballistics_build25480438.json').read_text())
    def seed(s,count=20,resource=0x6ccb976676ef6cc6):
        manager,objects,states,descriptor=eagle_state(s,attacked=1,resource=resource)
        header=bytearray(0x48)
        struct.pack_into('<Q',header,0x18,owner_index);struct.pack_into('<4I',header,0x20,8,0xffffffff,1,0)
        struct.pack_into('<Q',header,0x38,owner_rows)
        s.mem.put(BASE+0x3326c38,Q(owners));s.mem.put(owners,header)
        s.mem.put(owner_index,(U(0xffffffff)+U(0xffffffff))*8)
        s.mem.put(owner_index+(901%8)*8,U(901)+U(0));s.mem.put(owner_rows,Q(source))
        s.mem.put(BASE+0x347cea8,Q(system));s.mem.put(system+0x30,U(count))
        s.mem.put(system+0x203c,bytes(4096))
        constants=fixture['constants']
        for rva,name in ((0x23c8128,'gravity'),(0x23c65a8,'radius_scale'),(0x23c7d3c,'density'),(0x23c6f1c,'pi'),(0x23c6e28,'half')):
            s.mem.put(BASE+rva,F(constants[name]))
        rows=[]
        for i in range(count):
            metadata=bytearray(0xc8);struct.pack_into('<Q',metadata,0,source)
            struct.pack_into('<2I',metadata,8,417,234);struct.pack_into('<I',metadata,0x80,417)
            physics=bytearray(0x70);struct.pack_into('<3f',physics,0,*fixture['live_cluster']['first_primary_position'])
            struct.pack_into('<3f',physics,12,*fixture['live_cluster']['first_primary_velocity'])
            struct.pack_into('<f',physics,0x34,.3)
            s.mem.put(system+0x203c+i*2,struct.pack('<H',2))
            s.mem.put(system+0x4d040+i*0xc8,metadata);s.mem.put(system+0x3040+i*0x70,physics)
            rows.append((bytes(metadata),bytes(physics)))
        return rows,(manager,objects,states,descriptor)
    def timers(s,n=20):return [struct.unpack('<f',s.mem.read(system+0x3040+i*0x70+0x34,4))[0] for i in range(n)]
    def log(s):return (s.logs/'CarpetBombNative.log').read_text(encoding='utf-8')
    def scenario():
        s=Scenario({'bomb':286,'direction':180,'forward':0});s.tick();return s

    def fixed_quantity_and_unchanged_data():
        s=scenario()
        try:
            rows,flight=seed(s);before=len(s.mem.writes);s.tick()
            assert s.state[b'cluster_fuse_changes']==20
            assert len(s.mem.writes)-before==20 and all(p==system+0x3040+i*0x70+0x34 for i,(p,_) in enumerate(s.mem.writes[before:]))
            assert all(1<t<10 for t in timers(s))
            assert '1 aircraft, 20 primary bombs' in log(s)
            for i,(metadata,physics) in enumerate(rows):
                assert s.mem.read(system+0x4d040+i*0xc8,0xc8)==metadata
                after=s.mem.read(system+0x3040+i*0x70,0x70)
                assert after[:0x34]==physics[:0x34] and after[0x38:]==physics[0x38:]
            for address,raw in s.projectiles.values():assert s.mem.read(address,272)==raw
            before=list(s.mem.writes)
            for _ in range(12):s.tick()
            assert s.mem.writes==before
            s.cfg('enabled=0\n')
            # A completed one-shot fuse setting is consumed by game simulation,
            # like a successful forward-target adjustment; disabling stops new work.
            assert all(t>1 for t in timers(s))
        finally:s.close()
        s=scenario()
        try:
            _,flight=seed(s,60);manager,objects,states,descriptor=flight
            state=s.mem.read(states,0xfc);s.mem.put(manager+0x20,U(3))
            for i in (1,2):
                s.mem.put(objects+i*8,Q(descriptor+i*0x100))
                s.mem.put(descriptor+i*0x100,Q(0x6ccb976676ef6cc6)+U(901+i)+U(902+i))
                s.mem.put(states+i*0xfc,state)
                s.mem.put(owner_index+((901+i)%8)*8,U(901+i)+U(i));s.mem.put(owner_rows+i*8,Q(source))
            s.tick()
            assert s.state[b'cluster_fuse_changes']==60 and '3 aircraft, 60 primary bombs' in log(s)
            assert all(t>1 for t in timers(s,60))
        finally:s.close()

    def scope_and_invalid_batches():
        for mode in ('ordinary','wrong_source','missing_source','incomplete','excess','other_eagle','bad_timer','low','nan','gravity','row_changed'):
            s=scenario()
            try:
                n=19 if mode=='incomplete' else 21 if mode=='excess' else 20
                rows,flight=seed(s,n,0x2ea01cb1676aca29 if mode=='ordinary' else 0x6ccb976676ef6cc6)
                manager,objects,states,descriptor=flight
                if mode=='wrong_source':s.mem.put(owner_rows,Q(source+0x1000))
                if mode=='missing_source':s.mem.put(BASE+0x3326c38,Q(0))
                if mode=='other_eagle':
                    s.mem.put(manager+0x20,U(2));s.mem.put(objects+8,Q(descriptor+0x100))
                    s.mem.put(descriptor+0x100,Q(0x2ea01cb1676aca29)+U(902)+U(903))
                    s.mem.put(owner_index+(902%8)*8,U(902)+U(1));s.mem.put(owner_rows+8,Q(source))
                if mode=='bad_timer':s.mem.put(system+0x3040+0x34,F(.8))
                if mode=='low':s.mem.put(system+0x3040+8,F(20))
                if mode=='nan':s.mem.put(system+0x3040+8,F(float('nan')))
                if mode=='gravity':s.mem.put(BASE+0x23c8128,F(-20))
                if mode=='row_changed':s.mem.put(s.projectiles[286][0]+0x34,F(1))
                before=list(s.mem.writes);s.tick()
                assert not s.state[b'cluster_fuse_changes'],mode
                if mode=='row_changed':assert not any(system<=p<system+0x100000 for p,_ in s.mem.writes[len(before):])
                else:assert s.mem.writes==before,mode
                assert s.state[b'phase']==(b'stopped' if mode=='row_changed' else b'active')
            finally:s.close()

    def concurrency_and_failure():
        for mode in ('metadata','owner','timer','partial'):
            s=scenario()
            try:
                rows,_=seed(s);address=system+0x3040+10*0x70+0x34
                if mode=='partial':s.mem.fail_address=address
                else:
                    original=s.mem.read;triggered=False
                    def race(p,n):
                        nonlocal triggered
                        if p==system+0x3040+19*0x70 and n==0x70 and not triggered:
                            triggered=True
                            if mode=='metadata':s.mem.put(system+0x4d040+10*0xc8+8,U(999))
                            elif mode=='owner':s.mem.put(owner_rows,Q(source+0x1000))
                            else:s.mem.put(address,F(.2))
                        return original(p,n)
                    s.mem.read=race
                before=list(s.mem.writes);s.tick()
                if mode=='partial':
                    assert s.state[b'phase']==b'stopped' and 'Cluster fuse write failed' in log(s)
                    assert all(abs(t-.3)<1e-6 for t in timers(s))
                    assert s.state[b'cleanup_complete'] is True
                else:
                    s.mem.read=original
                    assert s.mem.writes==before and not s.state[b'cluster_fuse_changes']
            finally:s.close()

    def numerical_cross_check():
        s=scenario()
        try:
            seed(s);s.tick();duration=timers(s)[0]
            z=fixture['live_cluster']['first_primary_position'][2]
            v=fixture['live_cluster']['first_primary_velocity'];y=[math.hypot(v[0],v[1]),v[2],z]
            c=fixture['constants'];k=(25*c['radius_scale'])**2*c['pi']*c['half']*.5*c['density']/100
            def derivative(a):
                speed=math.hypot(a[0],a[1]);return [-k*speed*a[0],c['gravity']-k*speed*a[1],a[1]]
            # Independent RK4 solver, rather than copying the Lua midpoint loop.
            t=0
            while t<duration:
                h=min(.01,duration-t);a=derivative(y)
                b=derivative([v+h*d/2 for v,d in zip(y,a)])
                cc=derivative([v+h*d/2 for v,d in zip(y,b)])
                d=derivative([v+h*e for v,e in zip(y,cc)])
                y=[v+h*(aa+2*bb+2*ccc+dd)/6 for v,aa,bb,ccc,dd in zip(y,a,b,cc,d)];t+=h
            assert abs(y[2]-(6+30))<.5
        finally:s.close()

    passed=[]
    for name,fn in [
        ('cluster fuse: exactly 20 source-linked native primaries, one write each, unchanged positions/damage/bomblets and no rearming',fixed_quantity_and_unchanged_data),
        ('cluster fuse: ordinary Eagles, ambiguous sources, missing/incomplete/excess batches and invalid ballistics fail closed',scope_and_invalid_batches),
        ('cluster fuse: concurrent metadata/source/timer changes and partial-write rollback',concurrency_and_failure),
        ('cluster fuse: captured primary state reaches chosen burst elevation in independent RK4 check',numerical_cross_check)]:
        fn();passed.append(name);print('PASS',name)
    return passed
