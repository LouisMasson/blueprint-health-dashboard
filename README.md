# Blueprint Health Dashboard

> A personal health analytics platform powered by Apple Watch data, multi-model AI analysis, and a "Council of LLMs" recommendation engine.

![Streamlit](https://img.shields.io/badge/Streamlit-1.45-FF4B4B?logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![OpenRouter](https://img.shields.io/badge/OpenRouter-multi--model-6B46C1)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-self--hosted-2496ED?logo=docker&logoColor=white)

---

## What is it?

Blueprint Health is a self-hosted dashboard that ingests weekly Apple Health exports, visualizes key longevity markers, and generates AI-powered recommendations using a novel **Council of LLMs** architecture.

The project is built around one core idea: **a single AI model is not enough for health decisions**. Three independent models analyze the same data in parallel, then a judge model synthesizes them — surfacing only what at least two models agree on.

---

## The Council of LLMs

The recommendation engine is the heart of the project. Here is how it works:

```
Apple Health Data (12 weeks)
         │
         ▼
  Context Prompt Builder
  (metrics table + targets)
         │
    ┌────┴──────────────────────┐
    │      Parallel async calls │
    │                           │
  Model 1        Model 2        Model 3
claude-sonnet   grok-3         gpt-4.1
    │              │               │
    └──────────────┴───────────────┘
                   │
            Judge Model
         (claude-sonnet)
                   │
       ┌───────────▼────────────┐
       │    Merged synthesis    │
       │  convergence score     │
       │  per recommendation    │
       └────────────────────────┘
```

**Why three models?**
- Each model has different training data, biases, and reasoning patterns
- Health is a domain where false confidence is dangerous
- Convergence scoring (1, 2, or 3 models agree) lets you weigh recommendations by consensus

**What the judge does:**
- Keeps recommendations where 2+ models converge
- Includes lone-model insights only if highly relevant
- Resolves contradictions by choosing the best-supported position
- Computes the final score as a weighted average of the three individual scores

Each weekly recommendation is stored in PostgreSQL and cached — no re-generation on reload.

---

## Features

| Page | Description |
|---|---|
| Dashboard | Weekly trends: sleep (total / deep / REM), HRV, resting heart rate, VO2max, workout count, running distance, active energy |
| Recommendations | Council of LLMs → judge synthesis → score /10 + prioritized actions + convergence indicators |
| Import | Upload Apple Health JSON export via Health Auto Export (iOS app) |

---

## Architecture

```
iPhone (Apple Watch)
    │  Health Auto Export (JSON)
    ▼
Import page (Streamlit)
    │  psycopg2
    ▼
PostgreSQL (Supabase)
    ├── raw.health_metrics         ← raw weekly data points
    ├── raw.health_workouts        ← workout sessions
    └── raw.health_recommendations ← cached AI outputs
         │
         │  dbt (live views)
         ▼
    agg.health_weekly              ← 1 row per week, all KPIs
    agg.gym_weekly                 ← strength training volume
    agg.gym_prs                    ← personal records
         │
         ▼
Streamlit Dashboard
    ├── Plotly charts
    └── Council of LLMs (OpenRouter → 3 models + judge)
              │
              ▼
         Synthesized recommendations
         stored back in PostgreSQL
```

**Deployment stack:** self-hosted VPS · Docker · Traefik (reverse proxy + TLS) · Basic auth

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit 1.45 |
| Charts | Plotly |
| AI orchestration | OpenRouter (multi-model API) |
| Models | claude-sonnet-4-6, grok-3, gpt-4.1, judge: claude-sonnet-4-6 |
| Data pipeline | dbt (PostgreSQL views) |
| Database | PostgreSQL 17 (Supabase) |
| HTTP client | httpx (async parallel calls) |
| Containerization | Docker + Traefik |
| Data source | Apple Watch via Health Auto Export |

---

## Project Structure

```
health-dashboard/
├── app/
│   ├── main.py                      # Streamlit entry point
│   ├── pages/
│   │   ├── 1_Dashboard.py           # Weekly metrics visualization
│   │   ├── 2_Recommandations.py     # Council of LLMs UI
│   │   └── 3_Import.py              # Health JSON import
│   └── lib/
│       ├── ai.py                    # Council of LLMs — parallel calls + judge
│       ├── db.py                    # PostgreSQL queries + data ingestion
│       └── config.py                # Pydantic settings (env-driven)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Health Metrics Tracked

| Metric | Target | Source |
|---|---|---|
| Total sleep | 7–9h / night | Apple Watch |
| Deep sleep | > 1.5h | Apple Watch |
| REM sleep | > 1.5h | Apple Watch |
| HRV | > 50ms | Apple Watch |
| Resting heart rate | < 55 bpm | Apple Watch |
| VO2max | > 52 ml/kg/min | Apple Watch |
| Workout sessions | >= 4 / week | Apple Watch |
| Running distance | >= 15 km / week | Apple Watch |
| Gym volume | >= 8,000 kg / week | Gym Logger |

---

## Setup

### Prerequisites
- PostgreSQL database (Supabase free tier works)
- OpenRouter API key
- dbt models: `agg.health_weekly`, `agg.gym_weekly`, `agg.gym_prs`
- Docker + Docker Compose

### Environment variables

```bash
cp .env.example .env
```

Edit `.env`:
```env
SUPABASE_DB_PASSWORD=your_password
OPENROUTER_API_KEY=your_openrouter_key
DB_HOST=your_db_host
DB_PORT=5432

# Optional: override models
MODEL_1=anthropic/claude-sonnet-4-6
MODEL_2=x-ai/grok-3
MODEL_3=openai/gpt-4.1
MODEL_JUDGE=anthropic/claude-sonnet-4-6
```

### Run locally

```bash
pip install -r requirements.txt
streamlit run app/main.py
```

### Run with Docker

```bash
docker compose up -d --build
```

---

## Data Privacy

No health data is stored externally. Everything stays in your own PostgreSQL database. The only external calls are to OpenRouter (LLM API) and they contain only anonymized metric tables — no names or personally identifiable information in the prompts.

---

## Related Projects

- [Gym Logger](https://github.com/LouisMasson/gym-logger) — PWA workout tracker that feeds strength training data into this dashboard

---

## License

MIT

---

*Built by [Louis Masson](https://louismasson.me)*
