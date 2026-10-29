"""Assemble canonical HD resources from verified old public media + seam inputs."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader
ROOT=Path(__file__).resolve().parents[1]
BASE_SHA='dd0eb2cce241bcdb82f29c5d14efc6ae6fcdb4d8160f10cc634cbfb740a8be28'
PREFIX='outputs/白龙桌宠素材/'
def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def assemble(base,inputs,out,work):
    base,inputs,out,work=map(Path,(base,inputs,out,work));work.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    assert digest(base)==BASE_SHA,'Base public ZIP SHA mismatch'
    catalog=json.loads((ROOT/'app/material_catalog.json').read_text(encoding='utf-8'));tier=catalog['tiers']['hd'];records=tier['files']
    with zipfile.ZipFile(base) as z:
        names=[n for n in z.namelist() if n.endswith('.exe') and '一键部署' in n];assert len(names)==1
        exe=work/'base-installer.exe'
        with z.open(names[0]) as source,exe.open('wb') as target:shutil.copyfileobj(source,target,1024*1024)
    # Read the embedded payload as data; never execute an old installer.
    payload=work/'base-payload.zip';payload.write_bytes(CArchiveReader(str(exe)).extract('payload.zip'))
    target=out/('bailong-hd-'+tier['id']+'.zip');temp=target.with_suffix('.tmp');proof=[]
    with zipfile.ZipFile(payload) as old,zipfile.ZipFile(inputs) as delta,zipfile.ZipFile(temp,'w',zipfile.ZIP_STORED,allowZip64=True) as result:
        assert len(delta.namelist())==len(set(delta.namelist()))
        assert set(delta.namelist())=={r['path'] for r in records if r['path'].startswith('quality-v5/')}
        for record in records:
            name=record['path'];info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.create_system=3;info.compress_type=zipfile.ZIP_STORED;info.external_attr=0o100644<<16
            if name=='素材清单.json':source=(ROOT/'outputs/白龙桌宠素材/素材清单.json').open('rb')
            elif name in delta.namelist():source=delta.open(name)
            else:source=old.open(PREFIX+name)
            h=hashlib.sha256();size=0
            with source,result.open(info,'w',force_zip64=True) as dest:
                while chunk:=source.read(1024*1024):h.update(chunk);size+=len(chunk);dest.write(chunk)
            assert size==record['bytes'] and h.hexdigest()==record['sha256'],'HD source mismatch: '+name
            proof.append(dict(path=name,bytes=size,sha256=h.hexdigest()))
    temp.replace(target)
    with zipfile.ZipFile(target) as z:assert z.testzip() is None
    result=dict(passed=True,materialId=tier['id'],files=proof,bytes=target.stat().st_size,sha256=digest(target),archive=target.name,basePublicZipSha256=BASE_SHA)
    (out/'assembly-proof.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'SHA256SUMS.txt').write_text(result['sha256']+'  '+target.name+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True);return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True);p.add_argument('--inputs',required=True);p.add_argument('--out',required=True);p.add_argument('--work',required=True);a=p.parse_args();assemble(a.base,a.inputs,a.out,a.work)
