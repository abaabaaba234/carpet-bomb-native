"""Flight traces must remain bounded and leave the existing flight behavior alone."""
import struct

def run(Scenario,BASE,eagle_state):
    U=lambda x:struct.pack('<I',x)
    def log(s):return (s.logs/'CarpetBombNative.log').read_text(encoding='utf-8')
    for mode in ('attacked','firing','outgoing','zero','shift'):
        s=Scenario({'direction':180,'forward':0 if mode=='zero' else 80},diagnostics=True)
        try:
            args={'attacked':1} if mode=='attacked' else {'firing':1} if mode=='firing' else {'velocity':(-200,0,0)} if mode=='outgoing' else {}
            manager,objects,states,descriptor=eagle_state(s,**args)
            before=s.mem.read(states,0xfc);s.tick()
            text=log(s)
            assert 'Flight first observation:' in text and 'configured_direction=180deg' in text
            if mode=='attacked':assert 'attacked=1' in text
            if mode=='firing':assert 'firing=1' in text
            if mode=='outgoing':assert 'toward_dot=-80000.0' in text
            if mode!='shift':assert s.mem.read(states,0xfc)==before
            else:assert struct.unpack('<3f',s.mem.read(states+0x54,12))==(80,0,6)
            for _ in range(4):s.tick()
            assert log(s).count('Flight first observation:')==1
            for generation in range(30):
                eagle_state(s,attacked=1);s.mem.put(descriptor+12,U(1000+generation));s.tick()
            assert s.state[b'flight_observation_count']==12
            assert 1<=log(s).count('Flight first observation:')<=12
            assert len(list(s.state[b'flight_observed'].keys()))==1
            s.mem.put(manager+0x20,U(0));s.tick()
            assert not list(s.state[b'flight_observed'].keys())
        finally:s.close()
    s=Scenario(diagnostics=True)
    try:
        for i in range(12):eagle_state(s,resource=0x2ea01cb1676aca29+i);s.tick()
        assert s.state[b'unmatched_flight_logs']==3
        assert log(s).count('no native CarpetBomb descriptor')==3
        assert not s.state[b'forward_adjustments']
    finally:s.close()
    name='bounded first-flight diagnostics preserve target handling, report early attack states and prune entity identities'
    print('PASS',name)
    return [name]
