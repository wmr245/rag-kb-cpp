# Longlite Corpus

这组语料是从官方长文档中抽取出来的轻量摘录版，用于在免费额度有限时做长文档语义回归。

- `quic_transport_excerpt.md`: 来自 RFC 9000
- `http_semantics_excerpt.md`: 来自 RFC 9110
- `tls13_excerpt.md`: 来自 RFC 8446

设计目标：

- 保留长文档中的正式定义、抽象摘要和关键术语
- 避免直接上传数十万字符全文，降低 embedding 开销
- 默认服务于 `text-embedding-v4 + 1536` 的日常回归
- 作为 `small/medium/large` 之外的补充验证，而不是替代真实大文档评测
