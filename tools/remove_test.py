"""Remove only unchanged test files from this project's installation receipt."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];DATA=Path(r'E:\SteamLibrary\steamapps\common\Helldivers 2\data').resolve()
receipt=ROOT/'validation/test_install.json';checked=[]
target=ROOT/'validation/test_install_removed.json'
if target.exists():
    version=json.loads(receipt.read_text()).get('version','legacy')
    assert re.fullmatch(r'[a-zA-Z0-9._-]+',version)
    target=ROOT/f'validation/test_install_removed_{version}.json'
    attempt=2
    while target.exists():
        target=ROOT/f'validation/test_install_removed_{version}_{attempt}.json'
        attempt+=1
for name,digest in json.loads(receipt.read_text())['files'].items():
    p=Path(name).resolve()
    assert p.parent==DATA and re.fullmatch(r'9ba626afa44a3aa3\.patch_\d+(?:\.stream|\.gpu_resources)?',p.name)
    if not p.exists():continue
    assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,'Test file changed; inspect it before removal: '+str(p)
    checked.append(p)
for p in checked:p.unlink();print('Removed',p.name)
receipt.rename(target)
