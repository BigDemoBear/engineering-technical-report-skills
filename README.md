# 工科科技报告写作与审校 · AI Skills

Engineering Technical Report Skills：让 AI 按证据组织工科科技报告，解释方法与公式，讨论真实结果，并完成 Word 格式和中文标点审校。

适用于技术分析、实验仿真、专题研究、调研综述和技术方案，按报告目的组织方法、结果、讨论与结论。

## 包含的技能

| 技能 | 用途 |
| --- | --- |
| [scientific-technical-report](skills/scientific-technical-report/README.md) | 工科科技报告的写作、定点修改、证据核对、公式解释和 Word 交付 |
| [scientific-punctuation-check](skills/scientific-punctuation-check/README.md) | 中文标点、标题层级与分项序号检查，可独立使用，也可由主技能调用 |

报告技能和标点技能作为两个同级目录一起安装。

## 安装

将 `skills/` 下的 `scientific-technical-report` 与 `scientific-punctuation-check` 两个完整目录安装到当前 AI 宿主的技能目录，例如 Windows 的 `%USERPROFILE%\.agents\skills\`。

重新打开会话并确认两个技能可见。实际执行还需要宿主能访问材料，提供相应文件、研究与渲染工具。

## 交给 AI 的示例

> 使用 $scientific-technical-report，根据我提供的资料写一份工科技术分析报告，输出 Word。采用默认科技报告格式，核对关键数值、公式与来源；缺少真实结果的部分列为待补，不编造。

> 使用 $scientific-technical-report，只规范这份报告的格式并检查标点和编号，保留技术数值与论证，另存副本。

默认采用 A4、正文 12 pt、1.5 倍行距与分级标题；无独立封面、目录或页眉页码。目标单位或项目模板优先。具体规则见 [报告技能说明](skills/scientific-technical-report/README.md)。

## 运行环境

- 建议 Python 3.10 或更新版本；成稿、证据、引用和标点候选检查只用标准库。
- 模板构建和格式审计需要 `python-docx`，可用 `python -m pip install -r requirements.txt` 安装。
- Word 成品及全页视觉检查依赖宿主文档工具和可用渲染器，例如 Word PDF 导出或 LibreOffice；默认字体为宋体、黑体和 Times New Roman，须在运行环境中合法可用。
- 网络检索、PDF/OCR 和学术来源访问使用宿主提供的工具。
- 脚本定位候选，AI 核对技术语义和来源，页面渲染检查实际排版。

## 许可与来源

本项目采用 [MIT](LICENSE)，第三方来源与许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

检索关键词：engineering technical report, AI skill, Codex skills, Chinese technical writing, DOCX, scientific punctuation；工科科技报告、工程技术报告、中文科技写作、标点审校。
