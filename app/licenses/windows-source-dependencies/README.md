# Windows 源码运行依赖声明

这些材料对应 Python 3.12 x64 的源码运行依赖：默认 `requirements-windows.lock` 为 6 项，`requirements-windows-media.lock` 的 imageio-ffmpeg 仅供明确选择 WebM 导入时安装。默认环境和主 CI 不安装媒体包，WebP 轻量动画不需要 FFmpeg。包版本、官方 PyPI URL、wheel SHA-256 和下载校验结果见 `docs/windows-dependencies.json`。此目录不包含 Windows 可执行文件，也不代表已完成 Windows 安装或运行验收。

## comtypes 1.4.17

`comtypes-1.4.17/LICENSE.txt` 原样取自所锁定的官方 wheel，是 MIT 许可文本。现有 `app/licenses/comtypes-LICENSE.txt` 与它仅换行格式不同，正文内容一致。原有文件保留。

## imageio-ffmpeg 0.6.0

`imageio-ffmpeg-0.6.0/LICENSE` 是 Python 包装器的完整 BSD-2-Clause 许可。源码模式可按需使用这个包装器提供的 FFmpeg 进行 WebM 转换；它不是 PyInstaller 等打包工具。

所锁定 Windows wheel 包含 `ffmpeg-win-x86_64-v7.1.exe`。只读检查其内嵌字符串可见 `7.1-essentials_build-www.gyan.dev`、`--enable-gpl --enable-version3 --enable-static`，以及 GPL 第 3 版或任何后续版本的声明。不能把这个 FFmpeg 程序也标为 BSD-2-Clause。没有在 Mac 安装或执行该程序。

`GPL-3.0.txt` 是已保留的 GNU GPL v3 完整通用正文。它不代替 FFmpeg 对应源码、构建配方、修改记录或各静态编解码库的许可证/版权声明。wheel 自带的 binaries README 仅说明可执行文件由发布脚本放入，已原样保留为 `UPSTREAM_BINARY_README.md`。

## 精确未闭合项

所选 wheel 没有提供完整的 FFmpeg 专属许可/署名集合或对应源码。尚未将该 exe 的完整源码、补丁、构建配方与各静态依赖逐一匹配。本次只提供代码和从官方 PyPI 安装的依赖锁，没有把 FFmpeg exe、wheel 或安装包放入仓库；这些资料不构成将来另行分发 FFmpeg 二进制的许可验收结论。

文件与 wheel 来源、原文 SHA、只读二进制观察范围见 `PROVENANCE.json`。Windows 上的实际安装、导入和功能检查应由 Windows CI 另行验证。
