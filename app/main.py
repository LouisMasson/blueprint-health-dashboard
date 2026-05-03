import streamlit as st
import pandas as pd
from lib.db import get_health_weekly
from lib.config import METRIC_TARGETS

st.set_page_config(
    page_title="Blueprint Health",
    page_icon="💚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("💚 Blueprint Health Dashboard")
st.caption("Données Apple Watch · Mise à jour hebdomadaire")

df = get_health_weekly(12)

if df.empty:
    st.warning("Aucune donnée disponible. Importe un fichier via la page **Import**.")
    st.stop()

latest = df.iloc[-1]
prev = df.iloc[-2] if len(df) >= 2 else None
week_label = str(latest["week_start"])

st.subheader(f"Semaine du {week_label}")

cols = st.columns(4)

def kpi(col, metric_key, value, prev_value=None):
    cfg = METRIC_TARGETS.get(metric_key, {})
    label = cfg.get("label", metric_key)
    unit = cfg.get("unit", "")
    higher_better = cfg.get("higher_better", True)

    if value is None or pd.isna(value):
        col.metric(label, "—")
        return

    target_min = cfg.get("min")
    target_max = cfg.get("max")

    if higher_better and target_min and value >= target_min:
        delta_color = "normal"
    elif not higher_better and target_max and value <= target_max:
        delta_color = "normal"
    else:
        delta_color = "inverse"

    delta = None
    if prev_value is not None and not pd.isna(prev_value) and prev_value != 0:
        delta = round(value - prev_value, 2)

    col.metric(
        label=f"{label} ({unit})" if unit else label,
        value=f"{value:.1f}",
        delta=f"{delta:+.1f}" if delta is not None else None,
        delta_color=delta_color,
    )


metrics_row1 = ["sleep_total_avg_h", "hrv_avg_ms", "rhr_avg", "vo2_max_latest"]
metrics_row2 = ["sleep_deep_avg_h", "sleep_rem_avg_h", "workouts_count", "running_distance_km"]

for i, m in enumerate(metrics_row1):
    val = latest.get(m)
    prev_val = prev[m] if prev is not None else None
    kpi(cols[i], m, val, prev_val)

cols2 = st.columns(4)
for i, m in enumerate(metrics_row2):
    val = latest.get(m)
    prev_val = prev[m] if prev is not None else None
    kpi(cols2[i], m, val, prev_val)

st.divider()

# Mini trend sparklines
import plotly.graph_objects as go

st.subheader("Tendances 12 semaines")
trend_cols = st.columns(2)

def sparkline(col, title, x, y, target_min=None, target_max=None, color="#4ade80"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", line=dict(color=color, width=2),
                             marker=dict(size=5)))
    if target_min:
        fig.add_hline(y=target_min, line_dash="dot", line_color="rgba(255,255,100,0.5)",
                      annotation_text=f"min {target_min}", annotation_position="bottom right")
    if target_max:
        fig.add_hline(y=target_max, line_dash="dot", line_color="rgba(255,100,100,0.5)",
                      annotation_text=f"max {target_max}", annotation_position="top right")
    fig.update_layout(
        title=title, height=200, margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, tickformat="%d/%m"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
        font=dict(color="#f1f5f9"),
    )
    col.plotly_chart(fig, use_container_width=True)

weeks = df["week_start"].astype(str)

with trend_cols[0]:
    sparkline(trend_cols[0], "Sommeil total (h)", weeks, df["sleep_total_avg_h"], target_min=7, target_max=9)
with trend_cols[1]:
    sparkline(trend_cols[1], "HRV (ms)", weeks, df["hrv_avg_ms"], target_min=50)

trend_cols2 = st.columns(2)
with trend_cols2[0]:
    sparkline(trend_cols2[0], "FC repos (bpm)", weeks, df["rhr_avg"], color="#f87171")
with trend_cols2[1]:
    sparkline(trend_cols2[1], "Entraînements / semaine", weeks, df["workouts_count"], target_min=4, color="#a78bfa")
