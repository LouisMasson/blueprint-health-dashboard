import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

from .config import settings


def _get_conn():
    return psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        connect_timeout=10,
    )


@st.cache_data(ttl=300)
def get_health_weekly(weeks: int = 12) -> pd.DataFrame:
    query = """
        SELECT *
        FROM agg.health_weekly
        WHERE week_start IS NOT NULL
        ORDER BY week_start DESC
        LIMIT %s
    """
    with _get_conn() as conn:
        df = pd.read_sql(query, conn, params=(weeks,))
    return df.sort_values("week_start")


def get_latest_week() -> Optional[dict]:
    df = get_health_weekly(1)
    if df.empty:
        return None
    return df.iloc[-1].to_dict()


def ensure_recommendations_table():
    with _get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw.health_recommendations (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                week_start   DATE NOT NULL UNIQUE,
                model_1_id   TEXT,
                model_1_raw  JSONB,
                model_2_id   TEXT,
                model_2_raw  JSONB,
                model_3_id   TEXT,
                model_3_raw  JSONB,
                judge_id     TEXT,
                final        JSONB,
                context_hash TEXT
            )
        """)


@st.cache_data(ttl=60)
def get_recommendations(limit: int = 4) -> list[dict]:
    try:
        with _get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, created_at, week_start, model_1_id, model_2_id, model_3_id, judge_id, final
                FROM raw.health_recommendations
                ORDER BY week_start DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def save_recommendation(
    week_start: date,
    model_1_id: str, model_1_raw: dict,
    model_2_id: str, model_2_raw: dict,
    model_3_id: str, model_3_raw: dict,
    judge_id: str, final: dict,
    context_hash: str,
):
    ensure_recommendations_table()
    with _get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO raw.health_recommendations
                (week_start, model_1_id, model_1_raw, model_2_id, model_2_raw,
                 model_3_id, model_3_raw, judge_id, final, context_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (week_start) DO UPDATE SET
                model_1_id   = EXCLUDED.model_1_id,
                model_1_raw  = EXCLUDED.model_1_raw,
                model_2_id   = EXCLUDED.model_2_id,
                model_2_raw  = EXCLUDED.model_2_raw,
                model_3_id   = EXCLUDED.model_3_id,
                model_3_raw  = EXCLUDED.model_3_raw,
                judge_id     = EXCLUDED.judge_id,
                final        = EXCLUDED.final,
                context_hash = EXCLUDED.context_hash,
                created_at   = now()
        """, (
            week_start,
            model_1_id, psycopg2.extras.Json(model_1_raw),
            model_2_id, psycopg2.extras.Json(model_2_raw),
            model_3_id, psycopg2.extras.Json(model_3_raw),
            judge_id, psycopg2.extras.Json(final),
            context_hash,
        ))


def ingest_health_json(payload: dict, export_date: str) -> tuple[int, int]:
    """Insert raw health metrics and workouts from a parsed JSON export."""
    KEY_METRICS = {
        "sleep_analysis", "active_energy", "basal_energy_burned",
        "step_count", "walking_running_distance", "heart_rate",
        "heart_rate_variability", "respiratory_rate", "resting_heart_rate",
        "vo2_max", "body_weight", "body_fat_percentage",
    }

    metrics = payload.get("data", {}).get("metrics", [])
    workouts = payload.get("data", {}).get("workouts", [])

    with _get_conn() as conn, conn.cursor() as cur:
        m_count = 0
        for m in metrics:
            name = m.get("name", "")
            if name not in KEY_METRICS:
                continue
            cur.execute("""
                INSERT INTO raw.health_metrics
                    (export_date, metric_name, unit, data_points, source)
                VALUES (%s, %s, %s, %s, 'apple_health')
                ON CONFLICT (export_date, metric_name) DO UPDATE SET
                    data_points = EXCLUDED.data_points,
                    ingested_at = now()
            """, (
                export_date,
                name,
                m.get("units"),
                psycopg2.extras.Json(m.get("data", [])),
            ))
            m_count += 1

        w_count = 0
        for w in workouts:
            energy = w.get("activeEnergyBurned")
            energy_kcal = energy.get("qty") if isinstance(energy, dict) else None
            dist = w.get("distance")
            distance_km = dist.get("qty") if isinstance(dist, dict) else None
            start = w.get("start")
            if not start:
                continue
            cur.execute("""
                INSERT INTO raw.health_workouts
                    (export_date, workout_type, start_time, end_time,
                     duration_min, energy_kcal, distance_km, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (start_time, workout_type) DO NOTHING
            """, (
                export_date,
                w.get("name"),
                start,
                w.get("end"),
                w.get("duration"),
                energy_kcal,
                distance_km,
                psycopg2.extras.Json(w),
            ))
            w_count += 1

    return m_count, w_count


def context_hash(df: pd.DataFrame) -> str:
    key = df[["week_start"]].tail(12).to_json()
    return hashlib.sha256(key.encode()).hexdigest()[:16]
