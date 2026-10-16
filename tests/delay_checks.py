"""Beacon activation delay ownership and native-reader evidence checks."""
import json,struct
from capstone import Cs,CS_ARCH_X86,CS_MODE_64

F=lambda n:struct.pack('<f',n)

def run(Scenario,BASE,ROOT):
    def delay_reload_and_payloads():
        for bomb in (170,192,239,286,141,188):
            s=Scenario({'bomb':bomb,'call_delay':5})
            try:
                # A nonzero game baseline must be added once, never overwritten or accumulated.
                s.mem.put(s.address[103]+0x54,F(2));s.tick()
                assert s.state[b'phase']==b'active' and s.r(103,0x54,4)==F(7)
                writes=len(s.mem.writes)
                for _ in range(4):s.tick()
                assert len(s.mem.writes)==writes
                for n in (60,1,0,8):
                    s.cfg(f'bomb={bomb}\ncall_delay={n}\n')
                    assert s.r(103,0x54,4)==F(2+n)
                    assert s.state[b'config'][b'bomb_count']==20
                for t in s.originals:
                    if t not in (33,103):assert s.r(t,0,400)==s.originals[t]
                for address,raw in s.projectiles.values():assert s.mem.read(address,len(raw))==raw
                s.cfg('enabled=0\ncall_delay=60\n')
                assert s.r(103,0x54,4)==F(2) and s.r(33,0,400)==s.originals[33]
                s.cfg('enabled=1\ncall_delay=manager\n')
                assert s.r(103,0x54,4)==F(7)
            finally:s.close()

    def default_relinquish_and_validation():
        s=Scenario()
        try:
            s.tick();address=s.address[103]+0x54
            assert not any(p==address for p,_ in s.mem.writes)
            # Zero neither changes nor watches an unowned delay.
            s.mem.put(address,F(3));s.tick();assert s.state[b'phase']==b'active'
            s.cfg('call_delay=0\n');assert s.mem.read(address,4)==F(3)
        finally:s.close()
        s=Scenario({'call_delay':5})
        try:
            s.tick();s.cfg('call_delay=0\n');address=s.address[103]+0x54
            s.mem.put(address,F(3));s.tick();assert s.state[b'phase']==b'active'
        finally:s.close()
        s=Scenario(cfg='call_delay=8\n')
        try:
            s.tick()
            for bad in ('-1','61','1.5','nan','inf','abc'):
                s.cfg(f'call_delay={bad}\nuses=99\n')
                assert s.state[b'config'][b'call_delay']==8 and s.state[b'config'][b'uses']==2
                assert s.r(103,0x54,4)==F(8)
            s.cfg('uses=3\n');assert s.r(103,0x54,4)==F(0)
        finally:s.close()

    def delay_conflicts_and_partial_failure():
        for stage in ('before','after','partial','disable_partial'):
            s=Scenario({'call_delay':10})
            try:
                address=s.address[103]+0x54
                if stage=='partial':s.mem.fail_address=address
                s.tick()
                if stage=='before':
                    s.cfg('call_delay=0\n');s.mem.put(address,F(12));s.cfg('call_delay=5\n')
                elif stage=='after':s.mem.put(address,F(12));s.tick()
                elif stage=='disable_partial':
                    s.mem.fail_address=address;s.cfg('enabled=0\n')
                assert s.state[b'phase']==b'stopped'
                assert s.r(33,0,400)==s.originals[33]
                assert s.mem.read(address,4)==F(12 if stage in ('before','after') else 0)
            finally:s.close()

    def captured_native_delay_reader():
        fixture=json.loads((ROOT/'tests/fixtures/code_windows_build25480438.json').read_text())
        cs=Cs(CS_ARCH_X86,CS_MODE_64)
        def instructions(rva):
            window=next(w for w in fixture['windows'] if int(w['rva'],16)==rva)
            return {a:(m,o) for a,n,m,o in cs.disasm_lite(bytes.fromhex(window['hex']),rva)}
        reader=instructions(0x87992e)
        assert reader[0x879941]==('mov','rdi, qword ptr [rbx + rsi*8]')
        assert reader[0x87997f]==('addss','xmm0, dword ptr [rdi + 0x54]')
        scheduler=instructions(0xb9abe8)
        assert scheduler[0xb9abe8]==('call','0x879900')
        assert scheduler[0xb9ac0c]==('addss','xmm0, xmm6')
        assert scheduler[0xb9ac2a]==('mov','qword ptr [rsi + rbx*8 + 0x1e0], rcx')

    passed=[]
    for name,fn in [
        ('beacon extra delay: six payloads, additive baseline, zero/max, reload, presets and disable restoration',delay_reload_and_payloads),
        ('beacon extra delay: zero leaves other owners alone, restore relinquishes ownership and invalid config is atomic',default_relinquish_and_validation),
        ('beacon extra delay: external ownership, partial write and disable failure restore the native grant transaction',delay_conflicts_and_partial_failure),
        ('beacon extra delay: independently captured native base-delay reader and deadline scheduler disassemble correctly',captured_native_delay_reader)]:
        fn();passed.append(name);print('PASS',name)
    return passed
