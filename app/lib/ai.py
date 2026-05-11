import asyncio
import concurrent.futures
import json
import re
from typing import Optional

from json_repair import repair_json

import httpx
import pandas as pd

from .config import settings, METRIC_TARGETS

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are a personal health coach focused on longevity and physical performance.
You analyze Apple Watch / Apple Health data for an active user and provide actionable, specific, data-driven recommendations.
Your style is direct, concise, and evidence-based. You are not a doctor — your advice covers lifestyle and training only.
Respond ONLY in valid JSON, no markdown, no text before or after."""

RECO_SCHEMA = """{
  "summary": "1 phrase synthèse de la semaine",
  "score": 7,
  "wins": [{"metric": "nom_métrique", "observation": "ce qui va bien"}],
  "warnings": [{"metric": "nom_métrique", "observation": "tendance préoccupante", "hypothesis": "cause probable"}],
  "recommendations": [
    {"priority": 1, "category": "sommeil|récupération|activité|nutrition", "action": "action concrète", "rationale": "pourquoi", "target": "valeur cible"}
  ],
  "focus_next_week": "1 marqueur clé à surveiller"
}"""

JUDGE_PROMPT = """Tu es un arbitre expert en santé et performance. Tu reçois 3 analyses indépendantes des mêmes données de santé.
Ton rôle : fusionner ces analyses en une synthèse optimale.
Règles :
- Garder les recommandations où ≥ 2 modèles convergent (ajoute "convergence": 2 ou 3)
- Si 1 seul modèle mentionne une reco, l'inclure seulement si elle est très pertinente (ajoute "convergence": 1)
- Éliminer les contradictions — choisir la position la plus étayée
- Le score final = moyenne pondérée des 3 scores
- Répondre UNIQUEMENT en JSON valide avec le même schéma + champ "convergence" sur chaque reco"""


def _build_context_prompt(df: pd.DataFrame, df_gym: pd.DataFrame | None = None) -> str:
    cols = [
        "week_start", "sleep_total_avg_h", "sleep_deep_avg_h", "sleep_rem_avg_h",
        "hrv_avg_ms", "rhr_avg", "vo2_max_latest", "workouts_count", "runs_count",
        "running_distance_km", "active_energy_total_kj", "respiratory_rate_avg",
    ]
    available = [c for c in cols if c in df.columns]
    subset = df[available].tail(12).copy()
    subset["week_start"] = subset["week_start"].astype(str)
    table = subset.to_markdown(index=False, floatfmt=".1f")

    gym_section = ""
    if df_gym is not None and not df_gym.empty:
        gym_cols = ["week_start", "sessions_count", "volume_kg_total", "sets_total", "rpe_avg"]
        gym_available = [c for c in gym_cols if c in df_gym.columns]
        gym_subset = df_gym[gym_available].tail(12).copy()
        gym_subset["week_start"] = gym_subset["week_start"].astype(str)
        gym_table = gym_subset.to_markdown(index=False, floatfmt=".0f")
        gym_section = f"""

Données musculation hebdomadaires (Gym Logger) :
{gym_table}
"""

    targets = "\n".join(
        f"- {v['label']} ({v['unit']}): "
        + (f"cible {v.get('min', '')}–{v.get('max', v.get('min', ''))}" if v.get("higher_better") else f"cible < {v.get('max', '')}")
        for v in METRIC_TARGETS.values()
    )

    return f"""Voici les données de santé hebdomadaires de Louis (12 dernières semaines) :

{table}
{gym_section}
Références optimales :
{targets}

Analyse les tendances, identifie les points forts et les points de vigilance.
Fournis 3 à 5 recommandations actionnables pour la semaine à venir.

Format de réponse attendu :
{RECO_SCHEMA}"""


async def _call_model(client: httpx.AsyncClient, model_id: str, user_prompt: str) -> dict:
    resp = await client.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "https://health.patronusguardian.org",
            "X-Title": "Blueprint Health Dashboard",
        },
        json={
            "model": model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
        },
        timeout=60.0,
    )
    if not resp.is_success:
        raise ValueError(f"HTTP {resp.status_code} from {model_id}: {resp.text[:200]}")
    raw_text = resp.json()["choices"][0]["message"]["content"]
    # Strip markdown fences if present
    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.MULTILINE)
    raw_text = re.sub(r"\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
    # Extract outermost JSON object
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON in output from {model_id}: {raw_text[:200]}")
    json_str = match.group()
    # Try strict parse first, then use json-repair as fallback
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        try:
            repaired = repair_json(json_str, return_objects=True)
            if isinstance(repaired, dict):
                return repaired
            raise ValueError(f"repair_json returned non-dict: {type(repaired)}")
        except Exception as e:
            raise ValueError(f"JSON parse error from {model_id}: {e} — snippet: {json_str[:300]}")


async def _run_parallel(user_prompt: str) -> tuple[dict, dict, dict]:
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _call_model(client, settings.model_1, user_prompt),
            _call_model(client, settings.model_2, user_prompt),
            _call_model(client, settings.model_3, user_prompt),
            return_exceptions=True,
        )
    outputs = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            outputs.append({"error": str(r), "score": None, "recommendations": []})
        else:
            outputs.append(r)
    return outputs[0], outputs[1], outputs[2]


async def _judge(client: httpx.AsyncClient, r1: dict, r2: dict, r3: dict) -> dict:
    judge_user = f"""Analyse 1 ({settings.model_1}):
{json.dumps(r1, ensure_ascii=False, indent=2)}

Analyse 2 ({settings.model_2}):
{json.dumps(r2, ensure_ascii=False, indent=2)}

Analyse 3 ({settings.model_3}):
{json.dumps(r3, ensure_ascii=False, indent=2)}

Produis la synthèse finale fusionnée."""
    return await _call_model(client, settings.model_judge, judge_user)


def generate_recommendations(df: pd.DataFrame, df_gym: pd.DataFrame | None = None) -> tuple[dict, dict, dict, dict]:
    """Returns (model1_out, model2_out, model3_out, final_merged).

    Uses a thread pool to avoid RuntimeError when called from Streamlit's
    already-running event loop.
    """
    user_prompt = _build_context_prompt(df, df_gym)

    async def _all():
        r1, r2, r3 = await _run_parallel(user_prompt)
        async with httpx.AsyncClient() as client:
            final = await _judge(client, r1, r2, r3)
        return r1, r2, r3, final

    def _run_in_new_loop():
        return asyncio.run(_all())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_in_new_loop).result()
