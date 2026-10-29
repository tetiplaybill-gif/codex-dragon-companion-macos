# Python 运行时来源与许可

本源码的构建运行时基线为 **CPython 3.12.16**，来自 Astral 的 **python-build-standalone 20261026** 官方发布，目标为 `aarch64-apple-darwin`，构建选项为 `pgo+lto`。

Python 版权归 Python Software Foundation 及完整许可证中列出的历史权利人。完整 Python 许可见 `python-runtime/3.12.16/licenses/LICENSE.cpython.txt`。官方完整运行时归档携带的其他依赖许可也原样保存在该 `licenses/` 目录，不能把运行时内的所有组件重新标为同一种许可。

官方 install_only/full 档案的下载地址和 SHA-256、构建来源提交、原始 `PYTHON.json` 的 SHA，以及本目录的许可文件清单见 `python-runtime/3.12.16/PROVENANCE.json`。公开元数据摘要只包含版本、架构、构建选项等字段；没有发布构建机器的用户路径。

这些材料来自同一官方完整归档。完整运行时还包含应用可能没有打包的组件，因此保留其完整许可集合不等于断言每个组件都进入应用。若自行构建或另行分发应用，实际包含内容须另行验证；本说明不宣称做过 CPython 或其所有依赖的源码位对位重建。
