"""Repair this addon's imported assets and four verified deployed archives.

The running manager's settings are left to the manager. Every overwritten
file is backed up, and its new digest is recorded. Refuse unknown game files.
"""
from pathlib import Path, PurePosixPath
from datetime import datetime
import os,json,zipfile,hashlib,subprocess

ROOT=Path(__file__).resolve().parents[1]
ARSENAL=Path(os.environ['LOCALAPPDATA'])/'hd2arsenal'
DATA=Path(r'E:\SteamLibrary\steamapps\common\Helldivers 2\data').resolve()
GUID='acffed9b-07c3-48f8-a936-19874038111b'
LOADER='612eaf70-d682-43c7-9efd-16dcc695f977'
sha=lambda b:hashlib.sha256(b).hexdigest()
state=json.loads((ARSENAL/'hd2a_data.json').read_text(encoding='utf-8'))
mods=state['modsList'][state['selectedProfile']]['mods']
mod=next(m for m in mods if m['uuid']==GUID)
loader=next(m for m in mods if m['uuid']==LOADER)
assert mod['enabled'] and loader['enabled']
assert sum(bool(m['enabled']) for m in mods)==2,'Verify additional enabled mods separately.'
cache=Path(mod['path']).resolve()
assert cache.parent==(ARSENAL/'mods').resolve()
assert mod['options'][0]['enabled']
selected={}
for option in mod['options'][1:]:
    assert option['enabled']
    choices=[x for x in option['suboptions'] if x['enabled']]
    assert len(choices)==1
    include=choices[0]['include'];assert len(include)==1
    axis=PurePosixPath(include[0]).parts[1]
    selected[axis]=include[0]
assert set(selected)=={'uses','cooldown'}

running=subprocess.run(['powershell','-NoProfile','-Command',
    '(Get-Process helldivers2 -ErrorAction SilentlyContinue | Measure-Object).Count'],
    capture_output=True,text=True,check=True)
assert running.stdout.strip()=='0','Exit the game before repair.'
with zipfile.ZipFile(ROOT/'research/failed_packages/NativeCarpetBomb_v0.3.0_STARTUP_FAILED.zip') as z:
    old_core=z.read('Core/9ba626afa44a3aa3.patch_0')
with zipfile.ZipFile(ROOT/'dist/NativeCarpetBomb_v0.3.1.zip') as z:
    new={n:z.read(n) for n in z.namelist()}
loader_bytes=(Path(loader['path'])/'data/9ba626afa44a3aa3.patch_0').read_bytes()
assert loader_bytes==(ROOT.parent/'Bingus-Shared-Loader-v18/data/9ba626afa44a3aa3.patch_0').read_bytes()
assert (DATA/'9ba626afa44a3aa3.patch_0').read_bytes() in (old_core,new['Core/9ba626afa44a3aa3.patch_0'])
existing={p.name for p in DATA.glob('9ba626afa44a3aa3.patch_*')
          if p.suffix not in ('.stream','.gpu_resources')}
assert existing in ({'9ba626afa44a3aa3.patch_0','9ba626afa44a3aa3.patch_3'},
                    {'9ba626afa44a3aa3.patch_0','9ba626afa44a3aa3.patch_1'},
                    {f'9ba626afa44a3aa3.patch_{i}' for i in range(4)})
loader_index=3 if '9ba626afa44a3aa3.patch_3' in existing else 1
assert (DATA/f'9ba626afa44a3aa3.patch_{loader_index}').read_bytes()==loader_bytes
if len(existing)==4:
    for axis,index in (('uses',1),('cooldown',2)):
        known={sha(body) for name,body in new.items() if name.startswith('Options/'+axis+'/')
               and name.endswith(f'.patch_{index}')}
        assert sha((DATA/f'9ba626afa44a3aa3.patch_{index}').read_bytes()) in known

backup=ROOT/'research/startup_repair'/datetime.now().strftime('%Y%m%d_%H%M%S')
backup.mkdir(parents=True,exist_ok=False)
receipt=[]
def replace(target,body,group,relative):
    target=target.resolve()
    assert target.is_relative_to(cache if group=='manager' else DATA)
    previous=target.read_bytes() if target.exists() else None
    saved=None
    if previous is not None:
        saved=backup/group/relative;saved.parent.mkdir(parents=True,exist_ok=True)
        saved.write_bytes(previous)
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.codex-tmp')
    assert not temporary.exists()
    temporary.write_bytes(body);os.replace(temporary,target)
    assert target.read_bytes()==body
    receipt.append({'target':str(target),'backup':str(saved) if saved else None,
        'before_sha256':sha(previous) if previous is not None else None,'after_sha256':sha(body)})

for name,body in new.items():
    parts=PurePosixPath(name).parts
    assert not PurePosixPath(name).is_absolute() and '..' not in parts
    replace(cache.joinpath(*parts),body,'manager',Path(*parts))
deployed=[('Core',0,0),(selected['uses'],1,1),(selected['cooldown'],2,2)]
for folder,source_index,target_index in deployed:
    for suffix in ('','.stream','.gpu_resources'):
        name=f'9ba626afa44a3aa3.patch_{target_index}'+suffix
        source=f'{folder}/9ba626afa44a3aa3.patch_{source_index}'+suffix
        replace(DATA/name,new[source],'game',Path(name))
for suffix in ('','.stream','.gpu_resources'):
    name='9ba626afa44a3aa3.patch_3'+suffix
    replace(DATA/name,loader_bytes if not suffix else b'','game',Path(name))

result={'version':'0.3.1','selected':selected,'manager_cache':str(cache),
        'game_data':str(DATA),'files':receipt,'loader_unchanged':True,
        'cold_start_verified':False}
(backup/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
(ROOT/'validation/manager_repair.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Repaired manager assets and game patches 0/1/2; verified v18 loader at 3.')
print('Selected presets:',selected)
print('Backup:',backup)
