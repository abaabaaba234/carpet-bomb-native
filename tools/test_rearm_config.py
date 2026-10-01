"""Temporarily exercise the addon's rearm setting through its own config.

Uses a read-only process handle. The addon performs its regular guarded data
transaction; this script never writes process memory. Restore the exact config
bytes after checking the new value, and check that only rearm data changed.
Run on the ship bridge: python tools/test_rearm_config.py PID
"""
from pathlib import Path
from datetime import datetime
import ctypes as c,struct,json,sys,time,os,hashlib

script=Path(__file__).with_name('capture_live.py')
exec(compile(script.read_text(encoding='utf-8').split('\ntry:',1)[0],str(script),'exec'))
cfg=Path(os.environ['LOCALAPPDATA'])/'CowboyBingus/Helldivers2/Logs/CarpetBombNative.cfg'
log_path=cfg.with_suffix('.log')
output=ROOT/'research/rearm_verification'/datetime.now().strftime('%Y%m%d_%H%M%S')
output.mkdir(parents=True,exist_ok=False)
result={'version':'0.4.0','pid':pid,'method':'addon config; external process handle read-only',
        'tested_rearm':30,'config_restored':False,'restoration_verified':False}
original=None;temporary=None
try:
    dos=read(base,64);pe=read(base+struct.unpack_from('<I',dos,60)[0],96)
    assert struct.unpack_from('<I',pe,8)[0]==0x6ab3b43f and struct.unpack_from('<I',pe,80)[0]==0x4744000
    assert 'Loaded v0.4.0' in log_path.read_text(encoding='utf-8')
    addresses={t:ptr(base+0x37cb600+t*8) for t in (18,33,38,49,103)}
    before={t:read(a,400) for t,a in addresses.items()}
    assert all(raw and struct.unpack_from('<I',raw)[0]==t for t,raw in before.items())
    assert struct.unpack_from('<I',before[49],0x3c)[0]==7
    assert struct.unpack_from('<I',before[33],0xc8)[0]==103
    name=read(ptr(base+0x21d4aa0+49*8),64).split(b'\0')[0]
    title=read(struct.unpack_from('<Q',before[49],0x10)[0],128).split(b'\0')[0]
    assert name==b'EagleRearm' and title==b'EAGLE. REARM'
    baseline=struct.unpack_from('<f',before[49],0x68)[0]
    result.update(original_rearm=baseline,uses=struct.unpack_from('<I',before[103],0x50)[0],
                  call_interval=struct.unpack_from('<f',before[103],0x68)[0])
    original=cfg.read_bytes();(output/'config_before.cfg').write_bytes(original)
    temporary=original.rstrip(b'\r\n')+b'\nrearm=30\n'
    cfg.write_bytes(temporary)
    def wait_for(value):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            assert ptr(base+0x37cb600+49*8)==addresses[49],'Rearm record moved'
            raw=read(addresses[49]+0x68,4)
            if raw==struct.pack('<f',value):return
            time.sleep(0.1)
        raise AssertionError('Timed out waiting for addon rearm value '+str(value))
    wait_for(30)
    changed={t:read(a,400) for t,a in addresses.items()}
    assert changed[49]==before[49][:0x68]+struct.pack('<f',30)+before[49][0x6c:]
    assert all(changed[t]==before[t] for t in (18,33,38,103))
    result['only_rearm_cooldown_changed']=True
finally:
    try:
        if original is not None and temporary is not None and cfg.read_bytes()==temporary:
            cfg.write_bytes(original);result['config_restored']=True
            wait_for(result['original_rearm'])
            assert all(read(a,400)==before[t] for t,a in addresses.items())
            assert cfg.read_bytes()==original
            result['restoration_verified']=True
            result['config_sha256']=hashlib.sha256(original).hexdigest()
            result['restored_rearm']=result['original_rearm']
        result['log_tail']=log_path.read_text(encoding='utf-8').splitlines()[-8:]
        (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        (ROOT/'validation/rearm_live_test.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    finally:K.CloseHandle(handle)
assert result['only_rearm_cooldown_changed'] and result['restoration_verified']
