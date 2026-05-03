import streamlit as st
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.db import get_health_weekly, get_recommendations, save_recommendation, context_hash, ensure_recommendations_table
from lib.ai import generate_recommendations
from lib.config import settings

st.set_page_config(page_title="Recommandations · Blueprint", page_icon="🤖", layout="wide")
st.title("🤖 Recommandations IA")

ensure_recommendations_table()

df = get_health_weekly(12)
if df.empty:
    st.warning("Aucune donnée. Importe un fichier d'abord.")
    st.stop()

latest_week = str(df.iloc[-1]["week_start"])
ctx_hash = context_hash(df)

# — Historique —
past = get_recommendations(4)
latest_reco = past[0] if past else None
already_generated = latest_reco and str(latest_reco["week_start"]) == latest_week

st.subheader(f"Semaine du {latest_week}")

if already_generated and latest_reco.get("final"):
    st.success("Recommandations générées · " + str(latest_reco["created_at"])[:16])
    _show = latest_reco["final"]
else:
    _show = None

# — Génération —
col_btn, col_info = st.columns([2, 5])
with col_btn:
    gen_btn = st.button("⚡ Générer les recommandations", type="primary", use_container_width=True)
with col_info:
    st.caption(f"3 modèles en parallèle → judge · {settings.model_1.split('/')[-1]} · {settings.model_2.split('/')[-1]} · {settings.model_3.split('/')[-1]}")

if gen_btn:
    with st.spinner("Appel des 3 modèles en parallèle…"):
        try:
            r1, r2, r3, final = generate_recommendations(df)
        except Exception as e:
            st.error(f"Erreur lors de la génération : {e}")
            st.stop()

    # Save to DB
    save_recommendation(
        week_start=df.iloc[-1]["week_start"],
        model_1_id=settings.model_1, model_1_raw=r1,
        model_2_id=settings.model_2, model_2_raw=r2,
        model_3_id=settings.model_3, model_3_raw=r3,
        judge_id=settings.model_judge, final=final,
        context_hash=ctx_hash,
    )
    get_recommendations.clear()
    _show = final
    st.success("Synthèse générée et sauvegardée ✓")

    with st.expander("Détails par modèle"):
        tabs = st.tabs([settings.model_1.split("/")[-1], settings.model_2.split("/")[-1], settings.model_3.split("/")[-1]])
        for tab, raw in zip(tabs, [r1, r2, r3]):
            with tab:
                if "error" in raw:
                    st.error(raw["error"])
                else:
                    _score = raw.get("score", "?")
                    st.metric("Score", f"{_score}/10")
                    st.json(raw, expanded=False)

# — Affichage de la synthèse —
def show_reco(data: dict):
    if not data:
        return

    col_score, col_summary = st.columns([1, 5])
    score_raw = data.get("score", "?")
    score_rationale = None
    # Handle score as dict {"value": N, "rationale": "..."}, plain number, or string
    if isinstance(score_raw, dict):
        score_rationale = score_raw.get("rationale")
        score = score_raw.get("value", "?")
    else:
        score = score_raw
    try:
        score_num = float(score)
    except (TypeError, ValueError):
        score_num = None
    with col_score:
        color = "green" if score_num and score_num >= 7 else ("orange" if score_num and score_num >= 5 else "red")
        st.markdown(f"<div style='font-size:3rem;font-weight:700;color:{color}'>{score}<span style='font-size:1rem;color:#94a3b8'>/10</span></div>", unsafe_allow_html=True)
        if score_rationale:
            st.caption(score_rationale)
    with col_summary:
        st.markdown(f"**{data.get('summary', '')}**")
        focus = data.get("focus_next_week")
        if focus:
            st.info(f"🎯 Focus semaine prochaine : {focus}")

    wins = data.get("wins", [])
    warnings = data.get("warnings", [])
    recos = data.get("recommendations", [])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### ✅ Points forts")
        for w in wins:
            st.markdown(f"- **{w.get('metric', '')}** — {w.get('observation', '')}")

    with c2:
        st.markdown("### ⚠️ Points de vigilance")
        for w in warnings:
            hypo = f" *(hypothèse : {w.get('hypothesis')})*" if w.get("hypothesis") else ""
            st.markdown(f"- **{w.get('metric', '')}** — {w.get('observation', '')}{hypo}")

    st.markdown("### 🎯 Recommandations")
    for r in sorted(recos, key=lambda x: x.get("priority", 99)):
        conv = r.get("convergence")
        conv_badge = f" `{conv}/3 modèles`" if conv else ""
        cat_colors = {"sommeil": "🌙", "récupération": "💓", "activité": "🏃", "nutrition": "🥗"}
        icon = cat_colors.get(r.get("category", "").lower(), "▶")
        target = f" → cible : **{r.get('target')}**" if r.get("target") else ""
        with st.container():
            st.markdown(f"**{r.get('priority', '')}. {icon} {r.get('action', '')}**{conv_badge}")
            st.caption(f"{r.get('rationale', '')}{target}")
            st.divider()

if _show:
    show_reco(_show)

# — Historique —
if past:
    st.subheader("Historique")
    for p in past:
        wk = str(p["week_start"])
        with st.expander(f"Semaine du {wk}"):
            final_data = p.get("final") or {}
            if final_data:
                score = final_data.get("score", "?")
                summary = final_data.get("summary", "")
                st.markdown(f"**Score : {score}/10** — {summary}")
                recos = final_data.get("recommendations", [])
                for r in recos:
                    st.markdown(f"- {r.get('action', '')}")
            else:
                st.caption("Données non disponibles")
