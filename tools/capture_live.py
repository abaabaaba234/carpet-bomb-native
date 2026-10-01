"""Bounded read-only capture of Eagle payload settings on the verified game build."""
from pathlib import Path
import ctypes as c
from ctypes import wintypes as w
import struct,json,sys
ROOT=Path(__file__).resolve().parents[1]
types=json.loads((ROOT.parent/'shield_vehicle_resupply/.frv-repair-work/references/all-types.json').read_text())
def dlhash(name):
    h=5381
    for ch in name:h=(h*33+ord(ch))&0xffffffff
    return (h-5381)&0xffffffff
names={dlhash(name):name for name in types}
K=c.WinDLL('kernel32',use_last_error=True)
class Module(c.Structure):
    _fields_=[('size',w.DWORD),('id',w.DWORD),('pid',w.DWORD),('global_usage',w.DWORD),('process_usage',w.DWORD),('base',c.c_void_p),('bytes',w.DWORD),('handle',w.HMODULE),('name',w.WCHAR*256),('path',w.WCHAR*260)]
K.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];K.CreateToolhelp32Snapshot.restype=w.HANDLE
K.Module32FirstW.argtypes=[w.HANDLE,c.POINTER(Module)];K.Module32NextW.argtypes=[w.HANDLE,c.POINTER(Module)]
K.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];K.OpenProcess.restype=w.HANDLE
K.ReadProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
K.CloseHandle.argtypes=[w.HANDLE]
pid=int(sys.argv[1]);snapshot=K.CreateToolhelp32Snapshot(0x18,pid)
entry=Module();entry.size=c.sizeof(entry);ok=K.Module32FirstW(snapshot,c.byref(entry));base=None
while ok:
    if entry.name.lower()=='game.dll':base=entry.base;break
    ok=K.Module32NextW(snapshot,c.byref(entry))
K.CloseHandle(snapshot);assert base,'game.dll is not loaded'
handle=K.OpenProcess(0x410,False,pid);assert handle,c.get_last_error()
def read(p,n):
    if not 0xffff<p<0x7fffffff0000 or not 0<n<=512*1024:return None
    b=c.create_string_buffer(n);got=c.c_size_t()
    if not K.ReadProcessMemory(handle,p,b,n,c.byref(got)) or got.value!=n:return None
    return b.raw
def ptr(p):
    data=read(p,8);return struct.unpack('<Q',data)[0] if data else 0
def read_large(p,n):
    if not 0<n<=16*1024*1024:return None
    chunks=[]
    for offset in range(0,n,512*1024):
        chunk=read(p+offset,min(n-offset,512*1024))
        if not chunk:return None
        chunks.append(chunk)
    return b''.join(chunks)
try:
    dos=read(base,64);pe=read(base+struct.unpack_from('<I',dos,60)[0],96)
    assert struct.unpack_from('<I',pe,8)[0]==0x6ab3b43f and struct.unpack_from('<I',pe,80)[0]==0x4744000
    root=ptr(base+0x346bf98);table=ptr(root+0xf12e78)
    out=ROOT/'research/live';out.mkdir(exist_ok=True)
    rows={}
    for t in (18,33,38,49,103):
        raw=read(ptr(base+0x37cb600+t*8),400)
        rows[t]={'uses':struct.unpack_from('<I',raw,0x50)[0],
                 'cooldown':struct.unpack_from('<f',raw,0x68)[0],
                 'additional':struct.unpack_from('<I',raw,0xc8)[0],
                 'payload':[hex(ptr(struct.unpack_from('<Q',raw,0x98)[0]+i*8)) for i in range(struct.unpack_from('<Q',raw,0xa0)[0])]}
        (out/f'stratagem_{t}.bin').write_bytes(raw)
    (out/'eagle_table.bin').write_bytes(read(table,1992))
    projectiles={}
    for t in (115,130,170,188,239,286):
        raw=read(ptr(base+0x37c7670+t*8),272)
        if raw:
            (out/f'projectile_{t}.bin').write_bytes(raw)
            projectiles[t]={'type':struct.unpack_from('<I',raw)[0],
                'speed':struct.unpack_from('<f',raw,0x20)[0],
                'mass':struct.unpack_from('<f',raw,0x24)[0],
                'drag':struct.unpack_from('<f',raw,0x28)[0],
                'gravity':struct.unpack_from('<f',raw,0x2c)[0]}
    pointers=read(root+0xf12000,0x1200)
    refs=[];donor=struct.pack('<Q',0x2ea01cb1676aca29)
    for o in range(0,len(pointers),8):
        p=struct.unpack_from('<Q',pointers,o)[0]
        header=read(p-28,28)
        if not header or header[4:8]!=b'LDLD':continue
        th,size=struct.unpack_from('<I',header)[0],struct.unpack_from('<I',header,16)[0]
        name=names.get(th,'unknown_'+hex(th));schema=types.get(name)
        if not schema:continue
        raw=read_large(p,size)
        if not raw:continue
        index_size=schema['members'][0]['size'] if name.endswith('Data') and schema['members'][0]['type']=='ComponentIndexData' else min(len(raw),131072)
        locations=[i for i in range(0,index_size,16) if raw[i:i+8]==donor]
        if locations:
            filename=f'{name}.bin';(out/filename).write_bytes(raw)
            refs.append({'root_offset':hex(0xf12000+o),'address':hex(p),'file':filename,
                         'type':name,'length':size,'schema_length':schema['size'],'index_size':index_size,
                         'donor_offsets':[hex(i) for i in locations]})
            if name=='EntitySettingsHashmap':
                pos=locations[0];component_ptr,component_count=struct.unpack_from('<QQ',raw,pos+8)
                component_bytes=read(component_ptr,component_count*2)
                (out/'entity_component_ids.bin').write_bytes(component_bytes)
                print('ENTITY COMPONENT IDS',struct.unpack('<'+'H'*component_count,component_bytes))
    info={'pid':pid,'base':hex(base),'root':hex(root),'eagle_table':hex(table),
          'stratagems':rows,'projectiles':projectiles,'donor_tables':refs}
    (out/'capture.json').write_text(json.dumps(info,indent=2));print(json.dumps(info,indent=2))
finally:K.CloseHandle(handle)
