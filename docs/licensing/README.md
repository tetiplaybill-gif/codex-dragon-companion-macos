# 发布许可与对应源码

适用版本：`v1.0.1-mac.2-preview.1`。

应用包携带完整第三方许可，入口是 `Contents/Resources/app/licenses/LICENSES_NOTICE.md`；源代码中的同一文件位于 [`app/licenses/LICENSES_NOTICE.md`](../../app/licenses/LICENSES_NOTICE.md)。项目和角色的授权说明以 [`NOTICE.md`](../../NOTICE.md) 为准，不以本目录替代。

- [Qt、绑定、插件与源码映射](QT_SOURCE_MAP.md)
- [共享库替换与构建说明](LIBRARY_REPLACEMENT.md)
- [对应源码下载清单](SOURCE_DOWNLOADS.json)
- [许可文本与署名文件索引](LICENSE_FILE_INDEX.json)
- [setuptools 覆盖源码与已知生成输入](../../third_party/setuptools-84.2.1/README.md)

对应源码与应用二进制使用[同一 Release](https://github.com/tetiplaybill-gif/codex-dragon-companion-macos/releases/tag/v1.0.1-mac.2-preview.1)。清单列明每个附件的精确版本、文件名、SHA-256 和官方来源。下载源码不另收费。

完整源码归档包含的项目范围通常大于应用实际使用范围；许可索引是保留原始声明的清单，不是“所有源文件都在二进制中启用”的 SBOM。二进制版本、上游 wheel 来源和最终构建信息应与此版本的构建说明一起核对。源码和声明没有被合并为单一许可证。

`build-tools/` 保留构建工具的许可资料，它们不因此变成运行时组件。PyInstaller 的 bootloader/runtime hooks 则属于实际嵌入部分，许可正文同时随应用交付。CPython 运行时以随包 `PYTHON_RUNTIME_NOTICE.md` 为准；不能从应用版本猜测其版本或构建来源。
