"""Install a tracked test core without replacing any existing game patch."""
from pathlib import Path
import re,json,zipfile,hashlib
from build import VERSION
ROOT=Path(__file__).resolve().parents[1];DATA=Path(r'E:\SteamLibrary\steamapps\common\Helldivers 2\data')
receipt=ROOT/'validation/test_install.json';assert not receipt.exists(),'Inspect the existing test receipt first.'
indices=[int(m.group(1)) for p in DATA.iterdir() if (m:=re.fullmatch(r'9ba626afa44a3aa3\.patch_(\d+)',p.name))]
name=f'9ba626afa44a3aa3.patch_{max(indices,default=-1)+1}';files={}
with zipfile.ZipFile(ROOT/f'dist/NativeCarpetBomb_v{VERSION}.zip') as z:
    for suffix in ('','.stream','.gpu_resources'):
        content=z.read('Core/9ba626afa44a3aa3.patch_0'+suffix);path=DATA/(name+suffix)
        with path.open('xb') as f:f.write(content)
        files[str(path)]=hashlib.sha256(content).hexdigest()
receipt.write_text(json.dumps({'purpose':'Native CarpetBomb repaired-payload verification','version':VERSION,'files':files},indent=2))
print('Installed native test:',DATA/name,'; 2 charges / 15 s; reconstructed native payload.')
