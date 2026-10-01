"""Build the standalone v18 native CarpetBomb addon and independent manager presets."""
from pathlib import Path
import struct,json,hashlib,zipfile
from preset_bytecode import encode as preset_bytecode
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.4.0';MASK=(1<<64)-1
def murmur64(data):
    m=0xc6a4a7935bd1e995;h=len(data)*m&MASK
    for i in range(0,len(data)//8*8,8):
        k=int.from_bytes(data[i:i+8],'little')*m&MASK;k^=k>>47;k=k*m&MASK;h=(h^k)*m&MASK
    tail=data[len(data)//8*8:]
    if tail:h=(h^int.from_bytes(tail,'little'))*m&MASK
    h^=h>>47;h=h*m&MASK;return h^(h>>47)
def patch(resource,source):
    body=struct.pack('<II',len(source),2)+source;offset=192
    # Tiny 224/240-byte option archives crash the native resource resolver
    # before Lua starts. Reserve one page while keeping exact resource lengths.
    size=max(4096,(offset+len(body)+15)&~15);kind=0xa14e8dfa2cd117e2
    header=struct.pack('<IIII',0xf0000011,1,1,0)+bytes(16)+struct.pack('<Q',size)+bytes(32)
    type_entry=struct.pack('<IIQQII',0,0,kind,1,16,16)
    entry=struct.pack('<7Q6I',murmur64(resource.encode()),kind,offset,0,0,0,0,len(body),0,0,16,16,0)
    return header+type_entry+entry+bytes(offset-len(header+type_entry+entry))+body+bytes(size-offset-len(body))
def build():
    files={}
    def add(folder,index,resource,source):
        name=f'{folder}/9ba626afa44a3aa3.patch_{index}'
        files[name]=patch(resource,source);files[name+'.stream']=b'';files[name+'.gpu_resources']=b''
    add('Core',0,'mods/carpet_bomb_native/core',(ROOT/'src/core.lua').read_bytes().replace(b'\r\n',b'\n'))
    options=[{'Name':'核心 / Core','Description':'修复地毯轰炸缺失的实体组件和进场高度，作为补给附带的额外战备进入任务。需要 v18 加载器。','Include':['Core']}]
    for index,(axis,title,values,description) in enumerate([
        ('uses','使用次数 / Charges',[2,1,3,4,5,6,8,10,-1],'默认 2 次；使用个人飞鹰次数与补给机制。'),
        ('cooldown','调用冷却（每次使用之间） / Call Interval',[15,900,0,5,10,30,60,120,300,600],'地毯式轰炸每次使用之间的基础冷却，默认 15 秒。'),
        ('rearm','飞鹰返航装填冷却 / Eagle Rearm',[-1,0,5,10,15,30,60,120,150,180,300,600,900],
         '次数耗尽后飞鹰返回装填的基础冷却，也适用于手动重新武装。所有携带的飞鹰战备共用，舰船升级仍按原版计算。默认保持原版。'),
    ],1):
        choices=[]
        for n in values:
            folder=f'Options/{axis}/{"unlimited" if axis=="uses" and n==-1 else "vanilla" if n==-1 else n}'
            add(folder,index,'mods/carpet_bomb_native/'+axis,preset_bytecode(n))
            label='无限 / Unlimited' if axis=='uses' and n==-1 else '保持原版 / Vanilla' if n==-1 else f'{n} 次' if axis=='uses' else f'{n} 秒'
            choices.append({'Name':label,'Description':description,'Include':[folder]})
        options.append({'Name':title,'Description':description+' 部署后重启并进入新任务。','SubOptions':choices})
    manifest={'Version':1,'Guid':'acffed9b-07c3-48f8-a936-19874038111b','Name':'原生地毯轰炸默认携带 / Native CarpetBomb v'+VERSION,
      'Description':'原生地毯式轰炸自动携带，不占四个自选槽位。可分别设置使用次数、每次使用之间的冷却，以及飞鹰返航装填冷却。需要 Bingus Shared Loader v18；支持 Steam build 25480438。', 'Options':options}
    # Arsenal's import can decode text with the Windows ANSI code page.
    # JSON escapes retain the Chinese labels under either text encoding.
    files['manifest.json']=json.dumps(manifest,ensure_ascii=True,indent=2).encode('ascii')
    for name in ('README_中文.md','CREDITS.md'):files[name]=(ROOT/name).read_bytes()
    if (ROOT/'validation/report.json').exists():files['VALIDATION.json']=(ROOT/'validation/report.json').read_bytes()
    output=ROOT/'dist'/f'NativeCarpetBomb_v{VERSION}.zip';output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,body in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,10,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,body)
    (ROOT/'manifest.json').write_bytes(files['manifest.json'])
    print(output);print('SHA256',hashlib.sha256(output.read_bytes()).hexdigest());return output
if __name__=='__main__':build()
