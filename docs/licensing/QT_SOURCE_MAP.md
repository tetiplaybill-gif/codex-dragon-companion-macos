# Qt 6.9.2 与对应源码

本版本使用 PySide6 Essentials / Shiboken6 6.9.2，Qt framework 的版本为 6.9.2。采用这些组件可适用的 LGPL v3 许可路线，并随应用提供 LGPL v3、GPL v3、适用版权及第三方声明。

| 官方源码包 | 应用使用的组件范围 |
|---|---|
| `qtbase-everywhere-src-6.9.2.tar.xz` | QtCore、QtGui、QtWidgets、QtNetwork、QtDBus，以及相关 macOS 平台、样式、TLS、网络信息和基础图像插件。 |
| `qtsvg-everywhere-src-6.9.2.tar.xz` | QtSvg、SVG 图像插件和 SVG 图标引擎。 |
| `qtimageformats-everywhere-src-6.9.2.tar.xz` | ICNS、macOS HEIF/JPEG2000、TGA、TIFF、WBMP、WebP 等附加图像插件。 |
| `pyside-setup-everywhere-src-6.9.2.tar.xz` | PySide6 Python 绑定、libpyside6、Shiboken6/libshiboken6 及其构建工具和脚本。 |

四份未修改的官方源码归档作为本版本 Release 附件提供；官方原始下载地址、附件链接和 SHA-256 见 [SOURCE_DOWNLOADS.json](SOURCE_DOWNLOADS.json)。SHA 校验对应已取得的官方档案；它不构成由源码位对位重建上游 wheel 的证明。

许可证和来源材料的应用内目录为 `app/licenses/qt/`：QtBase 215 份、QtSvg 10 份、QtImageFormats 13 份、PySide 12 份版本匹配材料。保留完整 `LICENSES`、源码第三方 attribution 及其引用正文，便于查看原始版权和条件。

例如 QtSvg 保存 XSVG 声明，QtImageFormats 保存 libtiff/libwebp 的版权与许可，PySide 保存 Shiboken 引用的 Python/PSF 材料。源码中的“可选”“系统库未找到时使用”等条件仍然适用；不能仅根据源码归档存在某库，断言 wheel 实际使用了那个内嵌版本。

本项目没有修改这些上游 Qt/PySide 源码。本项目的应用代码改动不等于对 Qt 库源码的改动。打包工具会处理 Mach-O 加载路径、架构和签名，因此最终打包文件与 wheel 原文件的整个文件哈希可能不同；判断版本来源应结合构建锁定文件、wheel 下载哈希和实际模块版本，不以签名差异推断代码被重新实现。

上游 wheel 的完整构建配方、全部可选项和补丁集合，并未由本项目重新运行和独立复现。此处提供正确版本的官方源码和相关构建脚本，不宣称完成了上游构建的位对位再现。若使用者重建库，应遵循各源码包中的构建说明并选择相同的 Python/Qt ABI；最终发行包的动态库替换和签名行为另见 [LIBRARY_REPLACEMENT.md](LIBRARY_REPLACEMENT.md)。
