# Orion API 参考

## 上传接口

POST /docs/upload 用于上传文件，参数包括 file、title、owner。

## 查询接口

POST /rag/query 的 body 包含 question、topK、docScope。
topK 建议不超过 10。
docScope 用于限制只在指定文档集合内检索。

## 健康检查

GET /health 用于检查服务是否可用。

## 缓存行为

命中缓存时，响应头 x-cache 会返回 hit。
