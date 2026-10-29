# 发布许可与对应源码

源码开发基线：`v1.0.1-mac.2-preview.1`。本次仅公开代码。

第三方许可材料在源码仓库中保存，入口位于 [`app/licenses/LICENSES_NOTICE.md`](../../app/licenses/LICENSES_NOTICE.md)。项目和角色的授权说明以 [`NOTICE.md`](../../NOTICE.md) 为准，不以本目录替代。

- [Qt、绑定、插件与源码映射](QT_SOURCE_MAP.md)
- [共享库替换与构建说明](LIBRARY_REPLACEMENT.md)
- [对应源码下载清单](SOURCE_DOWNLOADS.json)
- [许可文本与署名文件索引](LICENSE_FILE_INDEX.json)
- [setuptools 覆盖源码与已知生成输入](../../third_party/setuptools-84.2.1/README.md)

项目代码和 setuptools 相关源文件通过[源码仓库](https://github.com/tetiplaybill-gif/codex-dragon-companion-macos)提供。清单保留已核对的 Qt 官方源码档案版本、文件名、SHA-256 和原始地址；不承诺本仓库 Release 附件或成品应用下载。

完整源码归档包含的项目范围通常大于应用实际使用范围；许可索引是保留原始声明的清单，不是“所有源文件都在二进制中启用”的 SBOM。若自行构建或另行分发二进制，应另行核对实际版本、上游 wheel 来源和构建信息。源码和声明没有被合并为单一许可证。

`build-tools/` 保留构建工具的许可资料，它们不因此变成运行时组件。PyInstaller 的 bootloader/runtime hooks 会在相应构建方式下嵌入程序，许可正文已保存在仓库。CPython 构建基线见 `app/licenses/PYTHON_RUNTIME_NOTICE.md`；不能把源码材料存在视为成品已经发布。
