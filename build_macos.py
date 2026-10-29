"""Local macOS .app build (ad-hoc signed, not notarized); no installer, signing identity or upload.

Every run writes to new build/macos-<version>-<time> and release/macos-<version>-<time>
folders and never deletes anything, so earlier builds stay in place. --dmg also
writes a drag-to-Applications disk image and its SHA-256 next to the .app."""
import argparse,hashlib,json,platform,plistlib,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'app'))
from version import VERSION, DISPLAY_VERSION
from desktop_services import all_items
from sustained_assets import seam_items
from platform_paths import BUNDLE_ID
NAME='BailongEnhanced'
# Community macOS release number on top of the upstream version; bump the suffix per macOS release.
MAC_VERSION=DISPLAY_VERSION
# Data the frozen app reads below platform_paths.app_root() (Contents/Resources).
DATA=['app/fonts','app/sounds','app/branding','app/licenses','app/material_catalog.json','app/book_catalog.json']

def fresh(parent,stamp):
    """A new, empty folder for this run; an existing one is never reused or cleaned."""
    path=ROOT/parent/f'macos-{VERSION}-{stamp}'
    if path.exists():raise SystemExit(f'构建目录已存在，未改动：{path}。请稍后重试。')
    path.mkdir(parents=True);return path

def icon(work):
    """Build an .icns from the Windows .ico; the largest frame is 256 px."""
    from PIL import Image
    iconset=work/'bailong.iconset';iconset.mkdir()
    with Image.open(ROOT/'app/branding/bailong.ico') as im:
        im.size=max(im.ico.sizes());source=im.convert('RGBA')
    for px in (16,32,64,128,256,512):
        source.resize((px,px),Image.Resampling.LANCZOS).save(iconset/f'icon_{px}x{px}.png')
        if px<=256:source.resize((px*2,px*2),Image.Resampling.LANCZOS).save(iconset/f'icon_{px}x{px}@2x.png')
    target=work/'bailong.icns';subprocess.run(['iconutil','-c','icns',str(iconset),'-o',str(target)],check=True)
    return target

def materials():
    """Return (root, files) of the light playback set, verified against the catalog.

    MaterialStore treats the bundled base folder as the light tier; HD stays a
    separate, downloaded and verified tier, as in the Windows release."""
    source=ROOT/'outputs/白龙桌宠素材';manifest=json.loads((source/'素材清单.json').read_text(encoding='utf-8'))
    names=sorted({item.get('playbackFile') or item['file'] for item in all_items(manifest)+seam_items(manifest)})
    from asset_pack import digest
    light=ROOT/'build/materials/light';catalog=json.loads((ROOT/'app/material_catalog.json').read_text(encoding='utf-8'))
    expected={f['path']:f['sha256'] for f in catalog['tiers']['light']['files']}
    for name in names:
        if not (light/name).is_file() or digest(light/name)!=expected[name]:raise SystemExit(f'轻量素材与目录不一致：{name}。先运行 build_materials.py。')
    return light,names

def disk_image(bundle,work,dist):
    """Compressed read-only image with the app and an Applications link; the app keeps its signature."""
    stage=work/'dmg';stage.mkdir()
    subprocess.run(['ditto',str(bundle),str(stage/bundle.name)],check=True)
    (stage/'Applications').symlink_to('/Applications')
    image=dist/f'{NAME}-{MAC_VERSION}-macos-{platform.machine()}.dmg'
    subprocess.run(['hdiutil','create','-volname','白龙桌宠','-srcfolder',str(stage),'-fs','HFS+','-format','UDZO',str(image)],check=True)
    subprocess.run(['hdiutil','verify',str(image)],check=True)
    h=hashlib.sha256()
    with image.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    # `shasum -a 256 -c` reads this "<digest>  <name>" line from the download folder.
    Path(f'{image}.sha256').write_text(f'{h.hexdigest()}  {image.name}\n',encoding='utf-8')
    print(f'已生成 {image}')
    return image

def build(cards_only=False,dmg=False):
    """Bundle the light set, or nothing with cards_only: animations are then downloaded in settings, as with the Windows card-only package."""
    if sys.platform!='darwin':raise SystemExit('只能在 macOS 上构建 .app')
    root,names=(None,[]) if cards_only else materials()
    stamp=time.strftime('%Y%m%d-%H%M%S');work=fresh('build',stamp);dist=fresh('release',stamp)
    stage=work/'materials'
    if not cards_only:
        for name in names+['素材清单.json']:
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
            # APFS clone: no extra disk space for the staged copy.
            subprocess.run(['cp','-c',str(root/name),str(target)],check=True)
    # Both paths are new and empty, so PyInstaller has nothing to replace; the
    # wrapper also refuses any recursive delete it might still attempt.
    args=[sys.executable,str(ROOT/'tools/pyinstaller_keep_files.py'),'--windowed','--onedir','--name',NAME,'--osx-bundle-identifier',BUNDLE_ID,
          '--icon',str(icon(work)),'--distpath',str(dist),'--workpath',str(work/'work'),'--specpath',str(work),'--paths',str(ROOT/'app'),
          '--exclude-module','imageio_ffmpeg','--exclude-module','comtypes','--exclude-module','pefile']
    for item in DATA:
        source=ROOT/item;args+=['--add-data',f'{source}:{Path(item).parent if source.is_file() else item}']
    if not cards_only:args+=['--add-data',f'{stage}:outputs/白龙桌宠素材']
    args.append(str(ROOT/'app/enhanced.py'))
    subprocess.run(args,cwd=ROOT,check=True)
    bundle=dist/f'{NAME}.app';info=bundle/'Contents/Info.plist'
    with info.open('rb') as f:plist=plistlib.load(f)
    plist.update(CFBundleName='白龙桌宠',CFBundleDisplayName='白龙桌宠',CFBundleShortVersionString=MAC_VERSION,CFBundleVersion=VERSION,
                 LSUIElement=True,NSHighResolutionCapable=True,LSMinimumSystemVersion='12.0')
    with info.open('wb') as f:plistlib.dump(plist,f)
    # Editing Info.plist breaks PyInstaller's ad-hoc signature; arm64 needs one to launch.
    subprocess.run(['codesign','--force','--deep','--sign','-',str(bundle)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(bundle)],check=True)
    print(f'已构建 {bundle}（{"仅卡片，动画可在设置中下载" if cards_only else "内置轻量素材"}；ad-hoc 签名，未公证）')
    if dmg:disk_image(bundle,work,dist)
    return bundle

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cards-only',action='store_true',help='不内置动画；启动后在 设置 → 角色与素材 中下载轻量或高清动画')
    parser.add_argument('--dmg',action='store_true',help='同时生成可拖入“应用程序”的 .dmg 及其 SHA-256')
    options=parser.parse_args()
    build(options.cards_only,options.dmg)
