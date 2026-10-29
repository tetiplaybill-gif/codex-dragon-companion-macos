"""GitHub Actions-only HD release assembly; never changes stable Latest."""
import hashlib,json,os,re,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO='Wunsch2048/codex-bailong-desktop-pet';API='repos/'+REPO
catalog=json.loads((ROOT/'app/material_catalog.json').read_text(encoding='utf-8'));tier=catalog['tiers']['hd'];TAG='materials-'+tier['id']
def gh(*args,raw=False):
    data=subprocess.check_output(['gh',*args]);return data if raw else json.loads(data)
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def draft():
    assert os.environ['GITHUB_ACTIONS']=='true' and os.environ['GITHUB_REPOSITORY']==REPO
    rid=os.environ['RELEASE_ID'];assert rid.isdecimal()
    r=gh('api',API+'/releases/'+rid)
    assert r['tag_name']==TAG and r['draft'] and r['prerelease']
    return r
def prepare():
    r=draft();aid=os.environ['INPUT_ASSET_ID'];expected=os.environ['INPUT_SHA']
    assert aid.isdecimal() and re.fullmatch('[0-9a-f]{64}',expected)
    asset=next(a for a in r['assets'] if str(a['id'])==aid)
    assert asset['name']=='hd-seam-inputs.zip' and asset['digest']=='sha256:'+expected and asset['state']=='uploaded'
    work=ROOT/'hd-work';work.mkdir(exist_ok=True)
    with (work/'inputs.zip').open('wb') as f:subprocess.run(['gh','api','-H','Accept: application/octet-stream',API+'/releases/assets/'+aid],stdout=f,check=True)
    assert sha(work/'inputs.zip')==expected
    url='https://github.com/'+REPO+'/releases/download/v0.7.2/bailong-desktop-pet-0.7.2-windows-x64.zip'
    with urllib.request.urlopen(url,timeout=90) as source,(work/'base.zip').open('wb') as target:
        while block:=source.read(1024*1024):target.write(block)
    print('Downloaded public base and verified seam inputs',flush=True)
def publish():
    r=draft();out=ROOT/'hd-output';proof=json.loads((out/'assembly-proof.json').read_text(encoding='utf-8'))
    assert proof['passed'] and proof['materialId']==tier['id'] and proof['sha256']==os.environ['EXPECTED_SHA']
    assert proof['bytes']==(out/proof['archive']).stat().st_size
    assert sha(out/proof['archive'])==proof['sha256']
    names=(proof['archive'],'SHA256SUMS.txt','assembly-proof.json')
    for name in names:
        existing=next((a for a in gh('api',r['assets_url']) if a['name']==name),None)
        if existing:assert existing['state']=='uploaded' and existing['digest']=='sha256:'+sha(out/name)
        else:subprocess.run(['gh','release','upload',TAG,str(out/name),'--repo',REPO],check=True)
    for name in names:
        asset=next(a for a in gh('api',r['assets_url']) if a['name']==name)
        assert asset['state']=='uploaded' and asset['digest']=='sha256:'+sha(out/name) and asset['size']==(out/name).stat().st_size
    gh('api','--method','DELETE',API+'/releases/assets/'+os.environ['INPUT_ASSET_ID'],raw=True)
    gh('api','--method','PATCH',API+'/releases/'+str(r['id']),'-F','draft=false','-F','prerelease=true','-f','make_latest=false')
    print('HD resource verified and published as prerelease; stable Latest unchanged',flush=True)
if __name__=='__main__':
    {'prepare':prepare,'publish':publish}[sys.argv[1]]()
