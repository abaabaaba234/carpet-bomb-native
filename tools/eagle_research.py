"""Offline code and captured-data inspection for the failed native grant."""
from pathlib import Path
import json,struct,sys
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'eagle-carpet-bomb'
sys.path.insert(0,str(ROOT.parent/'shield_vehicle_resupply/.v020-disassembler'))
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
md=Cs(CS_ARCH_X86,CS_MODE_64)
code=(OLD/'research/current/code.bin').read_bytes()
types=json.loads((ROOT.parent/'shield_vehicle_resupply/.frv-repair-work/references/all-types.json').read_text())
print('TYPE ROOT',type(types).__name__)
if isinstance(types,dict):
    for key,value in types.items():
        if 'eagle' in key.lower():print(key,json.dumps(value))
def dis(start,length):
    for i in md.disasm(code[start-0x1000:start-0x1000+length],start):
        print(f'{i.address:08x}: {i.bytes.hex():24s} {i.mnemonic} {i.op_str}')
target=0x514640
offset=0;xrefs=[]
while True:
    offset=code.find(b'\xe8',offset)
    if offset<0 or offset+5>len(code):break
    if offset+0x1000+5+struct.unpack_from('<i',code,offset+1)[0]==target:xrefs.append(offset+0x1000)
    offset+=1
print('EagleComponent accessor call sites:',[hex(x) for x in xrefs])
for a in xrefs:print('CALL CONTEXT',hex(a));dis(a-30,100)
data=(OLD/'research/current/eagle_table.bin').read_bytes()
for i in range(20):
    resource,index,unknown=struct.unpack_from('<QII',data,i*16)
    if index<11:
        row=data[320+index*152:320+(index+1)*152]
        print('RECORD',f'{resource:016x}',index,'WORDS',struct.unpack('<38I',row))
