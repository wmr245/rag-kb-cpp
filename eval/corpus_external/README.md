# 外部长文档样本

这批样本用于 `xlarge` 套件，目标不是一次性覆盖所有外部数据，而是先抽样一批来源稳定、长度明显高于手写语料的官方文档。

## 当前样本

- `rfc9000.txt`
  - 来源：https://www.rfc-editor.org/rfc/rfc9000.txt
- `rfc9110.txt`
  - 来源：https://www.rfc-editor.org/rfc/rfc9110.txt
- `rfc8446.txt`
  - 来源：https://www.rfc-editor.org/rfc/rfc8446.txt
- `rfc9293.txt`
  - 来源：https://www.rfc-editor.org/rfc/rfc9293.txt
- `eric_ed483001.pdf`
  - 来源：https://www.govinfo.gov/app/details/ERIC-ED483001
  - 下载：https://www.govinfo.gov/content/pkg/ERIC-ED483001/pdf/ERIC-ED483001.pdf

## 选择理由

- RFC 文档结构稳定、章节清晰，适合测试长文档结构化召回。
- ERIC PDF 代表真实报告型 PDF，适合测试 PDF 解析和引用。
- 这批文档都来自官方公开来源，便于复现和说明来源。

## 使用建议

- 当前仓库默认 Embedding 已切到 `text-embedding-v4 + 1536`。
- `xlarge` 会显著消耗 embedding 免费额度，不建议作为日常回归。
- 日常优先使用 `longlite`，只有在阶段性验收时再跑 `xlarge`。
