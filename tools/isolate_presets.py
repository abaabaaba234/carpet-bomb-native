"""Quarantine only deployed files matching this addon's selected option resources."""
from pathlib import Path
import json,hashlib,zipfile,struct,shutil
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
DATA=Path(r'E:\SteamLibrary\steamapps\common\Helldivers 2\data').resolve()
with zipfile.ZipFile(ROOT/'research/failed_packages/NativeCarpetBomb_v0.3.0_STARTUP_FAILED.zip') as z:
    known={hashlib.sha256(z.read(n)).hexdigest():n for n in z.namelist()
           if n.startswith('Options/') and '.patch_' in n and not n.endswith(('.stream','.gpu_resources'))}
targets=[]
for path in DATA.glob('9ba626afa44a3aa3.patch_*'):
    if path.suffix in ('.stream','.gpu_resources'):continue
    if hashlib.sha256(path.read_bytes()).hexdigest() not in known:continue
    for suffix in ('','.stream','.gpu_resources'):
        p=Path(str(path)+suffix).resolve()
        assert p.parent==DATA
        if p.exists():targets.append(p)
assert len(targets)==6,'Expected exactly two option archives with their sidecars.'
out=ROOT/'research/startup_quarantine'/datetime.now().strftime('%Y%m%d_%H%M%S')
out.mkdir(parents=True,exist_ok=False)
receipt=[]
for p in targets:
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    shutil.move(str(p),str(out/p.name))
    receipt.append({'original':str(p),'saved':str(out/p.name),'sha256':digest})
(out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print('Quarantined:',[p.name for p in targets])
print('Core and loader retained; options temporarily use 2 charges / 15 seconds.')
