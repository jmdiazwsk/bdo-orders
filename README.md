# BDO Orders Platform

Real-time e-commerce order processing system built with Python, FastAPI, Kafka, PostgreSQL, and LocalStack for AWS services simulation.

## Architecture Overview

This system processes order events in real-time through a messaging pipeline and provides REST API access to order data and metrics.

### Components

- **API Service**: FastAPI-based REST API for order queries and metrics
- **Consumer Service**: Kafka consumer for real-time order processing
- **PostgreSQL**: Primary data store for orders
- **Kafka**: Message streaming for order events
- **LocalStack**: Local AWS services simulation (S3, SNS)

### Key Features

- Real-time order processing with Kafka
- Idempotent order ingestion (prevents duplicates)
- Automated alerting for high-value orders and traffic spikes
- REST API with order lookup and time-windowed metrics
- Containerized deployment with Docker Compose
- AWS integration for alerting and error handling

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local testing)
- Git
- PowerShell or Bash terminal

## Project Structure

```
bdo-orders-platform/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # FastAPI endpoints
│   │   ├── consumers/         # Kafka consumers
│   │   ├── core/             # Settings and config
│   │   ├── db/               # Database session management
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic (alerts)
│   │   └── main.py           # FastAPI application
│   ├── Dockerfile
│   └── requirements.txt
├── infra/
│   ├── .env                  # Docker Compose environment variables
│   ├── docker-compose.yml    # Infrastructure definition
│   └── setup-localstack.ps1  # LocalStack setup script
├── tests/
│   ├── unit/                 # Unit tests
│   │   ├── test_api.py
│   │   ├── test_consumer.py
│   │   ├── test_health.py
│   │   └── test_validation_and_rate.py
│   └── integration/          # Integration tests
│       ├── test_end_to_end.py
│       └── test_full_flow.py
└── README.md                # This file
```

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd bdo-orders-platform
```

### 2. Configure Environment

The project uses environment variables defined in `infra/.env`. The default configuration should work out of the box.

### 3. Start Infrastructure

```bash
cd infra
docker-compose up -d
```

This will start:
- PostgreSQL database (port 5433)
- Kafka (port 9092)
- LocalStack (port 4566)
- API service (port 8000)
- Consumer service

### 4. Setup AWS Resources

After services are running, setup S3 bucket and SNS topic:

```bash
# From infra directory
docker-compose exec localstack awslocal s3 mb s3://bdo-orders --region eu-west-1
docker-compose exec localstack awslocal sns create-topic --name bdo-alerts --region eu-west-1
```

### 5. Verify Installation

```bash
# Check all services are healthy
docker-compose ps

# Test API health endpoint
curl http://localhost:8000/health
```

## Usage

### API Endpoints

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Get Single Order
```bash
curl http://localhost:8000/orders/o-123
```

#### Get Metrics with Time Window
```bash
# Last 5 minutes (default)
curl http://localhost:8000/metrics

# Last 1 hour
curl "http://localhost:8000/metrics?window=1h"

# Last 2 days
curl "http://localhost:8000/metrics?window=2d"
```

Expected response:
```json
{
  "count_orders": 15,
  "sum_amount": 2450.5,
  "top_countries": ["ES", "FR", "US"]
}
```

### Publishing Test Orders

#### Using Kafka Console Producer
```bash
# Access Kafka container
docker-compose exec kafka bash

# Create test order
kafka-console-producer.sh --bootstrap-server localhost:9092 --topic orders
```

Send JSON messages:
```json
{"order_id": "o-1", "user_id": "u-1", "amount": 25.0, "country": "ES", "created_at": "2025-09-28T10:00:00Z"}
{"order_id": "o-2", "user_id": "u-2", "amount": 1500.0, "country": "FR", "created_at": "2025-09-28T10:01:00Z"}
```

### Monitoring Alerts

The system generates alerts for:

1. **High-value orders**: `amount >= 1000`
2. **Traffic spikes**: `> 20 orders per minute`

Check alerts:
```bash
# View LocalStack logs for SNS
docker-compose logs localstack

# List S3 objects
docker-compose exec localstack awslocal s3 ls s3://bdo-orders --recursive
```

## Testing

### Setup Test Environment

**Important**: Run all pytest commands from the project root directory (`C:\bdo-orders-platform\`), not from the `infra/` directory.

```bash
# Navigate to project root
cd C:\bdo-orders-platform

# Install test dependencies
pip install pytest pytest-asyncio httpx pytest-cov
```

### Run Tests

#### Unit Tests (No Docker Required)

```bash
# run all tests
pytest -q
# From project root directory
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_consumer.py -v
pytest tests/unit/test_api.py -v

# With coverage
pytest tests/unit/ --cov=backend/app --cov-report=html
```

#### Integration Tests (Docker Required)

```bash
# Ensure services are running
cd infra
docker-compose up -d
cd ..

# Run integration tests
pytest tests/integration/ -v

# Or run inside container
docker-compose -f infra/docker-compose.yml exec api python -m pytest /app/../tests/unit/ -v
```

### Test Structure

#### Unit Tests (`tests/unit/`)

- **test_consumer.py**: Message parsing, persistence logic, alert conditions
- **test_api.py**: API endpoints, query parameters, error handling
- **test_health.py**: Health check endpoint
- **test_validation_and_rate.py**: Order validation and rate limiting

#### Integration Tests (`tests/integration/`)

- **test_full_flow.py**: Complete Kafka → Consumer → Database → API flow
- **test_end_to_e2e.py**: End-to-end system testing

### Common Test Commands

```bash
# All unit tests with verbose output
pytest tests/unit/ -v

# Specific test function
pytest tests/unit/test_consumer.py::test_parse_valid_message -v

# Tests with coverage report
pytest tests/unit/ --cov=backend/app --cov-report=term-missing

# Run tests inside Docker container
docker-compose -f infra/docker-compose.yml exec api pytest /app/../tests/unit/ -v
```

## Development

### Local Development Setup

```bash
# Create virtual environment (from project root)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Start only infrastructure services
cd infra
docker-compose up -d db kafka zookeeper localstack

# Run API locally (from project root)
cd ..
export DATABASE_URL="postgresql+asyncpg://orders:orders_dev_password@localhost:5433/orders_db"
export KAFKA_BROKERS="localhost:9092"
export AWS_ENDPOINT_URL="http://localhost:4566"
uvicorn backend.app.main:app --reload --port 8000
```

### Running Services Separately

The assessment requires API and consumer as separate services. Both are included in the docker-compose setup:

```bash
# View running services
docker-compose ps

# View logs for specific services
docker-compose logs api
docker-compose logs consumer

# Scale consumer if needed
docker-compose up -d --scale consumer=2
```

## Troubleshooting

### Common Issues

#### Tests not found
```bash
# WRONG: Running from infra directory
cd infra
pytest tests/unit/  # This will fail

# CORRECT: Running from project root
cd C:\bdo-orders-platform
pytest tests/unit/  # This will work
```

#### Import errors in tests
```bash
# Ensure you're in the project root and have the virtual environment activated
cd C:\bdo-orders-platform
.venv\Scripts\activate
python -m pytest tests/unit/ -v
```

#### Kafka connectivity issues
```bash
# Test Kafka from inside container
docker-compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

# Create topic manually if needed
docker-compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --create --topic orders --partitions 1 --replication-factor 1
```

#### Database connection errors
```bash
# Check database health
docker-compose exec db pg_isready -U orders -d orders_db

# Connect to database directly
docker-compose exec db psql -U orders -d orders_db
```

### Logs and Debugging

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f consumer

# Filter logs for errors
docker-compose logs api | grep ERROR
```

### Reset Environment

```bash
# Stop and remove everything
docker-compose down -v

# Restart fresh
docker-compose up -d --build
```

## Production Considerations

### Performance Optimizations

1. **Database Indexing**: 
   - Order lookup by `order_id` (implemented)
   - Time-range queries on `created_at` (implemented)
   - Country-based filtering (implemented)

2. **Kafka Consumer Tuning**:
   - Batch processing (50 records per poll)
   - Manual offset commits
   - Error handling with retry logic

3. **API Performance**:
   - Async database operations
   - Connection pooling
   - Response caching for metrics

### Scalability

1. **Horizontal Scaling**:
   - Multiple consumer instances with different consumer groups
   - API load balancing behind reverse proxy
   - Database read replicas for metrics queries

2. **Container Orchestration**:
   - Deploy to Kubernetes with proper resource limits
   - Use StatefulSets for stateful services (DB, Kafka)
   - Implement health checks and readiness probes

### Monitoring

1. **Logging**: Structured JSON logging with correlation IDs
2. **Metrics**: Prometheus metrics for order rates, API latency
3. **Alerting**: PagerDuty integration for critical failures
4. **Tracing**: Distributed tracing with Jaeger

## Architecture Decisions

### Technology Choices

1. **FastAPI**: High performance, automatic API documentation, native async support
2. **PostgreSQL**: ACID compliance, complex queries, excellent indexing
3. **Kafka**: High throughput, fault tolerance, ordered processing
4. **Pydantic**: Type safety, automatic validation, great error messages
5. **LocalStack**: AWS service mocking for local development

### Design Patterns

1. **Idempotent Processing**: Order IDs prevent duplicate processing
2. **Circuit Breaker**: Graceful handling of external service failures  
3. **Event-Driven Architecture**: Loose coupling between services
4. **Repository Pattern**: Clean separation of data access logic

# Deploy consumer
kubectl apply -n bdo-dev -f k8s/consumer-deployment.yaml
kubectl apply -n bdo-dev -f k8s/consumer-pdb.yaml


Deployment: replicas = number of Kafka partitions (scalable)

Delivery: at-least-once semantics with manual commits + DB idempotency

PDB: ensures availability during node upgrades

Metrics: Prometheus counters with ServiceMonitor

Database & Kafka

DEV: deploy with Helm charts (Bitnami/Strimzi for Kafka, Bitnami Postgres with PVC)

PROD: use managed services (AWS RDS/Aurora for Postgres, MSK/Confluent for Kafka)

# Example dev setup with Helm
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install kafka bitnami/kafka -n bdo-dev
helm install postgres bitnami/postgresql -n bdo-dev

Migrations
# Run Alembic migrations before API/consumer startup
kubectl apply -n bdo-dev -f k8s/job-migrate.yaml


Ensures schema is up to date before services start

Observability

Logs: structured with order_id, partition, offset

Metrics: Prometheus + Grafana dashboards

Key metrics:

messages_consumed_total

processing_latency_seconds

db_upserts_total

retries_total

dlq_total

kafka_consumer_lag

Deployment Flow
# 1. Namespace + configs
kubectl create ns bdo-dev
kubectl apply -n bdo-dev -f k8s/configmap.yaml
kubectl apply -n bdo-dev -f k8s/secrets.yaml

# 2. Migrations
kubectl apply -n bdo-dev -f k8s/job-migrate.yaml

# 3. API + Consumer
kubectl apply -n bdo-dev -f k8s/api-deployment.yaml
kubectl apply -n bdo-dev -f k8s/consumer-deployment.yaml

# 4. Verify
kubectl -n bdo-dev get pods,svc,ingress

# With this Kubernetes design the platform is:

Scalable: API via HPA, consumer via partitions

Fault-tolerant: PDBs, idempotent DB writes, managed DB/Kafka in prod

Observable: logs and metrics integrated with Prometheus/Grafana