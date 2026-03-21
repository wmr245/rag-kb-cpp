# 外部长文档数据源建议

这份清单用于给当前项目扩充更大的评测语料。优先选择公开、稳定、可解释来源，方便面试中讲“为什么选这批文档”。

## 优先级建议

### 第一优先级：马上能用，最适合当前项目

- RFC Editor 全量 RFC 文档
  - 来源：官方 RFC Editor
  - 形式：TXT / PDF / XML 批量压缩包
  - 适合：长技术文档、章节结构检索、精确 citation、英文术语匹配
  - 推荐原因：格式稳定、版权清晰、章节结构天然明显，非常适合做 chunking / 混合检索 / citation 演示
  - 链接：https://www.rfc-editor.org/retrieve/bulk

- GovInfo ERIC 教育研究报告
  - 来源：美国政府 GovInfo
  - 形式：PDF 报告集合
  - 适合：PDF 解析、长文档问答、政策类和研究类问题
  - 推荐原因：官方公开、文档长度合适、PDF 场景真实
  - 链接：https://www.govinfo.gov/help/eric

- GovInfo CZIC 海岸信息中心文档集
  - 来源：美国政府 GovInfo
  - 形式：近 5,000 份公开文档
  - 适合：多主题、多长度、异构 PDF 文档库
  - 推荐原因：规模比手写语料大很多，又不像学术全量库那么重，适合做中等规模知识库
  - 链接：https://www.govinfo.gov/help/czic

### 第二优先级：更大、更适合做研究型 RAG

- UnarXive 2024
  - 来源：Hugging Face 数据集卡
  - 形式：2.28M 篇结构化 arXiv 全文 JSONL
  - 适合：超大规模学术 RAG、结构化章节检索、metadata-heavy 检索
  - 推荐原因：有标题、章节、引用等丰富结构，但体量很大，建议先抽样使用
  - 链接：https://huggingface.co/datasets/ines-besrour/unarxive_2024

- SEC EDGAR 批量数据
  - 来源：SEC 官方 API / bulk ZIP
  - 形式：公司提交历史、XBRL、财报相关结构化数据
  - 适合：金融文档 RAG、长年报/10-K 检索、表格与 metadata 检索
  - 推荐原因：官方、长期更新、真实业务价值高，但清洗成本比 RFC 更高
  - 链接：https://www.sec.gov/edgar/sec-api-documentation

## 如果你要 benchmark，而不只是扩库

- MultiHop-RAG
  - 来源：Hugging Face
  - 特点：2556 个跨 2 到 4 篇文档的 query，带证据关系
  - 适合：跨文档推理、多跳召回、metadata-aware 检索验证
  - 链接：https://huggingface.co/datasets/yixuantt/MultiHopRAG

- Open RAG Benchmark（arXiv 子集）
  - 来源：GitHub 仓库
  - 特点：1000 篇 PDF、3045 个 QA、包含 gold doc/section 信息
  - 适合：端到端 retrieval + generation benchmark
  - 链接：https://github.com/vectara/open-rag-bench

- CLAP NQ
  - 来源：Hugging Face
  - 特点：long-form QA，带 grounded passages
  - 适合：长答案生成和 grounding 评测
  - 链接：https://huggingface.co/datasets/PrimeQA/clapnq

## 对当前项目最稳的扩容顺序

1. 先用 RFC + GovInfo PDF 做第一批“大文档扩容”
2. 把 `medium / large` suite 扩成一个新的 `xlarge` 抽样套件
3. 先控制在 20 到 50 份文档，保证每次回归还能在几分钟内跑完
4. 等回归稳定后，再考虑接入 UnarXive 或 SEC EDGAR 的抽样子集

## 实操建议

- 第一阶段不要一上来就抓几万份文档，先做“抽样但更真实”的语料层
- 每类外部数据先选 5 到 10 份代表性文档
- 保留来源说明、下载时间和筛选标准，方便以后复现
- 对超大语料优先做离线抽样，而不是直接塞进当前本地 Docker 环境
