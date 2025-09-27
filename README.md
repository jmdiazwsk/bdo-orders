# BDO Orders Platform (Backend Python / FastAPI)

This repository implements the technical assessment:
- Kafka consumer (orders)
- PostgreSQL persistence (idempotent, dedup by `order_id`)
- REST API (FastAPI): `/orders/{order_id}`, `/metrics?window=5m`, `/health`
- Alerts via AWS (SNS/S3) using LocalStack
- Tests with pytest (unit + one integration)
- Containers and docker-compose (Kafka, Postgres, LocalStack, API, Consumer)
- Optional k8s manifests and CI notes

## Quickstart (dev)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
