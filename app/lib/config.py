from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 5433
    db_name: str = "postgres"
    db_user: str = "postgres"
    db_password: str = Field(alias="SUPABASE_DB_PASSWORD")

    openrouter_api_key: str
    model_1: str = "anthropic/claude-sonnet-4-6"
    model_2: str = "x-ai/grok-4.1-fast"
    model_3: str = "openai/gpt-4.1"
    model_judge: str = "anthropic/claude-sonnet-4-6"

    dbt_project_dir: str = "/root/Projects/data-platform/dbt"
    dbt_profiles_dir: str = "/root/.dbt"
    venv_python: str = "/root/.venv-data-platform/bin/python3"
    dbt_bin: str = "/root/.venv-data-platform/bin/dbt"



settings = Settings()


METRIC_TARGETS = {
    "sleep_total_avg_h":  {"label": "Sommeil total",     "unit": "h",        "min": 7.0,  "max": 9.0,  "higher_better": True},
    "sleep_deep_avg_h":   {"label": "Sommeil profond",   "unit": "h",        "min": 1.5,               "higher_better": True},
    "sleep_rem_avg_h":    {"label": "Sommeil REM",       "unit": "h",        "min": 1.5,               "higher_better": True},
    "hrv_avg_ms":         {"label": "HRV",               "unit": "ms",       "min": 50.0,              "higher_better": True},
    "rhr_avg":            {"label": "FC repos",          "unit": "bpm",      "max": 55.0,              "higher_better": False},
    "vo2_max_latest":     {"label": "VO2max",            "unit": "ml/kg/min","min": 52.0,              "higher_better": True},
    "workouts_count":     {"label": "Entraînements",     "unit": "/sem",     "min": 4.0,               "higher_better": True},
    "running_distance_km":{"label": "Course",            "unit": "km",       "min": 25.0,              "higher_better": True},
}
