# 最小证据记录

关键结论能追溯到具体材料即可。多来源或含重复数值的报告在输出目录维护 `evidence.json`；短段任务可用简短来源表，不强行建立台账。工作记录不自动插入正式正文。

## 记录格式

台账顶层使用 `schema_version: "1.0"` 及 `sources`、`claims`、`numbers` 三个数组。没有数值时 numbers 可以为空。无版本号的输入按 1.0 读取并输出兼容提示。

```json
{
  "schema_version": "1.0",
  "sources": [
    {"id": "S1", "location": "inputs/case-results.csv", "locator": "case_A 行", "verification": "opened"}
  ],
  "claims": [
    {"id": "C1", "text": "实际撰写的一个关键论断", "source_ids": ["S1"], "section": "结果分析", "status": "supported"}
  ],
  "numbers": [
    {"key": "动作时间", "condition": "case_A/方法甲/同一时间起点", "section": "结果分析", "value": 25.0, "unit": "ms", "source_ids": ["S1"]}
  ]
}
```

上例只展示记录语法，`25.0` 不是用户研究事实。实际使用时替换为真实来源与记录。

- `location` 是可找到的文件路径或网页 URL，`locator` 是物理页码、章节/式/表号、行号或数据行键。不要用文件名代替具体位置。
- `verification`：`opened` 表示本次实际打开并核对相关内容；`metadata-only` 表示只核对了书目元数据；`unread` 表示未读。该值必须如实填写。
- `claims.status`：`supported` 或 `needs-evidence`。supported 只能引用已打开核对的来源。派生结论同时指向原始输入与保存的计算记录；公式正确性和语义支持仍需人工/模型审阅。
- “计划提出缩短 20% 的目标”可被计划文件支持，记为 supported；“实际缩短 20%”需要真实结果，不因目标存在而得到支持。缺证据的断言可以 needs-evidence 和空 source_ids 留在草稿台账中，不放入成稿结论。
- `numbers` 记录摘要、正文、表格和结论中重复使用的关键量。相同 `key + condition` 表示同一物理量和口径；不同工况、方法、时间起点、误差分母应写入 condition，而不是强行统一数值。
- 比较前将单位及数值归一到一种单位。value 保存同一量的未舍入值；各处显示舍入与换算由正文复核。正负号、数量级和峰值/有效值另行检查。
- value 使用计算可提供的充分精度，不要求 JSON 精确表示循环小数。分数或高精度量在计算记录中保留输入、公式或精确分数文本，台账保存其有限浮点近似；正文按统一口径舍入。不要把显示值反复截断后用作后续计算。

## 关联实际稿件中的数值

需要机械核对关键量时，在相应 `numbers` 记录中增加 `occurrences`，绑定本次待交付稿中的位置、原句和显示值。每处出现分别记录；同一句有多个数值时选足以区分它们的原句片段。

```json
"occurrences": [
  {"locator": "line:12", "quote": "工况A的动作时间为25.0 ms。", "value_text": "25.0", "unit": "ms"},
  {"locator": "line:28", "quote": "结论：工况A的动作时间为0.0250 s。", "value_text": "0.0250", "unit": "s"}
]
```

这是要加进单个数值记录的字段示例，不是完整 JSON 文件；位置和数值均须换成真实稿件内容。`quote` 是在所指段/行中恰好出现一次的原文片段，`value_text` 是该片段中与 `unit` 相邻的单个十进制/科学记数法显示值，保留原有正负号及末位零。它记录显示精度，不能当成未舍入的真实值。正文改动后重新定位；可先用 scripts/report_io.py 的 `read_report` 函数取得 DOCX 段落定位，也可由宿主工具查看并按其 XML 段落顺序映射，不把 Word 页码当成 paragraph 编号。

数字记录可不带 occurrences，原有台账内部校验仍可运行。若运行 `check_report.py --ledger ... --final`，每个关键数值记录都需至少一个位置；未绑定记录报告错误，未列出的其他出现位置仍需模型通读检查。短段直接核对即可，不为了工具另建大型台账。详细换算与舍入边界见 [manuscript-checks.md](manuscript-checks.md)。

## 结构与扩展

缺少必填项、类型不符、不支持的版本或明确占位字段会返回带位置的输入错误。必填字段名称以示例为准，`numbers.occurrences` 为可选；每个 occurrence 必填 `locator/quote/value_text/unit`。未知字段给明确警告，不静默忽略；有意保留的额外元数据放入根或记录的 `extensions` 对象，校验器不解释其内容。标准字段中的普通中文词语不按“待补/待定”子串直接判错。

## 执行检查

在已安装本技能的目录中执行，Python 路径使用当前宿主提供的运行时：

```text
python scripts/audit_evidence.py <报告目录>/evidence.json
python scripts/audit_evidence.py <报告目录>/evidence.json --final
```

默认检查结构、来源 ID、未核对来源上的受支持论断、空的关键论断，以及重复量的数值/单位冲突。发现 needs-evidence 时输出警告，草稿可继续；`--final` 将未解决论断升级为错误。退出码 0 表示这些检查无错误（可以仍有警告），1 表示内容问题，2 表示输入格式/读取错误。

台账检查完成后，对照来源和实际稿件核对关键结论、输入数值与各处显示值。`unread` 和 `metadata-only` 来源继续作为研究线索，最终关键结论使用已打开核对的证据。

## 缺材料时

能够完成的内容继续写。对缺失结果、冲突输入、尚未执行的验证分别记录，不借助一般知识填造。计划报告可正式讨论拟采用方法与验证方案；不能为“完整”而加入已完成试验或性能提升的叙述。
