# rag-kb-cpp

## Quick Start
```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
Health Check
curl http://localhost:8000/health
curl http://localhost:8080/health
Services
postgres: pgvector/pgvector:pg16

redis: redis:7-alpine

ai-service: FastAPI

gateway: C++ Drogon
EOF


**2) 本地启动与验收（先跑通，再提交）**
```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8080/health