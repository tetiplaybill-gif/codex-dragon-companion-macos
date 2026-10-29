# setuptools 84.2.1 中的相关覆盖源码

这里保存本版本使用的 6 个 `_validate_pyproject` Python 源文件、同目录 NOTICE、生成命令明确命名的两个 schema 输入、相邻 `config/NOTICE`，以及 setuptools 主许可证。文件未被本项目改写，均与 setuptools 84.2.1 安装包的 RECORD 哈希相符。

具体文件、SHA-256 和范围见 `SOURCE_PROVENANCE.json`。这些可编辑源文件已随 Git 保存在当前目录，通过[源码仓库](https://github.com/tetiplaybill-gif/codex-dragon-companion-macos)交付，不依赖 Release 附件或成品下载。源码许可保持其原有条款。

## 许可与源码范围

`setuptools/config/_validate_pyproject/NOTICE` 包含 fastjsonschema 的 BSD-3-Clause 和 validate-pyproject 的 MPL-2.0 全文，并说明相关生成代码和项目来源。`setuptools/config/NOTICE` 标明两个 schema 的 MPL 来源。不要把这些代码因为被 setuptools 捆绑而一概当作 MIT。

保存的 Python 模块是 `__init__.py`、`error_reporting.py`、`extra_validations.py`、`fastjsonschema_exceptions.py`、`fastjsonschema_validations.py`、`formats.py`。上游 NOTICE 中写作 `format.py`，实际分发文件名为 `formats.py`；此处保留原声明，不自行改写其内容。

## 生成资料的可确认范围

上游 NOTICE 记录的 `validate_pyproject.pre_compile` 命令保留在原文件中；它显式引用的 `distutils.schema.json` 与 `setuptools.schema.json` 已一并提供，都是可编辑的原始 JSON 文件。

生成验证器包含 `VERSION = "2.21.2"` 标记。这个标记不能独立证明所有嵌入片段的上游版本；validate-pyproject 的精确版本/提交号和完整生成器、插件环境未从安装包中得到确认。本项目没有运行该生成命令，也不声称验证了位对位再生成，或已独立确认生成器的全部首选修改形式。

这些源码与输入可直接从仓库当前目录取得。若修改受 MPL 覆盖的文件并再分发，应遵循保留的 MPL 条款。该说明不对无关桌宠代码、角色或动画增加授权。
