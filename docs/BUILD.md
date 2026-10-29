# 从源码构建 macOS 预览版

以下面向 Apple Silicon Mac。构建产物为 ad-hoc 签名的 `.app`，可选生成 DMG；此流程不进行 Apple 公证。构建前请阅读 [NOTICE](../NOTICE.md) 及随附组件许可。本仓库仅公开源码；构建脚本生成本地目录，不负责安装到“应用程序”或公开成品。

## 固定构建输入

源码仓库为 [tetiplaybill-gif/codex-dragon-companion-macos](https://github.com/tetiplaybill-gif/codex-dragon-companion-macos)，请从 `main` 获取源码；当前源码版本为 `1.0.1-community.2-preview.1`。本文只介绍 Mac，Windows 请看 [Windows 源码运行](WINDOWS.md)。

本地验证构建采用 [Astral python-build-standalone 20261026](https://github.com/astral-sh/python-build-standalone/releases/tag/20261026) 提供的 **CPython 3.12.16 / aarch64-apple-darwin**：

| 输入 | 固定来源与校验值 |
|---|---|
| Python 运行时 | [install_only.tar.gz](https://github.com/astral-sh/python-build-standalone/releases/download/20261026/cpython-3.12.16%2B20261026-aarch64-apple-darwin-install_only.tar.gz) |
| 运行时 SHA-256 | `fbf4afef53c2a6b72bb741bc06d5671a9dfaf87bd84e5aa73ac9b3d0d589f14e` |
| 上游构建提交 | `fa506e0858ac9f2cc5b289c137b888a2aa24d1ee` |
| macOS 依赖锁 SHA-256 | `93cee4db0dc629ea192ae742fee967873d11320e162fd7006667bfef05ce55ae` |

源码根目录已包含 `requirements-macos.lock`，无需从 Release 下载。该锁固定 11 个构建依赖及 wheel 哈希，采用 PySide6 Essentials、Shiboken 6.9.2；不要用完整 PySide6 元包、系统 Python 或其他平台的依赖清单替代后仍声称复现了这份本地验证构建。`requirements-enhanced.txt` 保留上游依赖信息，不是本 macOS 构建锁。

运行时和依赖的来源及哈希已核对。能安装依赖或通过 `pip check`，不代表已经完成干净机器安装、最低 macOS 版本、动画及启动联动验收；已完成项目及限制见[本地验证记录](VALIDATION.md)。

## 准备环境

需要 Git，以及可用的 macOS 构建工具 `iconutil`、`codesign`；生成 DMG 还需要 `hdiutil`。如系统提示缺少开发工具，请通过 Apple 正常安装流程准备。

```sh
git clone --branch main https://github.com/tetiplaybill-gif/codex-dragon-companion-macos.git
cd codex-dragon-companion-macos
```

下载上述 Python 归档，核对 SHA-256 后解压到源码目录内的 `.build-python/`，使解释器位于 `.build-python/python/bin/python3.12`。确认仓库内依赖锁的 SHA-256 与上表一致后：

```sh
.build-python/python/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: --require-hashes -r requirements-macos.lock
.venv/bin/python -m pip check
```

若已有与锁文件匹配的 `wheelhouse/`，可以离线安装：

```sh
.venv/bin/python -m pip install --no-index --find-links wheelhouse --require-hashes -r requirements-macos.lock
.venv/bin/python -m pip check
```

不要忽略哈希错误或临时放宽版本来“完成”复现构建。若依赖锁缺失、平台不匹配或指定文件已不可取得，停止复现流程并反馈；自行换依赖属于另一份开发构建。

## 构建本地仅卡片应用

```sh
.venv/bin/python build_macos.py --cards-only
```

输出位于新建的 `release/macos-<版本>-<时间>/`，包含本地应用。需要自用磁盘映像时可另加 `--dmg`，生成 DMG 及 SHA-256 文件；这些均为本地产物，不是本仓库提供的成品下载。`build/` 保存构建中间产物。仅卡片构建不需要下载动画，用户安装后在“设置 → 素材”按需获取；不要把个人下载缓存打进应用。

该命令会给生成的应用添加 ad-hoc 签名并验证签名结构，不会使它获得 Apple 公证，也不会改变系统安全设置。自行构建产物的最低系统要求必须同时满足所用 Python、Qt 与其他动态库，不能只依据 `Info.plist` 的声明判断兼容性。

## 隔离测试与验收

测试时使用临时数据目录，避免把自己的任务、登录状态或桌宠设置当作 fixture：

```sh
BAILONG_CHECK_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/bailong-check.XXXXXX")"
mkdir -p "$BAILONG_CHECK_ROOT/state" "$BAILONG_CHECK_ROOT/codex"
LOCALAPPDATA="$BAILONG_CHECK_ROOT/state" \
CODEX_HOME="$BAILONG_CHECK_ROOT/codex" \
PYTHONPATH=app QT_QPA_PLATFORM=offscreen \
.venv/bin/python -m unittest \
  test_public_announcements test_public_announcements_panel \
  test_mac_concealed_playback test_full_screen_geometry
```

这组测试覆盖公告逻辑、界面和部分人物隐藏行为。离屏测试不能证明真实桌面的所有行为；依赖人物素材的测试还需要相应资源。本地使用前应另外核对构建产物的版本、arm64 架构、签名、许可通知和哈希，并实际检查首次启动、人物下载、Codex 连接、启动联动开启与关闭、退出及保留数据的更新。不要为完成验收关闭 Gatekeeper 或清除 quarantine。

源码仓库只保存程序与明确纳入的静态资源；构建产物、运行时、素材下载包、用户配置、任务日志和验证截图不应提交到 Git。`requirements-macos.lock` 应保留，任何依赖或运行时更新都需重新记录来源、哈希和验证范围。
