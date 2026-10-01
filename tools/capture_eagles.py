"""Read-only sampling of live Eagle flight and payload state, bounded to 180 seconds."""
from pathlib import Path
import sys,json,time,struct,math
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
harness=ROOT.parent/'shield_vehicle_resupply/.unit-parent-work/inspect_live_parent.py'
exec(compile(harness.read_text().split('\ntry:',1)[0],str(harness),'exec'))
duration=float(sys.argv[2]) if len(sys.argv)>2 else 0
assert 0<=duration<=180
start=time.monotonic();samples=[];last=None
output=ROOT/'research/live'/('eagle_flight_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.jsonl')
output.parent.mkdir(parents=True,exist_ok=True)
stream=output.open('x',encoding='utf-8')
print('Read-only flight capture:',output,flush=True)
def static_config(resource):
    root=ptr(base+0x346bf98)
    if not root:return None
    data=ptr(root+0xf12e78)
    if not data:return None
    for step in range(20):
        key,index,_=struct.unpack('<QII',read(data+((resource%20+step)%20)*16,16))
        if key==0:return None
        if key==resource:
            assert index<64
            return read(data+320+index*152,152)
    return None
try:
    dos=read(base,64);pe=read(base+struct.unpack_from('<I',dos,60)[0],96)
    assert struct.unpack_from('<I',pe,8)[0]==0x6ab3b43f
    while True:
        manager=ptr(base+0x3326650)
        assert manager,'EagleSystem is not initialized; enter a mission first.'
        count=u32(manager+0x20)
        assert count<=64
        objects=ptr(manager+0x48);states=ptr(manager+0x58)
        overrides=table(manager+0x70);override_rows=ptr(manager+0xb0)
        records=[]
        for i in range(count):
            descriptor_ptr=ptr(objects+i*8);resource,entity,unit=struct.unpack('<QII',read(descriptor_ptr,16))
            state=read(states+i*0xfc,0xfc);config_index=lookup(overrides,entity)
            config=read(override_rows+config_index*152,152) if config_index is not None else static_config(resource)
            # +0x54 is the fixed strike target; +0x78 moves with the aircraft.
            target=struct.unpack_from('<3f',state,0x54);current=struct.unpack_from('<3f',state,0x78)
            record={'entity':entity,'unit':unit,'resource':f'{resource:016x}',
                'position':current,'target':target,'velocity':struct.unpack_from('<3f',state,0xd4),
                'horizontal_distance':math.hypot(current[0]-target[0],current[1]-target[1]),
                'height_difference':current[2]-target[2],
                'firing':state[0x70],'has_attacked':state[0x71],
                'config_source':'override' if config_index is not None else 'static',
                'flags':state[:16].hex(),'state_hex':state.hex(),
                'payload':struct.unpack_from('<I',config,16)[0] if config else None,
                'projectile':struct.unpack_from('<I',config,24)[0] if config else None,
                'config_hex':config.hex() if config else None}
            records.append(record)
        sample={'seconds':round(time.monotonic()-start,3),'records':records};samples.append(sample)
        stream.write(json.dumps(sample)+'\n');stream.flush()
        label=[(r['resource'],r['payload'],r['firing'],r['has_attacked']) for r in records]
        if label!=last:
            print(json.dumps({'seconds':sample['seconds'],'count':count,'states':label}),flush=True);last=label
        if time.monotonic()-start>=duration:break
        time.sleep(0.05)
    (ROOT/'research/live/eagle_flight_samples.json').write_text(json.dumps(samples,indent=2))
    print('Saved',len(samples),'flight samples',flush=True)
finally:
    stream.close()
    K.CloseHandle(handle)
