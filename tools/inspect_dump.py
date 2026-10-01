"""Inspect a local Windows minidump without executing or altering the target."""
from pathlib import Path
import json,struct,sys

dump=Path(sys.argv[1]).read_bytes()
assert dump[:4]==b'MDMP'
def unpack(fmt,offset):return struct.unpack_from('<'+fmt,dump,offset)
count,directory=unpack('II',8)
streams={}
for i in range(count):
    kind,size,rva=unpack('III',directory+i*12);streams[kind]=(rva,size)
modules=[]
if 4 in streams:
    p,_=streams[4];n=unpack('I',p)[0]
    for i in range(n):
        q=p+4+i*108;base,size,checksum,timestamp,name=unpack('QIIII',q)
        length=unpack('I',name)[0]
        modules.append({'name':dump[name+4:name+4+length].decode('utf-16-le'),
                        'base':base,'size':size,'timestamp':timestamp})
def identify(address):
    for m in modules:
        if m['base']<=address<m['base']+m['size']:
            return Path(m['name']).name+'+'+hex(address-m['base'])
    return hex(address)
memory=[]
if 5 in streams:
    p,_=streams[5]
    for i in range(unpack('I',p)[0]):
        start,size,rva=unpack('QII',p+4+i*16);memory.append((start,size,rva))
if 9 in streams:
    p,_=streams[9];n,rva=unpack('QQ',p)
    for i in range(n):
        start,size=unpack('QQ',p+16+i*16);memory.append((start,size,rva));rva+=size
def read(address,length):
    for start,size,rva in memory:
        if start<=address and address+length<=start+size:
            return dump[rva+address-start:rva+address-start+length]
    return b''
assert 6 in streams,'No exception stream'
p,_=streams[6];thread=unpack('I',p)[0]
code,flags,record,address,n=unpack('IIQQI',p+8)
parameters=unpack('Q'*min(n,15),p+40)
size,rva=unpack('II',p+160)
registers={name:unpack('Q',rva+offset)[0] for name,offset in
           [('rax',120),('rcx',128),('rdx',136),('rbx',144),('rsp',152),('rbp',160),
            ('rsi',168),('rdi',176),('r8',184),('r9',192),('r10',200),('r11',208),
            ('r12',216),('r13',224),('r14',232),('r15',240),('rip',248)]}
stack=read(registers['rsp'],512);candidates=[]
for i in range(0,len(stack),8):
    value=struct.unpack_from('<Q',stack,i)[0];label=identify(value)
    if '+' in label:candidates.append({'stack_offset':hex(i),'candidate':label})
result={'thread':thread,'exception':hex(code),'instruction':identify(address),
        'parameters':[hex(v) for v in parameters],
        'registers':{k:identify(v) for k,v in registers.items()},
        'stack_module_addresses':candidates,
        'game_modules':[{'name':Path(m['name']).name,'base':hex(m['base']),
                         'size':hex(m['size']),'timestamp':hex(m['timestamp'])}
                        for m in modules if Path(m['name']).name.lower() in ('game.dll','helldivers2.exe')]}
print(json.dumps(result,indent=2))
if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,indent=2),encoding='utf-8')
