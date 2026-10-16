"""Bounded read-only projectile traces; never model this as a physics/gameplay test."""
import struct

def run(Scenario,BASE,eagle_state):
    U=lambda n:struct.pack('<I',n)
    Q=lambda n:struct.pack('<Q',n)
    system=0xa0000000
    def setup(s,counter=1):
        s.mem.put(BASE+0x347cea8,Q(system))
        s.mem.put(system+0x30,U(counter))
        s.mem.put(system+0x203c,bytes(4096))
    def slot(s,index,kind='primary',active=True):
        metadata=bytearray(0xc8)
        struct.pack_into('<Q',metadata,0,0x1122334455667788)
        struct.pack_into('<2I',metadata,8,1234,234 if kind=='primary' else 32)
        struct.pack_into('<2I',metadata,0x7c,0 if kind=='primary' else 162,417 if kind=='primary' else 0)
        physics=bytearray(0x70)
        struct.pack_into('<3f',physics,0,-700,50,120)
        struct.pack_into('<3f',physics,12,200,0,-30)
        struct.pack_into('<f',physics,0x18,.75)
        struct.pack_into('<f',physics,0x34,.25)
        s.mem.put(system+0x203c+index*2,struct.pack('<H',2 if active else 0))
        s.mem.put(system+0x4d040+index*0xc8,metadata)
        s.mem.put(system+0x3040+index*0x70,physics)
        return bytes(metadata),bytes(physics)
    def log(s):return (s.logs/'CarpetBombNative.log').read_text(encoding='utf-8')
    def start(s):eagle_state(s,attacked=1);s.tick()

    def read_only_and_late_selection():
        s=Scenario({'bomb':286,'forward':80,'direction':180})
        try:
            s.tick();setup(s,2);a=slot(s,0);b=slot(s,1,'secondary')
            # The original first-flight log cap must not suppress the cluster trace.
            s.state[b'flight_observation_count']=12
            writes=list(s.mem.writes);start(s)
            text=log(s)
            assert 'Cluster trace start:' in text and 'Cluster projectile settings:' in text
            assert 'active_primary_observations=1 active_secondary_observations=1' in text
            assert 'primary slot=0 source=1234' in text and 'secondary slot=1 source=1234' in text
            assert 'pos=(-700.0,50.0,120.0)' in text and 'field_34=0.25' in text
            assert s.mem.writes==writes
            for index,expected in ((0,a),(1,b)):
                assert s.mem.read(system+0x4d040+index*0xc8,0xc8)==expected[0]
                assert s.mem.read(system+0x3040+index*0x70,0x70)==expected[1]
            # Inactive, unrelated and reused slots must not be followed as an old projectile.
            slot(s,0,active=False);s.mem.put(system+0x4d040+0xc8+8,U(999));s.tick()
            assert 'active_primary_observations=0 active_secondary_observations=0' in log(s)
            assert not list(s.state[b'cluster_trace'][b'tracked'].keys())
            s.cfg('bomb=192\n');assert s.state[b'cluster_trace'] is None
        finally:s.close()

    def ring_bounds_and_lifetime():
        s=Scenario({'bomb':286,'forward':0})
        try:
            s.tick();setup(s,0xffffffff);start(s)
            slot(s,2047);slot(s,0,'secondary');s.mem.put(system+0x30,U(1));s.tick()
            assert 'cursor=1 inspected_recent=2' in log(s)
            assert 'active_primary_observations=1 active_secondary_observations=1' in log(s)
            s.mem.put(system+0x30,U(2001));s.mem.reads.clear();s.mem.read_bytes=0;s.tick()
            assert 'inspected_recent=512 truncated=true' in log(s)
            assert sum(s.mem.reads.values())<1300 and s.mem.read_bytes<120000
            for _ in range(80):s.tick()
            assert s.state[b'cluster_trace'] is None
            assert log(s).count('Cluster trace sample=')==40
            manager,objects,states,descriptor=eagle_state(s,attacked=1)
            s.mem.put(descriptor+12,U(1000));s.tick()
            for generation in range(1001,1010):
                s.mem.put(descriptor+12,U(generation));s.tick()
            for _ in range(80):s.tick()
            s.mem.put(descriptor+12,U(2000));s.tick()
            assert s.state[b'cluster_trace_count']==2
            assert log(s).count('Cluster trace sample=')==80
        finally:s.close()

    def failure_isolation_and_idle_cost():
        for mode in ('missing','replaced','exception','start_exception','disabled','other_bomb'):
            s=Scenario({'bomb':192 if mode=='other_bomb' else 286,'forward':0})
            try:
                s.tick()
                if mode!='missing':setup(s)
                writes=list(s.mem.writes)
                if mode=='start_exception':
                    original=s.mem.read;projectile=s.projectiles[286][0]
                    def broken_start(p,n):
                        if p==projectile and n==272:raise RuntimeError('injected diagnostic startup failure')
                        return original(p,n)
                    s.mem.read=broken_start
                start(s)
                if mode=='start_exception':
                    s.mem.read=original
                    assert s.state[b'cluster_trace_fault'] is True
                    assert not s.state[b'forward_fault']
                if mode=='replaced':s.mem.put(BASE+0x347cea8,Q(system+0x1000));s.tick()
                if mode=='exception':
                    original=s.mem.read
                    def broken(p,n):
                        if p==system+0x30:raise RuntimeError('injected diagnostic read failure')
                        return original(p,n)
                    s.mem.read=broken;s.tick();s.mem.read=original
                    assert s.state[b'cluster_trace_fault'] is True
                if mode=='disabled':s.cfg('enabled=0\n')
                assert s.state[b'phase'] in (b'active',b'disabled')
                if mode!='disabled':assert s.mem.writes==writes
                if mode=='other_bomb':
                    assert not s.state[b'cluster_trace_count']
                    assert (BASE+0x347cea8,8) not in s.mem.reads
                else:assert s.state[b'cluster_trace'] is None
            finally:s.close()

    passed=[]
    for name,fn in [
        ('cluster trace: main/secondary signatures and positions, existing log cap, reused slots and no projectile writes',read_only_and_late_selection),
        ('cluster trace: 32-bit cursor wrap, 512-slot budget, six retained examples and two 40-sample windows',ring_bounds_and_lifetime),
        ('cluster trace: missing/replaced systems, diagnostic exceptions, disable and zero cost for other bombs',failure_isolation_and_idle_cost)]:
        fn();passed.append(name);print('PASS',name)
    return passed
