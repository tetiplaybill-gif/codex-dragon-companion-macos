"""Content-addressed hard links for new versions; old installs stay untouched."""
import hashlib,json,os,re
from pathlib import Path

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def object_path(root,sha):
    if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError('共享素材标识无效')
    root=Path(root).resolve();base=root/'shared-assets'
    if base.is_symlink() or base.resolve().parent!=root:raise ValueError('共享素材目录无效')
    p=base/(sha+'.webp')
    if p.is_symlink():raise ValueError('共享素材对象不能是符号链接')
    return p
def share(dest,root,register_new=lambda sha:None):
    manifest=dest/'payload-manifest.json'
    if not manifest.is_file():return []
    data=json.loads(manifest.read_text(encoding='utf-8'));records=[]
    for name,value in data['files'].items():
        if not name.startswith('outputs/白龙桌宠素材/') or not name.endswith('.webp'):continue
        path=(dest/name).resolve()
        if not path.is_relative_to(dest.resolve()):raise ValueError('共享素材路径无效')
        sha=value['sha256'];obj=object_path(root,sha);mode='private'
        try:
            obj.parent.mkdir(parents=True,exist_ok=True);exists=obj.exists()
            valid=exists and obj.is_file() and obj.stat().st_size==value['bytes'] and digest(obj)==sha
        except OSError:
            records.append(dict(path=name,sha256=sha,bytes=value['bytes'],mode=mode));continue
        if exists:
            if valid:
                temp=path.with_suffix('.link.tmp')
                try:os.link(obj,temp);os.replace(temp,path);mode='hardlink'
                except OSError:temp.unlink(missing_ok=True)
        else:
            register_new(sha)  # Durable journal before the first new object.
            try:os.link(path,obj);mode='hardlink'
            except OSError:pass  # Unsupported volume: retain the verified copy.
        records.append(dict(path=name,sha256=sha,bytes=value['bytes'],mode=mode))
    return records
def cleanup_new(root,identifiers):
    for sha in identifiers:
        obj=object_path(root,sha)
        # Only this failed transaction's unreferenced, intact objects qualify.
        if obj.is_file() and obj.stat().st_nlink==1 and digest(obj)==sha:obj.unlink()
def verify_version(folder,records):
    for item in records or []:
        path=(folder/item['path']).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file() or digest(path)!=item['sha256']:raise ValueError('回退素材不完整，未更改现有入口。')
