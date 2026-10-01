"""Read-only, bounded capture of Eagle bomb simulation slots."""
from pathlib import Path
from datetime import datetime
import sys,json,struct,time
ROOT=Path(__file__).resolve().parents[1]
harness=ROOT.parent/'shield_vehicle_resupply/.unit-parent-work/inspect_live_parent.py'
exec(compile(harness.read_text().split('\ntry:',1)[0],str(harness),'exec'))
duration=float(sys.argv[2]) if len(sys.argv)>2 else 0
assert 0<=duration<=180
output=ROOT/'research/live'/('projectiles_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.jsonl')
start=time.monotonic();last=None
try:
    with output.open('x',encoding='utf-8') as stream:
        print('Read-only bomb capture:',output,flush=True)
        while True:
            manager=ptr(base+0x347cea8)
            counter=u32(manager+0x30)
            flags=struct.unpack('<2048H',read(manager+0x203c,4096))
            physics=read(manager+0x3040,2048*0x70)
            metadata=read(manager+0x4d040,2048*0xc8)
            bombs=[]
            for i in range(2048):
                row=metadata[i*0xc8:(i+1)*0xc8]
                if struct.unpack_from('<I',row,0xc)[0]!=234:continue
                if duration and not flags[i]&2:continue
                state=physics[i*0x70:(i+1)*0x70]
                bombs.append({'slot':i,'flags':flags[i],
                    'position':struct.unpack_from('<3f',state,0),
                    'velocity':struct.unpack_from('<3f',state,12),
                    'delay':struct.unpack_from('<f',state,24)[0],
                    'gravity':struct.unpack_from('<f',state,28)[0],
                    'unit':struct.unpack_from('<I',state,0x4c)[0],
                    **({'physics_hex':state.hex(),'metadata_hex':row.hex()} if not duration else {})})
            sample={'seconds':round(time.monotonic()-start,3),'counter':counter,'bombs':bombs}
            stream.write(json.dumps(sample)+'\n');stream.flush()
            label=(len(bombs),sum(bool(x['flags']&2) for x in bombs))
            if label!=last:print(json.dumps({'seconds':sample['seconds'],'counter':counter,'bomb_slots':label[0],'active_bombs':label[1]}),flush=True);last=label
            if time.monotonic()-start>=duration:break
            time.sleep(0.05)
finally:K.CloseHandle(handle)
