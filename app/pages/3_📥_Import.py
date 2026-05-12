import json
import subprocess
import sys
import os
import tempfile
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.db import ingest_health_json, get_health_weekly
from lib.config import settings

st.set_page_config(page_title="Import · Blueprint", page_icon="📥", layout="centered")
st.title("📥 Import données de santé")

st.markdown("""
Importe ton export **Health Auto Export** (JSON hebdomadaire).
Après l'import, dbt sera relancé pour recalculer les agrégats.
""")

uploaded = st.file_uploader(
    "Fichier JSON Health Auto Export",
    type=["json"],
    help="Fichier du type HealthAutoExport-YYYY-MM-DD-YYYY-MM-DD.json",
)

if uploaded:
    if uploaded.size > 50 * 1024 * 1024:
        st.error("Fichier trop volumineux (max 50 MB)")
        st.stop()
    try:
        payload = json.loads(uploaded.read())
    except json.JSONDecodeError as e:
        st.error(f"Fichier JSON invalide : {e}")
        st.stop()

    # Extract export date from filename or use today
    fname = uploaded.name
    export_date = datetime.today().strftime("%Y-%m-%d")
    parts = fname.replace("HealthAutoExport-", "").replace(".json", "").split("-")
    if len(parts) >= 3:
        try:
            export_date = "-".join(parts[3:6]) if len(parts) >= 6 else "-".join(parts[:3])
        except Exception:
            pass

    metrics = payload.get("data", {}).get("metrics", [])
    workouts = payload.get("data", {}).get("workouts", [])
    st.info(f"Fichier valide · **{len(metrics)} métriques** · **{len(workouts)} workouts** · date référence : `{export_date}`")

    if st.button("💾 Importer et relancer dbt", type="primary"):
        with st.spinner("Insertion en base…"):
            try:
                m_count, w_count = ingest_health_json(payload, export_date)
                st.success(f"✓ {m_count} métriques + {w_count} workouts insérés dans `raw`")
            except Exception as e:
                st.error(f"Erreur d'insertion : {e}")
                st.stop()

        with st.spinner("Relance de dbt (clean + agg)…"):
            # Write a patched profiles.yml using the socat proxy host
            import yaml, pathlib
            profiles_override = "/tmp/dbt-profiles-override"
            pathlib.Path(profiles_override).mkdir(exist_ok=True)
            profile = {
                "homelab": {
                    "target": "prod",
                    "outputs": {
                        "prod": {
                            "type": "postgres",
                            "host": settings.db_host,
                            "port": settings.db_port,
                            "dbname": "postgres",
                            "user": "postgres",
                            "password": settings.db_password,
                            "schema": "public",
                            "threads": 4,
                            "connect_timeout": 10,
                            "sslmode": "require",
                        }
                    },
                }
            }
            with open(f"{profiles_override}/profiles.yml", "w") as f:
                yaml.dump(profile, f)

            cmd = [
                settings.dbt_bin, "run",
                "--profiles-dir", profiles_override,
                "--select", "clean.health_daily agg.health_weekly",
                "--log-path", "/tmp/dbt-logs",
                "--target-path", "/tmp/dbt-target",
            ]
            result = subprocess.run(
                cmd,
                cwd=settings.dbt_project_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                st.success("✓ dbt run terminé")
            else:
                st.error("dbt run a échoué")
                st.code(result.stderr, language="bash")
                st.stop()

        # Clear cache
        get_health_weekly.clear()
        st.success("🎉 Import complet ! Données disponibles dans le Dashboard.")
        st.balloons()

        with st.expander("Logs dbt"):
            st.code(result.stdout, language="bash")

# — Statut actuel —
st.divider()
st.subheader("État des données")
df = get_health_weekly(4)
if not df.empty:
    latest = df.iloc[-1]
    st.metric("Dernière semaine disponible", str(latest["week_start"]))
    st.metric("Semaines dans la base", len(df))
    col1, col2, col3 = st.columns(3)
    col1.metric("Sommeil moy.", f"{latest.get('sleep_total_avg_h', 0):.1f}h")
    col2.metric("HRV moy.", f"{latest.get('hrv_avg_ms', 0):.0f}ms")
    col3.metric("Workouts", f"{latest.get('workouts_count', 0):.0f}")
else:
    st.warning("Aucune donnée en base.")
