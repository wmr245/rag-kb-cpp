# Orion 运行手册

## 服务启动步骤

1. 检查 .env 配置。
2. 执行 docker compose up --build -d。
3. 访问 /health 确认 gateway 和 ai-service 可用。

## 故障触发条件

当接口 5xx 比例连续五分钟超过 5% 时触发故障响应。

## 初步排查

1. 先看 gateway 健康状态。
2. 再检查 ai-service 日志。
3. 最后确认 PostgreSQL 和 Redis 连接。

## 升级规则

如果十五分钟内无法恢复，就升级给值班负责人和后端负责人。
