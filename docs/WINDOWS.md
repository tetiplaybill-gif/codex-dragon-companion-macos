# Windows 源码运行

本页面向 Windows 10 1809+ / Windows 11、x64 和 Python 3.12 64 位。本仓库只公开源码，不提供 EXE 或 MSI 安装包。当前为社区预览版，Windows 真实桌面的完整验收尚未完成；Windows Server 2022 上的 CI、导入与离屏界面测试不能代替 Windows 10/11 的实际使用验证。

## 准备与启动

准备 Git 和 Python 3.12 x64，在 PowerShell 中执行：

```powershell
git clone --branch main https://github.com/tetiplaybill-gif/codex-dragon-companion-macos.git
cd codex-dragon-companion-macos
py -3.12 -c "import struct; print(struct.calcsize('P') * 8)"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-windows.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe app\enhanced.py
```

位数检查应输出 `64`。若系统没有 `py` 启动器，可用已安装的 Python 3.12 x64 可执行文件替换前两条 `py` 命令。这里直接调用虚拟环境里的 Python，无需激活脚本或修改 PowerShell 执行策略。

`requirements-windows.lock` 固定 Windows wheel 版本和 SHA-256，不能换用 macOS 锁文件。默认六项依赖包含 PySide6 Essentials、图像解码、进程与任务读取组件，以及 Windows 视频识别所需的 `comtypes`。依赖来源记录见 [windows-dependencies.json](windows-dependencies.json)。启动和运行不需要管理员权限；受组织策略限制的电脑可能无法注册启动项，应保留系统原有策略。

只有导入 WebM 素材并需要转换时，才额外安装含 FFmpeg 的可选依赖；轻量 WebP 动画无需这一步：

```powershell
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-windows-media.lock
```

## 人物、Codex 与公告

没有动画资源时先显示卡片。在“设置 → 素材（角色与素材）”选择“轻量 512px”，点击“下载并启用”。资源从原发布源按需下载并校验；准备好后等待当前动作的安全边界再切换。动画资源不包含在 Git 源码中，授权边界见 [NOTICE](../NOTICE.md)。

打开已安装并登录的 Codex 桌面应用，再用“检测连接与额度”检查连接。任务和 Token 用量来自本机 Codex 数据，账户额度依赖本机 Codex CLI 连接；无法确认的状态应显示未知或缓存，不等同于零。基础联动无需配置额外模型 API 密钥。WSL 连接是独立选项，使用对应 Linux 环境的登录，不应与 Windows 数据混为一谈。

公开公告无需 X 账号或付费 API：第三方 [Codex Resets](https://codex-resets.com/) 提供重置汇总，[Codex 官方更新记录](https://learn.chatgpt.com/docs/changelog) 提供产品更新，各来源只显示最新一条。默认每 15 分钟检查，受缓存与网络延迟影响；可调整间隔或静音。首次同步和功能更新不响铃。重置公告不代表当前账户额度已经到账，也不是个人 X 账号的全量推文同步。

## 随 Codex 启动与停止

新配置默认关闭启动联动。在“设置 → Codex → 启动与退出”开启“随 Windows Codex 桌面端启动”，再点击“应用”。它为当前 Windows 用户注册 `BailongCodexSync.vbs`，运行轻量监听；检测到 Codex 桌面主进程后启动桌宠。识别的是 Codex 桌面应用，单独运行 Codex CLI 或名称相似的 ChatGPT 应用不会代替它。

“登录 Windows 时启动”是独立选项，会在登录时直接启动桌宠；只想随 Codex 启动时无需开启。“Codex 桌面端关闭后退出桌宠”也单独选择，在确认 Codex 关闭后约 6 秒生效。手动退出桌宠后，本次 Codex 使用期间不会反复拉起，可按需手动再次运行。

关闭联动时，关闭“随 Windows Codex 桌面端启动”以及不再需要的“登录 Windows 时启动”，点击“应用”，再从托盘或菜单选择“退出桌宠”。启动项保存在当前用户的 Windows 启动文件夹，引用当前源码和虚拟环境的位置；移动或删除这些目录前应先停用，迁移后从新位置运行并重新启用。系统若禁用 Windows Script Host，启动项可能无法运行；可直接使用上述 Python 命令启动，无需放宽安全设置。

## 全屏视频与验证边界

Windows 的“全屏视频时让位”识别受支持的播放器或浏览器视频，只调整与视频所在屏幕相交的桌宠窗口层级，另一屏上的人物或面板保留置顶。它不会像 macOS 的隐藏处理那样暂停人物动画。未读完成提醒优先；提醒确认后可恢复让位，手动关闭“始终置顶”不会被自动重新开启。

这一逻辑已有模拟原生窗口的回归测试，覆盖混合双屏、跨屏恢复、未读完成提醒和手动关闭置顶。真实播放器、浏览器辅助功能、混合 DPI、任务栏/托盘、系统主题、音效与长期动画运行仍需 Windows 实机验证。CI 的成功只能证明相应测试覆盖范围；当前不宣称已完成这些桌面场景的验收。

## 更新与保留数据卸载

程序自动下载和安装已停用。更新时退出桌宠，获取新源码并使用对应 Windows 锁文件重新检查依赖，再运行 `app\enhanced.py`；先保留本地代码改动。素材下载与程序更新独立。

需要移除时，先按上文关闭启动项并退出桌宠，再移除不再需要的源码及虚拟环境。默认应用数据位于 `%LOCALAPPDATA%\BailongEnhanced\`，保留该目录可保留设置、素材和统计缓存；不要为卸载桌宠而删除 Codex 登录或任务数据。反馈问题时只提供系统版本、Python 位数、复现步骤和必要的脱敏信息，不要上传凭据或完整数据目录。
