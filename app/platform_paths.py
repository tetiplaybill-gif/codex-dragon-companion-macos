"""Per-platform user folders. Windows keeps its original LOCALAPPDATA layout."""
import os,sys
from pathlib import Path

WINDOWS=sys.platform=='win32'
MACOS=sys.platform=='darwin'
APP_ID='BailongEnhanced'
BUNDLE_ID='io.github.wunsch2048.bailong-enhanced'
# Hide console windows of helper processes; other systems take no flag.
NO_WINDOW=0x08000000 if WINDOWS else 0

def local_appdata():
    # An explicit LOCALAPPDATA also isolates tests and QA runs on macOS.
    value=os.environ.get('LOCALAPPDATA')
    if value:return Path(value)
    if MACOS:return Path.home()/'Library/Application Support'
    return Path.home()

def data_dir():return local_appdata()/APP_ID

def instance_server_name():
    """Keep explicit macOS data directories isolated from the normal desktop pet."""
    base='bailong-enhanced-local-v1'
    if MACOS and os.environ.get('LOCALAPPDATA'):
        import hashlib
        profile=str(data_dir().expanduser().resolve())
        return base+'-profile-'+hashlib.sha256(profile.encode('utf-8')).hexdigest()[:20]
    return base

def install_root():return local_appdata()/'Programs'/APP_ID

def startup_folder():
    """Windows per-user Startup folder; macOS uses a LaunchAgent instead."""
    return Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup'

def launch_agents():
    # LOCALAPPDATA is only set on macOS to isolate tests/QA; keep their agents out of the real login.
    value=os.environ.get('LOCALAPPDATA')
    return Path(value)/'LaunchAgents' if value and MACOS else Path.home()/'Library/LaunchAgents'

def launch_agent(name=''):
    """(plist path, label) of a per-user LaunchAgent; name '' is the pet itself."""
    label=BUNDLE_ID+('.'+name if name else '');return launch_agents()/(label+'.plist'),label

def write_launch_agent(path,label,args,**extra):
    """Start at the next login only; nothing is loaded into launchd now."""
    import plistlib
    args=[str(a) for a in args]
    if '/AppTranslocation/' in args[0]:raise OSError('请先把白龙桌宠移到“应用程序”文件夹，再开启登录启动')
    # Children (watcher <-> pet) must survive this job exiting, as they do on Windows.
    data=plistlib.dumps(dict(Label=label,ProgramArguments=args,RunAtLoad=True,KeepAlive=False,AbandonProcessGroup=True,
        LimitLoadToSessionType='Aqua',WorkingDirectory=str(app_root()),**extra))
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_bytes(data);os.chmod(temp,0o644);os.replace(temp,path)

def launch_agent_args(path):
    """ProgramArguments of a run-at-login agent, or None when missing or unreadable."""
    import plistlib,xml.parsers.expat
    try:
        with open(path,'rb') as f:value=plistlib.load(f)
    except (OSError,ValueError,xml.parsers.expat.ExpatError):return None
    return value.get('ProgramArguments') if isinstance(value,dict) and value.get('RunAtLoad') is True else None

def background_python():
    """Interpreter for detached helpers: pythonw on Windows, the current one elsewhere."""
    return Path(sys.executable).with_name('pythonw.exe') if WINDOWS else Path(sys.executable)

def app_root():
    """Folder holding app/ and outputs/: the source tree, the Windows install folder, or a macOS bundle's Resources."""
    if getattr(sys,'frozen',False):
        exe=Path(sys.executable).resolve()
        return exe.parents[1]/'Resources' if MACOS and exe.parent.name=='MacOS' else exe.parent
    return Path(__file__).resolve().parents[1]
