# 科学技术报告写作 Skill

面向中文工科技术报告的写作、修改与 Word 交付，适合研究报告、实验仿真报告、调研综述、技术方案和专题总结。当前技能版本：**1.3.1**。

本页供使用者阅读；AI 执行入口为 [SKILL.md](SKILL.md)。本技能不接管公文、科研周报或仅作语言翻译的任务。

## 能做什么

| 功能 | 实际处理内容 |
| --- | --- |
| 从材料成文 | 读取指定资料，梳理问题与证据，形成提纲、方法、结果讨论、结论和摘要；没有真实结果时只写有依据的部分 |
| 修订已有文稿 | 按指定范围修改，默认另存副本，保护图像、公式、上下标、脚注及引用字段 |
| 技术表达 | 解释公式用途、符号、单位与条件，区分实测、仿真、假设、解释和建议，核对关键论断与来源 |
| 格式调整 | 按默认配置或指定样例处理标题、正文、分项、表格、题注、参考文献及符号，并查看渲染页面 |
| 成稿检查 | 定位占位与草稿残留、引用候选、证据台账冲突，以及显式登记的正文关键数值 |
| 标点与序号审校 | 调用独立的 scientific-punctuation-check，结合上下文检查标点、标题层级及分项序号 |
| 专用模板 | 从用户指定的样例提炼格式与内容要求，保存独立配置包，供后续同类报告复用 |

AI 按任务组织写作与审校流程：脚本定位机械候选，AI 核对上下文与技术语义，页面渲染检查实际显示。

## 安装与使用条件

将本仓库 `skills/` 下的两个完整目录并列放入当前宿主识别的个人技能目录，例如 Windows 的 `%USERPROFILE%\.agents\skills\`：

```text
skills/
├─ scientific-technical-report/
│  ├─ SKILL.md
│  ├─ README.md
│  ├─ agents/
│  ├─ references/
│  ├─ scripts/
│  ├─ assets/
│  └─ licenses/
└─ scientific-punctuation-check/
   ├─ SKILL.md
   ├─ README.md
   ├─ agents/
   ├─ references/
   └─ scripts/
```

重新打开会话后，在技能列表确认两个技能可见。也可以在请求中指定 SKILL.md 路径，由 AI 读取执行。

- 只读成稿、引用、证据和标点检查使用 Python 3 标准库。
- Word 模板构建与格式审计另需 `python-docx`；应优先使用宿主已有运行环境。
- Word 成品生成和全页视觉检查需要宿主文档工具及可用渲染器，例如 Word PDF 导出或宿主捆绑的 LibreOffice。字体也需在运行环境中可用。
- 网络检索、PDF/OCR 等操作使用宿主提供的工具。

## 直接这样提要求

**新写报告：**

> 使用 $scientific-technical-report，根据我提供的材料撰写一份技术分析报告，面向课题组讨论，输出 Word。采用默认格式，缺少的数据单独列出，不编造结果。

**只调整原稿格式：**

> 使用 $scientific-technical-report，对这份原稿做整体格式规范化和标点、序号检查，不改技术数值与论证。采用默认模板，另存副本，提供调整说明和未解决问题。

**按样例建立专用模板：**

> 以附件 A 为格式和章节要求的依据，建立名为 protection-analysis 的专用配置包，再用它调整附件 B。保留样例原件，记录不能确定的参数。

**只修改指定章节：**

> 使用 $scientific-technical-report，只修改第 3 节的结果讨论，核对所引用的图表和数值，其他章节与版式保持原样。

提供材料时，说明哪个文件是原稿、哪个是事实来源、哪个才是格式样例。若有目标单位要求、修改边界、禁用网络或不运行计算等限制，一并写明即可。

## 默认格式

未指定模板时采用 `engineering-default`。它提供日常工科报告的阅读版式，目标单位的格式要求优先。

| 元素 | 默认设置 |
| --- | --- |
| 页面 | A4，四边 25 mm；无页眉、页码、独立封面、目录及图表清单 |
| 正文 | 宋体/Times New Roman，12 pt，1.5 倍行距，首行缩进 2 字符，段前后 0 |
| 文档标题 | 黑体 18 pt，居中，不另加粗 |
| 一至三级标题 | 黑体 16/14/12 pt，左对齐，不另加粗；Word 原生 `1 / 1.1 / 1.1.1` 多级编号 |
| 正文分项 | `（1）→ 1）→ ①`，同组连续，续行悬挂；序号后有说明文字时不整段加粗 |
| 表格 | 10.5 pt、单倍，默认三线表；表头加粗并跨页重复，数据行常规字重；复杂矩阵可记录例外 |
| 图题与表题 | 黑体 10.5 pt、居中、单倍；图题在下、表题在上，各自连续编号 |
| 参考文献 | 不编号的一级标题；条目 10.5 pt、单倍、悬挂 21 pt；默认 `[1]` 顺序编码 |
| 公式与符号 | 优先可编辑公式；标量变量斜体，单位与函数名正体；按实际数学、电气含义处理下标与相量 |

完整参数及例外见 [格式配置与样例适配](references/format-profiles.md)，现成模板见 [technical-report-template.docx](assets/technical-report-template.docx)。

优先级为：**本次明确要求 > 目标单位正式要求 > 指定样例或专用配置 > 默认配置**。

## 专用模板如何复用

每类专用报告使用一个数据与模板目录：

```text
report-profiles/protection-analysis/
├─ profile.json       格式覆盖，继承 engineering-default
├─ requirements.md    章节、内容、必填项与适用范围
├─ evidence.md        样例位置、观察依据、推断及未确认项
└─ template.docx      可编辑模板
```

后续请求“使用 protection-analysis 配置”并给出该目录即可。DOCX、PDF、图片及其他材料按原格式读取；扫描件需 OCR 或视觉复核。未测得的参数标为推断或继承默认。用用户指定为格式依据的样例建立模板。

## 配套工具与调用逻辑

通常由 AI 完成以下流程，无需使用者逐个运行脚本：

`读取材料与要求 → 选择配置/适配样例 → 写作或修订 → 机械检查与语义复核 → Word 渲染与全页检查 → 交付`

| 工具 | 用途 |
| --- | --- |
| `build_template.py` | 生成新模板，不覆盖已有输出，不直接调整原稿；复杂分节、章内图号及正式页眉页码需宿主文档工具处理 |
| `audit_format.py` | 核对可映射角色的字体、字号、粗体、段落及页面参数；未映射对象与表格布局等另查 |
| `audit_evidence.py` | 校验 evidence.json 的结构、来源关联和重复量冲突 |
| `check_report.py` | 查成稿残留，并核对台账显式登记位置的关键数值 |
| `check_references.py` | 查可解析的引用编号、DOI/URL 格式、ISBN 校验位及疑似重复项 |
| 独立标点技能 | 字符候选扫描、编号结构清单与上下文审校；自动编号实际显示仍需查看页面 |

需要手动运行时，在本技能目录执行以下示例，将文件名换成实际路径：

```text
python scripts/check_report.py "报告.docx" --final
python scripts/check_references.py "报告.docx"
python scripts/audit_evidence.py "evidence.json" --final
python scripts/check_report.py "报告.docx" --ledger "evidence.json" --final
python scripts/audit_format.py "报告.docx"
python scripts/build_template.py --output "新模板.docx"
```

带专用配置的格式审计或模板构建可加 `--profile "专用目录/profile.json"`。证据记录格式见 [evidence.md](references/evidence.md)，检查输出与退出码见 [manuscript-checks.md](references/manuscript-checks.md)；标点工具另见其 [README](../scientific-punctuation-check/README.md)。

## 交付与检查

正常交付包括用户要求的成品；需要时另附调整/检查说明、待补材料和可复用专用模板。内部台账不自动进入正式正文。已有文稿默认保留原件，另存修订副本。

- 对照来源核对关键数值与论断，结合上下文处理脚本候选。
- 按目标单位指定的标准版本核对著录与报告格式。
- 查看全部渲染页面，检查图片内文字、复杂公式、字段和自动编号。
- 缺少依据的内容列入待补资料，并标明稿件状态。

## 参考来源与许可

- [scientific-writing-cn](https://github.com/isabellayoungbrown52-hash/scientific-writing-cn)：研究理解、公式解释、结果讨论与修订方法。
- [K-Dense Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills)：来源—论断关联、一致性与成稿检查思路；本地脚本为简化或独立实现。
- [国家科技报告服务系统公开模板](https://www.nstrs.cn/standard/detail?arid=5652)、广东科技学院公开的科技报告编写格式要求：提供结构和格式参照，未直接套用完整汇交版式。

本技能采用 [MIT](LICENSE)。上游来源与许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，格式依据见 [format-sources.md](references/format-sources.md)，写作约定见 [local-guidance.md](references/local-guidance.md)。
