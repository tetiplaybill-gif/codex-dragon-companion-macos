"""Import only active animation files from the installed release for source use."""
import argparse,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from desktop_services import all_items
from sustained_assets import seam_items

def import_assets(source,dest):
    source=Path(source).resolve()
    if (source/'outputs/白龙桌宠素材/素材清单.json').is_file():source=source/'outputs/白龙桌宠素材'
    dest=Path(dest).resolve()/'outputs/白龙桌宠素材'
    data=json.loads((source/'素材清单.json').read_text(encoding='utf-8'))
    pairs=[]
    for item in all_items(data)+seam_items(data):
        name=item.get('playbackFile') or item['file'];src=(source/name).resolve();out=(dest/name).resolve()
        if not src.is_relative_to(source) or not out.is_relative_to(dest):raise ValueError('素材路径越界')
        if not src.is_file():raise FileNotFoundError(src)
        pairs.append((src,out))
    for src,out in pairs:
        out.parent.mkdir(parents=True,exist_ok=True)
        if src!=out:shutil.copy2(src,out)
    dest.mkdir(parents=True,exist_ok=True)
    if source!=dest:shutil.copy2(source/'素材清单.json',dest/'素材清单.json')
    return len(pairs)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path);args=p.parse_args();source=args.source
    if source is None:
        root=Path(os.environ['LOCALAPPDATA'])/'Programs/BailongEnhanced'
        record=json.loads((root/'installations.json').read_text(encoding='utf-8'))
        source=(root/'versions'/record['current']).resolve()
        if source.parent!=(root/'versions').resolve():raise ValueError('安装路径无效')
        if (source/'app/material_catalog.json').is_file():
            from material_store import MaterialStore
            store=MaterialStore(source,Path(os.environ['LOCALAPPDATA'])/'BailongEnhanced')
            if not store.available('hd'):raise ValueError('源码构建需高清原素材：请先在设置中下载高清，或用 --source 指定已解压的高清素材目录。')
            source=store.tier_root('hd');store.verify(source,'hd')
    print(f'已导入 {import_assets(source,ROOT)} 段播放素材；未读取设置、账号、聊天或统计。')
