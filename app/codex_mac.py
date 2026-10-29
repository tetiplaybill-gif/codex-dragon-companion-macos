"""macOS Codex discovery: the desktop app by bundle id, its CLI, and link opening."""
import json,os,plistlib,shutil,subprocess,xml.parsers.expat
from functools import lru_cache
from pathlib import Path

BUNDLE_ID='com.openai.codex'
# psutil names of the desktop main executable (ChatGPT.app today, a future Codex.app).
NAMES=('chatgpt','codex')
APP_NAMES=('ChatGPT.app','Codex.app')

def app_bundle(exe):
    p=Path(exe)
    return p.parents[2] if len(p.parents)>2 and p.parent.name=='MacOS' and p.parents[1].name=='Contents' and p.parents[2].suffix=='.app' else None

@lru_cache(maxsize=64)
def _identity(info,stamp):
    try:
        with open(info,'rb') as f:value=plistlib.load(f)
        return str(value.get('CFBundleIdentifier','')),str(value.get('CFBundleExecutable',''))
    except (OSError,ValueError,AttributeError,xml.parsers.expat.ExpatError):return '',''

def bundle_identity(bundle):
    """(CFBundleIdentifier, CFBundleExecutable); keyed by mtime so a reinstall is seen."""
    info=Path(bundle)/'Contents/Info.plist'
    try:return _identity(str(info),info.stat().st_mtime_ns)
    except OSError:return '',''

def desktop_executable(exe):
    """Only the main app process; helpers (.helper*) and the CLI (.cli) have other ids."""
    bundle=app_bundle(exe)
    if bundle is None:return False
    ident,name=bundle_identity(bundle)
    return ident==BUNDLE_ID and Path(exe).name==name

def running_bundles():
    import psutil
    found=[]
    for process in psutil.process_iter(['name','exe']):
        try:
            # Filter by name first: exe() is None for other users' processes.
            if (process.info['name'] or '').lower() in NAMES and process.info['exe'] and desktop_executable(process.info['exe']):
                bundle=app_bundle(process.info['exe'])
                if bundle not in found:found.append(bundle)
        except (psutil.NoSuchProcess,psutil.AccessDenied,OSError):pass
    return found

def installed_bundles():
    found=running_bundles()
    for root in (Path('/Applications'),Path.home()/'Applications'):
        for name in APP_NAMES:
            bundle=root/name
            if bundle not in found and bundle_identity(bundle)[0]==BUNDLE_ID:found.append(bundle)
    if not found:
        try:
            out=subprocess.run(['/usr/bin/mdfind',f'kMDItemCFBundleIdentifier == "{BUNDLE_ID}"'],capture_output=True,text=True,timeout=3).stdout
            for line in out.splitlines():
                bundle=Path(line.strip())
                if bundle.suffix=='.app' and bundle not in found and bundle_identity(bundle)[0]==BUNDLE_ID:found.append(bundle)
        except (OSError,subprocess.TimeoutExpired):pass
    return found

def package_entry(root):
    """CLI entry of a codex-package.json layout, confined to that folder.

    The unresolved path is returned so the daemon's 'current' link keeps following updates."""
    root=Path(root)
    try:entry=json.loads((root/'codex-package.json').read_text(encoding='utf-8')).get('entrypoint') or 'bin/codex'
    except (OSError,ValueError,AttributeError):entry='bin/codex'
    path=root/str(entry)
    try:
        if path.resolve().is_relative_to(root.resolve()) and path.is_file() and os.access(path,os.X_OK):return path
    except OSError:pass
    return None

def bundled_cli(bundle):return package_entry(Path(bundle)/'Contents/Resources/codex-cli')

def cli_candidates(home):
    """The desktop app's own CLI first, as on Windows; then the daemon copy, PATH, Homebrew and npm."""
    for bundle in installed_bundles():
        path=bundled_cli(bundle)
        if path:yield path
    path=package_entry(Path(home)/'packages/app-server-daemon/current')
    if path:yield path
    which=shutil.which('codex')
    if which:yield Path(which)
    for path in (Path('/opt/homebrew/bin/codex'),Path('/usr/local/bin/codex')):
        if path.is_file() and os.access(path,os.X_OK):yield path
    prefixes=[Path('/opt/homebrew/lib'),Path('/usr/local/lib'),Path.home()/'.npm-global/lib']+sorted((Path.home()/'.nvm/versions/node').glob('*/lib'),reverse=True)
    for prefix in prefixes:
        base=prefix/'node_modules/@openai'
        for pattern in ('codex/vendor/*/codex/codex','codex-darwin-*/vendor/*/codex/codex','codex/node_modules/@openai/codex-darwin-*/vendor/*/codex/codex'):
            for path in base.glob(pattern):
                if path.is_file():yield path

def open_desktop(url=None):
    """Open a codex:// link, or launch/activate the app; False when Launch Services refuses."""
    args=['/usr/bin/open',url] if url else ['/usr/bin/open','-b',BUNDLE_ID]
    try:return subprocess.run(args,capture_output=True,timeout=8).returncode==0
    except (OSError,subprocess.TimeoutExpired):return False
