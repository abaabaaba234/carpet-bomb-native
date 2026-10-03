"""Fault injection for recovery, state boundaries and configuration persistence."""
import struct

U=lambda n:struct.pack('<I',n)
F=lambda n:struct.pack('<f',n)
Q=lambda n:struct.pack('<Q',n)

def run(Scenario,BASE,eagle_state):
    def restore_retry():
        s=Scenario({'uses':3})
        try:
            s.tick();p=s.address[103]+0x50;write=s.mem.write;failures=[2];original=s.originals[103][0x50:0x54]
            def injected(address,data):
                if address==p and data==original and failures[0]:
                    failures[0]-=1;s.mem.writes.append((address,data));return False
                return write(address,data)
            s.mem.write=injected;s.mem.put(s.address[103]+0x68,F(77));s.tick()
            assert s.state[b'phase']==b'stopped' and len(s.state[b'owned'])==2
            assert s.r(103,0x50,4)==U(3)
            s.tick();assert s.r(103,0x50,4)==U(3)
            s.tick();assert s.r(103,0x50,4)==original
            assert s.r(103,0x68,4)==F(77) # A foreign write is never reverted.
            assert s.state[b'cleanup_attempts']==3 and len(s.state[b'owned'])==1
            writes=len(s.mem.writes)
            for _ in range(5):s.tick()
            assert len(s.mem.writes)==writes and not s.state[b'cleanup_complete']
        finally:s.close()

    def transaction_retry():
        s=Scenario({'uses':3})
        try:
            s.tick();p=s.address[103]+0x50;write=s.mem.write;failures=[2]
            def injected(address,data):
                if address==p and data==U(3) and failures[0]:
                    failures[0]-=1;s.mem.writes.append((address,data));return False
                return write(address,data)
            s.mem.write=injected;s.mem.fail_address=p;s.cfg('uses=4\n')
            assert s.state[b'phase']==b'stopped' and len(s.state[b'recovery'])==1
            assert s.state[b'recovery'][1][b'original']==U(3)
            s.tick()
            assert not len(s.state[b'recovery']) and s.r(103,0x50,4)==s.originals[103][0x50:0x54]
            assert s.state[b'cleanup_complete'] and s.r(33,0xc8,4)==U(0)
        finally:s.close()

    def identity_and_writer_guards():
        for mode in ('moved','foreign'):
            s=Scenario({'uses':3})
            try:
                s.tick();p=s.address[103]+0x50;write=s.mem.write;original=s.originals[103][0x50:0x54]
                def injected(address,data):
                    if address==p and data==original:s.mem.writes.append((address,data));return False
                    return write(address,data)
                s.mem.write=injected;s.mem.put(s.address[103]+0x68,F(77));s.tick()
                if mode=='moved':s.mem.put(BASE+0x37cb600+103*8,Q(0x77770000))
                else:s.mem.put(p,U(999))
                writes=len(s.mem.writes);s.tick();s.tick()
                assert not any(address==p for address,_ in s.mem.writes[writes:])
                assert len(s.state[b'owned'])>0 and s.state[b'cleanup_attempts']==3
            finally:s.close()

    def protection_and_free_retry():
        s=Scenario()
        try:
            table=s.tables[0];s.mem.protect(table['p'],len(table['original']),2)
            protect=s.mem.protect;failures=[2]
            def injected(p,n,value):
                if value==2 and failures[0]:failures[0]-=1;return 0
                return protect(p,n,value)
            s.mem.protect=injected;s.tick()
            assert s.state[b'phase']==b'stopped' and s.mem.page_protection(table['p'])==4
            assert list(s.state[b'protection_pending'].keys())
            s.tick();assert s.mem.page_protection(table['p'])==2
            assert not list(s.state[b'protection_pending'].keys())
        finally:s.close()
        s=Scenario()
        try:
            free=s.mem.free;failures=[1]
            def injected(p):
                if failures[0]:failures[0]-=1;return 0
                return free(p)
            s.mem.free=injected;s.mem.fail_address=s.mem.cursor;s.tick()
            assert len(s.mem.allocations)==1 and not s.state[b'cleanup_complete']
            s.tick();assert not s.mem.allocations and s.state[b'cleanup_complete']
        finally:s.close()

    def public_disable_and_stop():
        s=Scenario()
        try:
            s.tick();assert s.state[b'disable']() is True;s.tick()
            assert s.state[b'phase']==b'disabled' and s.r(33,0xc8,4)==U(0)
            assert 'enabled=0' in (s.logs/'CarpetBombNative.cfg').read_text()
            writes=len(s.mem.writes);assert s.state[b'disable']() is True;s.tick()
            assert len(s.mem.writes)==writes
            s.cfg('enabled=1\n');assert s.state[b'phase']==b'active'
            s.mem.put(s.address[103]+0x68,F(77));s.tick()
            result=s.state[b'disable']();assert result[0] is False
            writes=len(s.mem.writes);s.cfg('enabled=1\nuses=9\n');s.tick();s.tick()
            assert s.state[b'phase']==b'stopped'
            assert not any(data==U(103) for _,data in s.mem.writes[writes:])
            assert s.r(103,0x68,4)==F(77)
        finally:s.close()

    def atomic_configuration():
        for mode in ('write','flush','close','replace'):
            s=Scenario()
            try:
                s.tick();path=s.logs/'CarpetBombNative.cfg';saved=path.read_bytes();writes=len(s.mem.writes)
                if mode=='replace':s.replace_failure=True
                else:
                    s.lua.globals()[b'failure_stage']=mode.encode()
                    s.lua.execute(b'''
                        local open=io.open
                        io.open=function(path,mode)
                            local file,why=open(path,mode)
                            if not file or not path:match('CarpetBombNative%.cfg%.tmp$') or mode~='wb' then return file,why end
                            return {
                                write=function(_,text)if failure_stage=='write' then file:write(text:sub(1,10));return nil,'write failed' end;return file:write(text)end,
                                flush=function()if failure_stage=='flush' then return nil,'flush failed' end;return file:flush()end,
                                close=function()local ok=file:close();if failure_stage=='close' then return nil,'close failed' end;return ok end
                            }
                        end
                    ''')
                result=s.state[b'disable']();assert result[0] is False
                s.tick();assert path.read_bytes()==saved and s.state[b'phase']==b'active'
                assert s.state[b'config'][b'enabled']==1 and len(s.mem.writes)==writes
                assert not path.with_name(path.name+'.tmp').exists()
            finally:s.close()

    def schema_and_missing_file():
        s=Scenario({'uses':999,'cooldown':-7,'rearm':'invalid','bomb':999,'forward':float('nan')})
        try:
            s.tick();c=s.state[b'config']
            assert (c[b'uses'],c[b'cooldown'],c[b'rearm'],c[b'bomb'],c[b'forward'])==(2,15,-1,170,80)
            s.cfg('uses=7\ncooldown=30\n')
            for text in ('uses=2 trailing\n','uses=\n','language=zh invalid\n','enabled=bad\n'):
                s.cfg(text);assert c[b'uses']==7 and c[b'cooldown']==30
            s.cfg('\ufeffuses=8 # comment\ncooldown=0\n')
            assert c[b'uses']==8 and c[b'cooldown']==0
            (s.logs/'CarpetBombNative.cfg').unlink();s.tick()
            assert c[b'uses']==8 and c[b'cooldown']==0
        finally:s.close()

    def flight_restore_retry():
        for mode in ('retry','reused'):
            s=Scenario()
            try:
                s.tick();manager,objects,states,descriptor=eagle_state(s)
                p=states+0x54;before=s.mem.read(p,8);write=s.mem.write;failures=[2]
                def injected(address,data):
                    if address==p and data==before and failures[0]:
                        failures[0]-=1;s.mem.writes.append((address,data));return False
                    return write(address,data)
                s.mem.write=injected;s.mem.fail_address=p;s.tick()
                assert s.state[b'phase']==b'stopped' and len(s.state[b'recovery'])==1
                if mode=='reused':s.mem.put(descriptor+12,U(12345))
                writes=len(s.mem.writes);s.tick()
                if mode=='retry':
                    assert s.mem.read(p,8)==before and s.state[b'cleanup_complete']
                else:
                    s.tick();assert not any(address==p for address,_ in s.mem.writes[writes:])
                    assert len(s.state[b'recovery'])==1 and not s.state[b'cleanup_complete']
            finally:s.close()

    passed=[]
    for name,fn in [
        ('restore retains failures, preserves foreign values and stops after three cleanup rounds',restore_retry),
        ('failed transaction rollback retries before restoring original owned fields',transaction_retry),
        ('cleanup refuses moved records and subsequent competing writers',identity_and_writer_guards),
        ('page protection and unpublished allocation cleanup retry safely',protection_and_free_retry),
        ('public disable persists, is idempotent and cannot revive a stopped runtime',public_disable_and_stop),
        ('atomic config write/flush/close/replace failures preserve original bytes and settings',atomic_configuration),
        ('shared schema rejects invalid presets and malformed config without resetting on missing files',schema_and_missing_file),
        ('failed flight-target restoration retries only while the same aircraft identity remains',flight_restore_retry)]:
        fn();passed.append(name);print('PASS',name)
    return passed
