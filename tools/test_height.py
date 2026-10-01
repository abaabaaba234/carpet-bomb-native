"""Apply one guarded float change to this mod's private Eagle record for field testing."""
from pathlib import Path
import sys,json,struct,ctypes as c
ROOT=Path(__file__).resolve().parents[1]
harness=ROOT.parent/'shield_vehicle_resupply/.unit-parent-work/inspect_live_parent.py'
exec(compile(harness.read_text().split('\ntry:',1)[0],str(harness),'exec'))
try:
    pe=read(base+struct.unpack_from('<I',read(base,64),60)[0],96)
    assert struct.unpack_from('<I',pe,8)[0]==0x6ab3b43f
    root=ptr(base+0x346bf98);data=ptr(root+0xf12e78)
    header=read(data-28,28)
    assert struct.unpack('<I4sIIIII',header)==(0x556ff68b,b'LDLD',1,0x556ff68b,2144,1,0)
    fixture=next(x for x in json.loads((ROOT/'tests/fixtures/payload_tables_build25480438.json').read_text()) if x['name']=='EagleComponentData')
    raw=read(data,2144);original=bytes.fromhex(fixture['eagle_data_hex'])
    assert raw[320:1992]==original[320:1992],'An original Eagle row changed.'
    native=0x6ccb976676ef6cc6
    matches=[struct.unpack_from('<QII',raw,i*16) for i in range(20) if struct.unpack_from('<Q',raw,i*16)[0]==native]
    assert len(matches)==1 and matches[0][1]==11
    expected=bytearray(original[472:624]);struct.pack_into('<I',expected,16,6)
    assert raw[1992:]==expected,'Private native row differs from the deployed prototype.'
    address=data+1992+0x3c;before=struct.pack('<f',1000);wanted=struct.pack('<f',120)
    assert read(address,4)==before
    K.VirtualQueryEx.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t]
    K.VirtualQueryEx.restype=c.c_size_t
    memory=c.create_string_buffer(48)
    assert K.VirtualQueryEx(handle,address,memory,48)==48
    region,allocation,protect,size_region,state,protection,kind=struct.unpack('<QQI4xQIII4x',memory.raw)
    assert state==0x1000 and protection==4 and kind==0x20000 and region<=data-28 and address+4<=region+size_region
    K.CloseHandle(handle);handle=None
    handle=K.OpenProcess(0x438,False,pid)
    assert handle,('OpenProcess for guarded data write',c.get_last_error())
    K.WriteProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
    assert ptr(root+0xf12e78)==data and read(data,2144)==raw
    count=c.c_size_t();buffer=c.create_string_buffer(wanted)
    ok=K.WriteProcessMemory(handle,address,buffer,4,c.byref(count)) and count.value==4
    if not ok or read(address,4)!=wanted:
        restore=c.create_string_buffer(before)
        K.WriteProcessMemory(handle,address,restore,4,c.byref(count))
        raise RuntimeError('Height test write failed; attempted restoration.')
    receipt={'pid':pid,'purpose':'private CarpetBomb approach-height test','address':hex(address),'before':1000,'after':120,
             'original_eagle_rows_preserved':read(data+320,1672)==original[320:]}
    (ROOT/'validation/live_height_test.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))
finally:
    if handle:K.CloseHandle(handle)
