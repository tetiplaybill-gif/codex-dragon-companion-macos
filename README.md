# 白龙桌宠 · Windows / macOS 社区源码

在桌面查看 Codex 任务状态、完成提醒、本机 Token 用量和账户额度，并可按需下载白龙人物动画。

这是面向 **Windows x64 和 Apple Silicon Mac** 的第三方社区项目，与 OpenAI、Microsoft、Apple 无隶属关系。当前源码版本为 **1.0.1-community.2-preview.1**，属于预览阶段。**本仓库仅公开源码，不提供 EXE、MSI、DMG 等成品安装包。** 仓库名称保留原有 `-macos` 后缀，以维持已有链接。

[Windows 源码运行](docs/WINDOWS.md) · [Mac 构建说明](docs/BUILD.md) · [Mac 本地构建产物使用](docs/INSTALL.md) · [验证记录与限制](docs/VALIDATION.md) · [来源及许可](NOTICE.md)

## 开始使用

克隆仓库的 `main` 分支，然后按自己平台的说明准备 Python 和依赖：

```sh
git clone --branch main https://github.com/tetiplaybill-gif/codex-dragon-companion-macos.git
cd codex-dragon-companion-macos
```

Windows 使用 Python 3.12 x64 和 `requirements-windows.lock`，直接运行 `app/enhanced.py`，无需打包。Mac 使用 `requirements-macos.lock` 按构建说明运行。两份锁针对不同平台，不能混用。

启动后在“设置 → 素材（角色与素材）”选择轻量画质并点击“下载并启用”；动画从原发布源按需获取并校验。打开已登录的 Codex 桌面应用后，可用“检测连接与额度”检查连接。

“随 Codex 桌面端启动”由你自行开启并“应用”，新配置默认关闭。这会运行轻量监听器，在 Codex 桌面主进程出现时打开桌宠；另一个“登录系统时启动”是独立选项。Mac 构建脚本产生 ad-hoc 签名、未 Apple 公证的应用。

## 功能与数据

- **Codex 联动**：读取本机已有任务状态和用量，显示完成提醒；账户额度依赖本机 Codex 登录和 CLI 连接。不可用不会显示为零。
- **人物动画**：轻量素材独立下载，可调整大小、移动及动作设置。Mac 全屏让位时暂停被隐藏人物；Windows 在视频所在屏幕临时降低桌宠置顶，保留其他屏幕的显示。
- **公开公告**：免 X 登录、免付费读取 [Codex Resets](https://codex-resets.com/) 的第三方重置汇总，以及 [Codex 官方更新记录](https://learn.chatgpt.com/docs/changelog)。各来源只显示最新一条，分别标注来源、时间和状态。
- **公告提醒**：默认每 15 分钟检查，可调整间隔或静音；首次同步、重复公告、未来安排及功能更新不响铃。只有确认属于新发生重置的公告才触发提醒。

公告会受到来源覆盖范围、缓存及网络延迟影响，**不是个人 X 账号的完整推文同步，也不证明你的账户额度已经到账**。账户实际余额请看“额度”页；失败时保留的旧值会标注为缓存。

桌宠设置、素材和本机统计缓存保存在当前用户的应用数据目录；不会随源码提供。连接和公告功能不要求额外模型 API 密钥。可选聊天服务是独立功能，需要使用者另行配置。

## 系统与验证范围

| 项目 | 范围 |
|---|---|
| Windows 目标 | Windows 10 1809+ / Windows 11，x64、Python 3.12；CI 与真实桌面验收范围见 Windows 说明 |
| Mac 目标 | Apple Silicon / arm64；构建配置声明 macOS 12.0，具体要求取决于运行时和依赖 |
| 实机记录 | Mac 已在 macOS 27.0.1 做过有限本地验证；未完成 Windows 真人桌面验收 |
| 动画 | 仅卡片构建不内置动画，首次启用需要网络下载 |
| 本地构建签名 | ad-hoc，未 Apple 公证 |
| 更新 | 获取新源码后按平台说明运行或构建，保留应用数据；不运行上游成品自动更新 |

Python 运行时或依赖版本变化可能提高最低系统要求。已完成检查及未覆盖范围见[本地验证记录](docs/VALIDATION.md)，源码测试通过不代表所有机器安装成功或长期运行稳定。

## 反馈

请在 [Issues](https://github.com/tetiplaybill-gif/codex-dragon-companion-macos/issues) 提供应用版本、macOS 版本、芯片型号和复现步骤。截图请先遮住任务标题、回复内容、个人路径与账户信息；不要上传登录凭据、整个 Codex 数据目录或完整运行日志。
