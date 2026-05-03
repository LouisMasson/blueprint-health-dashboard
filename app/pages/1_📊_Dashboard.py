import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from lib.db import get_health_weekly

st.set_page_config(page_title="Dashboard · Blueprint", page_icon="📊", layout="wide")
st.title("📊 Tableau de bord santé")

weeks_opt = st.sidebar.selectbox("Période", [4, 8, 12, 24], index=2)
df = get_health_weekly(weeks_opt)

if df.empty:
    st.warning("Aucune donnée. Importe un fichier d'abord.")
    st.stop()

weeks = pd.to_datetime(df["week_start"]).dt.strftime("%d %b")

CHART_BG = "rgba(0,0,0,0)"
GRID_COLOR = "rgba(255,255,255,0.08)"
TEXT_COLOR = "#f1f5f9"

def base_layout(title="", height=280):
    return dict(
        title=title, height=height,
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        font=dict(color=TEXT_COLOR, size=11),
        margin=dict(l=8, r=8, t=36, b=8),
        legend=dict(orientation="h", y=-0.2),
        xaxis=dict(showgrid=False, tickvals=list(range(len(weeks))), ticktext=list(weeks)),
        yaxis=dict(showgrid=True, gridcolor=GRID_COLOR),
    )

x = list(range(len(weeks)))

# — SOMMEIL —
st.subheader("😴 Sommeil")
fig_sleep = go.Figure()
for col, name, color in [
    ("sleep_deep_avg_h", "Profond", "#818cf8"),
    ("sleep_rem_avg_h", "REM", "#4ade80"),
    ("sleep_total_avg_h", "Total", "#94a3b8"),
]:
    if col in df.columns:
        fig_sleep.add_trace(go.Scatter(x=x, y=df[col], name=name, mode="lines+markers",
                                       line=dict(color=color, width=2), marker=dict(size=5)))
fig_sleep.add_hline(y=7, line_dash="dot", line_color="rgba(255,200,0,0.4)", annotation_text="min 7h")
fig_sleep.add_hline(y=9, line_dash="dot", line_color="rgba(255,100,100,0.4)", annotation_text="max 9h")
fig_sleep.update_layout(**base_layout(height=300))
st.plotly_chart(fig_sleep, use_container_width=True)

# — RÉCUPÉRATION —
st.subheader("💓 Récupération cardiaque")
c1, c2 = st.columns(2)
with c1:
    fig_hrv = go.Figure()
    fig_hrv.add_trace(go.Scatter(x=x, y=df.get("hrv_avg_ms"), name="HRV (ms)",
                                  mode="lines+markers", fill="tozeroy",
                                  line=dict(color="#4ade80", width=2),
                                  fillcolor="rgba(74,222,128,0.1)"))
    fig_hrv.add_hline(y=50, line_dash="dot", line_color="rgba(255,200,0,0.5)", annotation_text="cible 50ms")
    fig_hrv.update_layout(**base_layout("HRV"))
    st.plotly_chart(fig_hrv, use_container_width=True)

with c2:
    fig_rhr = go.Figure()
    fig_rhr.add_trace(go.Scatter(x=x, y=df.get("rhr_avg"), name="FC repos (bpm)",
                                  mode="lines+markers",
                                  line=dict(color="#f87171", width=2), marker=dict(size=5)))
    fig_rhr.add_hline(y=55, line_dash="dot", line_color="rgba(255,200,0,0.5)", annotation_text="cible < 55")
    fig_rhr.update_layout(**base_layout("FC repos"))
    st.plotly_chart(fig_rhr, use_container_width=True)

# — ACTIVITÉ —
st.subheader("🏃 Activité & Performance")
c3, c4 = st.columns(2)
with c3:
    fig_vo2 = go.Figure()
    if "vo2_max_latest" in df.columns and df["vo2_max_latest"].notna().any():
        fig_vo2.add_trace(go.Scatter(x=x, y=df["vo2_max_latest"], name="VO2max",
                                      mode="lines+markers", line=dict(color="#fbbf24", width=2),
                                      marker=dict(size=6, symbol="diamond")))
        fig_vo2.add_hline(y=52, line_dash="dot", line_color="rgba(255,200,0,0.5)", annotation_text="cible 52")
    else:
        fig_vo2.add_annotation(text="Données VO2max non disponibles", xref="paper", yref="paper",
                                x=0.5, y=0.5, showarrow=False, font=dict(color="#64748b"))
    fig_vo2.update_layout(**base_layout("VO2max (ml/kg/min)"))
    st.plotly_chart(fig_vo2, use_container_width=True)

with c4:
    fig_work = go.Figure()
    if "workouts_count" in df.columns:
        fig_work.add_trace(go.Bar(x=x, y=df["workouts_count"], name="Entraînements",
                                   marker_color="#a78bfa"))
    if "runs_count" in df.columns:
        fig_work.add_trace(go.Bar(x=x, y=df["runs_count"], name="Sorties course",
                                   marker_color="#4ade80"))
    fig_work.add_hline(y=4, line_dash="dot", line_color="rgba(255,200,0,0.5)", annotation_text="cible 4")
    fig_work.update_layout(**base_layout("Entraînements / semaine"), barmode="group")
    st.plotly_chart(fig_work, use_container_width=True)

# — COURSE —
if "running_distance_km" in df.columns and df["running_distance_km"].notna().any():
    st.subheader("🏅 Course à pied")
    fig_run = go.Figure()
    fig_run.add_trace(go.Bar(x=x, y=df["running_distance_km"], name="Distance (km)",
                              marker_color="#4ade80", opacity=0.8))
    fig_run.add_hline(y=25, line_dash="dot", line_color="rgba(255,200,0,0.5)", annotation_text="cible 25km")
    fig_run.update_layout(**base_layout("Distance de course hebdomadaire (km)", height=250))
    st.plotly_chart(fig_run, use_container_width=True)

# — ÉNERGIE —
st.subheader("⚡ Énergie")
c5, c6 = st.columns(2)
with c5:
    if "active_energy_total_kj" in df.columns:
        fig_ae = go.Figure()
        fig_ae.add_trace(go.Bar(x=x, y=(df["active_energy_total_kj"] / 4.184).round(0),
                                 name="Énergie active (kcal)", marker_color="#fb923c"))
        fig_ae.update_layout(**base_layout("Énergie active (kcal/sem)"))
        st.plotly_chart(fig_ae, use_container_width=True)
with c6:
    if "respiratory_rate_avg" in df.columns and df["respiratory_rate_avg"].notna().any():
        fig_resp = go.Figure()
        fig_resp.add_trace(go.Scatter(x=x, y=df["respiratory_rate_avg"], name="Fr. respiratoire (rpm)",
                                       mode="lines+markers", line=dict(color="#67e8f9", width=2)))
        fig_resp.update_layout(**base_layout("Fréquence respiratoire (rpm)"))
        st.plotly_chart(fig_resp, use_container_width=True)

# — DATA TABLE —
with st.expander("Données brutes"):
    display_cols = [c for c in [
        "week_start", "sleep_total_avg_h", "sleep_deep_avg_h", "sleep_rem_avg_h",
        "hrv_avg_ms", "rhr_avg", "vo2_max_latest", "workouts_count",
        "running_distance_km", "active_energy_total_kj", "days_with_data",
    ] if c in df.columns]
    st.dataframe(df[display_cols].sort_values("week_start", ascending=False), use_container_width=True)
