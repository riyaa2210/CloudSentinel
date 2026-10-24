# Sentinel

Real-time cloud cost anomaly detector. Ingests AWS billing data, computes per-service z-scores, and flags spending anomalies before costs spiral.

## Why

Cloud bills surprise teams every month. Sentinel catches cost spikes as they happen — not when the invoice arrives. It computes statistical baselines per service and flags any cost that deviates beyond a configurable threshold.

## How It Works

```
Billing Data → Ingestion API → PostgreSQL → Z-Score Analysis → Anomalies
```

1. **Ingest** billing records (single, batch, or seed mock data)
2. **Store** in PostgreSQL with service, cost, region, timestamp, account
3. **Analyze** per-service cost distribution using z-score (mean + standard deviation)
4. **Flag** records where |z-score| exceeds threshold (default: 2.0 standard deviations)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/billing/` | Ingest a single billing record |
| `POST` | `/api/v1/billing/batch` | Ingest a batch of records |
| `POST` | `/api/v1/billing/seed?days=30` | Generate realistic mock AWS billing data |
| `GET` | `/api/v1/billing/` | List records (filter by `?service=` or `?region=`) |
| `GET` | `/api/v1/billing/summary` | Total cost per service |
| `GET` | `/api/v1/billing/{id}` | Get a single record |
| `GET` | `/api/v1/billing/anomalies` | Detect anomalies (configurable `?threshold=2.0`) |
| `GET` | `/health` | Health check |

## Anomaly Detection

Sentinel uses **z-score analysis** to detect cost anomalies:

```
z = (cost - mean) / std_dev
```

- Records are grouped by service (EC2, S3, RDS, etc.)
- Mean and standard deviation are computed per service
- Any record with |z| > threshold is flagged as anomalous
- Results are sorted by severity (highest |z-score| first)

Example: If EC2 averages $1.88/hr with std dev $0.33, a charge of $15.50/hr has a z-score of ~41 — clearly anomalous.

## Quick Start

```bash
# Clone and start
git clone https://github.com/kakarot-dev/sentinel.git
cd sentinel
docker compose up --build

# API at http://localhost:8000
# Docs at http://localhost:8000/docs

# Seed 30 days of mock data
curl -X POST "http://localhost:8000/api/v1/billing/seed?days=30"

# Detect anomalies
curl "http://localhost:8000/api/v1/billing/anomalies"

# Stricter threshold (only severe anomalies)
curl "http://localhost:8000/api/v1/billing/anomalies?threshold=5"
```

## Run Tests

```bash
cd backend && pip install -r requirements.txt && pytest tests/ -v
```

## Stack

- **Python 3.12** / **FastAPI** — async-ready API framework
- **SQLAlchemy 2.0** — ORM with mapped columns
- **PostgreSQL 16** — production database
- **Docker Compose** — single-command setup
- **GitHub Actions** — CI with lint (ruff) + tests on every push
