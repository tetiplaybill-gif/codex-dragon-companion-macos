# 第三方许可与对应源码

本文件随 Codex Dragon Companion for macOS 的 `v1.0.1-mac.2-preview.1` 预览版交付。项目与角色的来源和授权说明见同目录 `PROJECT_NOTICE.md`。第三方库、字体、声音及其源码保留各自许可证；本项目没有把它们重新许可为统一的 MIT 或其他单一许可证。

## 如何查阅

在 Finder 中对应用选择“显示包内容”，打开 `Contents/Resources/app/licenses/`，可直接阅读本文件及完整许可正文。源码仓库中对应位置为 `app/licenses/`。字体和声音的原始声明也保留在 `app/fonts/` 与 `app/sounds/`。

本版本的源码材料与二进制在同一 Release 提供，源码下载不另收费：

https://github.com/tetiplaybill-gif/codex-dragon-companion-macos/releases/tag/v1.0.1-mac.2-preview.1

各文件的精确名称、SHA-256、官方来源以及源码范围见同目录 `SOURCE_DOWNLOADS.json`，和仓库的 `docs/licensing/`。发布页的附件与校验清单应一起保留，不能把不明版本的项目首页当成对应源码。

## Qt、PySide6 与 Shiboken

本预览版使用 PySide6 Essentials 6.9.2 和 Shiboken6 6.9.2，包含 Qt 6.9.2 的动态库与插件。Qt、PySide6、Shiboken 的版权归 The Qt Company Ltd. 及相应贡献者；具体版权与第三方代码声明保留在随附原文中。

此发行采用这些库可适用的 GNU LGPL v3 路线；没有声称取得 Qt 商业授权。LGPL v3 和其引用的 GPL v3 完整文本分别见：

- `qt/pyside-6.9.2/LICENSES/LGPL-3.0-only.txt`
- `qt/pyside-6.9.2/LICENSES/GPL-3.0-only.txt`

各 Qt 模块也保留其 `LICENSES/`、`qt_attribution.json`、版权和引用许可正文。源码归档同时含其他平台、可选组件、测试及文档的许可选项；保留这些原文不表示本程序使用了全部组件或采用了商业/GPL 文档等所有可选条款。实际模块与来源的对应说明见 `docs/licensing/QT_SOURCE_MAP.md`。

LGPL 库所授予的修改权利，以及为调试这些修改而进行逆向工程的权利，不受本项目的一般说明限制。该说明不扩大无关角色素材或应用代码的授权范围。应用采用外置共享库布局；兼容替换、构建和 macOS 签名的技术说明见仓库 `docs/licensing/LIBRARY_REPLACEMENT.md`。这些说明不要求关闭系统安全保护。

## Python 包与构建时嵌入部分

| 组件 | 许可材料位置 | 范围 |
|---|---|---|
| Pillow 12.0.0 | `python-packages/runtime/pillow-12.0.0/licenses/LICENSE` | 完整 MIT-CMU 及其附带图像库条款，未删成单一许可证摘要。 |
| psutil 7.0.0 | `python-packages/runtime/psutil-7.0.0/LICENSE` | BSD-3-Clause。 |
| msgspec 0.22.0 | `python-packages/runtime/msgspec-0.22.0/licenses/LICENSE` | BSD-3-Clause。 |
| packaging 26.3 | `python-packages/runtime/packaging-26.3/licenses/` | Apache-2.0 或 BSD-2-Clause，原始三个许可文件均保留。 |
| setuptools 84.2.1 与实际捆绑依赖 | `python-packages/runtime/setuptools-84.2.1/`、`python-packages/runtime_vendored/` | 主许可及各捆绑项目独立许可，不将所有嵌入代码一概标成 MIT。 |
| setuptools 内 `_validate_pyproject` | `python-packages/runtime/setuptools-nested-notices-84.2.1/config/` | 两份 NOTICE，含 fastjsonschema 的 BSD-3-Clause 和 validate-pyproject 的 MPL-2.0。 |
| PyInstaller 6.22.3 的 bootloader、loader 与 runtime hooks | `python-packages/build_tool_with_embedded_runtime/pyinstaller-6.22.3/licenses/COPYING.txt` | GPL 及 Bootloader Exception、Apache 等适用完整条款。整个构建工具本身并非都在应用内运行。 |

Python 运行时的精确版本与完整许可另列于 `PYTHON_RUNTIME_NOTICE.md`。仅构建工具的材料在源码仓库 `docs/licensing/build-tools/`；不能因组件安装在构建环境便将其全部称作应用运行依赖。

## MPL 覆盖代码的源码

本版本实际使用的 setuptools `_validate_pyproject` 源文件、明确命名的 schema 输入及完整 NOTICE，位于仓库 `third_party/setuptools-84.2.1/`，并作为 `setuptools-84.2.1-covered-sources.zip` 随上述同版本 Release 提供，不另收费。

这些文件保留原许可，未在本项目中修改。源码提供范围、版本证据和生成环境限制见该目录 README；它们不被本项目的其他许可说明限制。提供实际源文件不等于声称已验证完整生成器环境或实现位对位重建。

## 字体、声音和公告来源

Chakra Petch 与 Noto Sans SC 的 SIL OFL、版权及上游说明保存在 `resources/fonts/`；原文件也随字体分发。声音来源和 Kenney CC0 声明保存在 `resources/sounds/`；不同声音以各自原始来源说明为准。

公告界面保留可点击的 [Codex Resets](https://codex-resets.com/) 第三方来源署名和 [OpenAI 官方变更日志](https://learn.chatgpt.com/docs/changelog) 链接。前者提供重置公告汇总，后者提供官方产品更新；它们不是完整个人 X 时间线，亦不代表用户账户额度已经到账。这些来源不为本改版背书。
