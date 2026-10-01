"""Read only the constants used by the native CarpetBomb range calculation."""
from pathlib import Path
import sys,json,struct
ROOT=Path(__file__).resolve().parents[1]
harness=ROOT.parent/'shield_vehicle_resupply/.unit-parent-work/inspect_live_parent.py'
exec(compile(harness.read_text().split('\ntry:',1)[0],str(harness),'exec'))
try:
    rvas={'gravity':0x23c8128,'dt_numerator':0x23c664c,'radius_scale':0x23c65a8,
          'density':0x23c7d3c,'pi':0x23c6f1c,'half':0x23c6e28,'epsilon':0x23c65b0,
          'integrator_half':0x23c6ad0}
    constants={name:struct.unpack('<f',read(base+rva,4))[0] for name,rva in rvas.items()}
    constants['resolution']=list(struct.unpack('<4I',read(base+0x21d2b28,16)))
    projectile=read(ptr(base+0x37c7670+170*8),272)
    constants['projectile_hex']=projectile.hex()
    constants['projectile_fields']={name:struct.unpack_from('<f',projectile,offset)[0]
        for name,offset in [('radius',0x18),('speed',0x20),('mass',0x24),('drag',0x28),('gravity',0x2c)]}
    projectile_system=ptr(base+0x347cea8)
    constants['projectile_system']={'address':hex(projectile_system),
        'enabled':read(projectile_system+0x28,1)[0],
        'spawn_counter':u32(projectile_system+0x30)}
    output=ROOT/'research/live/carpet_ballistics.json'
    output.write_text(json.dumps(constants,indent=2))
    print(json.dumps(constants,indent=2))
finally:K.CloseHandle(handle)
