import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from config import GOOGLE_BLUES, OPENAI_ORANGES


def is_google_portfolio(name):
    return "GOOGLE" in str(name).strip().upper()


def is_openai_portfolio(name):
    return "OPENAI" in str(name).strip().upper()


def build_line_style_map(portfolio_names):
    cleaned_names = [str(name).strip() for name in portfolio_names if pd.notna(name)]
    unique_names = list(dict.fromkeys(cleaned_names))

    google_names = sorted([name for name in unique_names if is_google_portfolio(name)])
    openai_names = sorted([name for name in unique_names if is_openai_portfolio(name)])

    style_map = {}

    for i, name in enumerate(google_names):
        style_map[name] = {
            "color": GOOGLE_BLUES[i % len(GOOGLE_BLUES)],
            "dash": "solid",
            "width": 3,
        }

    for i, name in enumerate(openai_names):
        style_map[name] = {
            "color": OPENAI_ORANGES[i % len(OPENAI_ORANGES)],
            "dash": "solid",
            "width": 3,
        }

    for name in unique_names:
        upper_name = name.upper()

        if upper_name in {"SPY", "US:SPY"}:
            style_map[name] = {"color": "#ff4d4f", "dash": "dot", "width": 3}
        elif upper_name in {"DIA", "US:DIA"}:
            style_map[name] = {"color": "#ffd84d", "dash": "dot", "width": 3}
        elif upper_name == "RANDOM A":
            style_map[name] = {"color": "#ffffff", "dash": "solid", "width": 3}
        elif upper_name == "RANDOM B":
            style_map[name] = {"color": "#9ca3af", "dash": "solid", "width": 3}

    fallback_palette = [
        "#b8c1ec",
        "#cdb4db",
        "#95d5b2",
        "#84a59d",
        "#f5cac3",
        "#9bf6ff",
    ]

    unstyled_names = [name for name in unique_names if name not in style_map]
    for i, name in enumerate(unstyled_names):
        style_map[name] = {
            "color": fallback_palette[i % len(fallback_palette)],
            "dash": "solid",
            "width": 2.5,
        }

    return style_map


def apply_line_styles(fig, style_map):
    for trace in fig.data:
        trace_name = str(trace.name).strip()
        style = style_map.get(
            trace_name,
            {"color": "#d1d5db", "dash": "solid", "width": 2.5},
        )
        trace.update(
            line=dict(
                color=style["color"],
                dash=style["dash"],
                width=style["width"],
            )
        )
    return fig


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def blend_hex(a, b, t):
    t = max(0, min(1, float(t)))
    rgb_a = hex_to_rgb(a)
    rgb_b = hex_to_rgb(b)
    mixed = tuple(int(round(x + (y - x) * t)) for x, y in zip(rgb_a, rgb_b))
    return rgb_to_hex(mixed)


def build_return_bar_colors(values):
    values = pd.to_numeric(values, errors="coerce").fillna(0)
    pos_max = values[values > 0].max() if (values > 0).any() else 0
    neg_min = values[values < 0].min() if (values < 0).any() else 0

    colors = []
    for value in values:
        if value > 0:
            strength = value / pos_max if pos_max > 0 else 0
            colors.append(blend_hex("#36cfa2", "#12484a", strength))
        elif value < 0:
            strength = abs(value / neg_min) if neg_min < 0 else 0
            colors.append(blend_hex("#8b2a3a", "#2b0a0a", strength))
        else:
            colors.append("#1a2333")
    return colors


def normalize_for_heatmap(series, invert=False):
    series = pd.to_numeric(series, errors="coerce").astype(float)
    valid = series.dropna()

    if valid.empty:
        return pd.Series([0.5] * len(series), index=series.index)

    low = valid.min()
    high = valid.max()

    if np.isclose(low, high):
        scaled = pd.Series([0.5] * len(series), index=series.index)
    else:
        scaled = (series - low) / (high - low)

    if invert:
        scaled = 1 - scaled

    return scaled.fillna(0.5).clip(0, 1)


def normalize_signed_for_heatmap(
    series,
    positive_floor=0.56,
    negative_ceiling=0.44,
    neutral_score=0.50,
    rank_weight=0.70,
):
    """
    Sign-aware normalization for heatmap rows.

    Goals:
    - positive values always land on the green side
    - negative values always land on the red side
    - values with the same sign get more visible color separation

    A blended rank + magnitude score creates a smoother visual progression
    than raw min-max scaling when many values are clustered together.
    """
    series = pd.to_numeric(series, errors="coerce").astype(float)
    scaled = pd.Series(neutral_score, index=series.index, dtype=float)

    pos = series[series > 0]
    if not pos.empty:
        if len(pos) == 1:
            scaled.loc[pos.index] = 1.0
        elif np.isclose(pos.min(), pos.max()):
            scaled.loc[pos.index] = (positive_floor + 1.0) / 2.0
        else:
            pos_rank = pos.rank(method="dense", ascending=True)
            pos_rank_scaled = (pos_rank - 1) / (pos_rank.max() - 1)
            pos_mag_scaled = (pos - pos.min()) / (pos.max() - pos.min())
            pos_strength = (rank_weight * pos_rank_scaled) + ((1 - rank_weight) * pos_mag_scaled)
            scaled.loc[pos.index] = positive_floor + pos_strength * (1 - positive_floor)

    neg = series[series < 0]
    if not neg.empty:
        neg_abs = neg.abs()
        if len(neg) == 1:
            scaled.loc[neg.index] = 0.0
        elif np.isclose(neg_abs.min(), neg_abs.max()):
            scaled.loc[neg.index] = negative_ceiling / 2.0
        else:
            neg_rank = neg_abs.rank(method="dense", ascending=True)
            neg_rank_scaled = (neg_rank - 1) / (neg_rank.max() - 1)
            neg_mag_scaled = (neg_abs - neg_abs.min()) / (neg_abs.max() - neg_abs.min())
            neg_strength = (rank_weight * neg_rank_scaled) + ((1 - rank_weight) * neg_mag_scaled)
            scaled.loc[neg.index] = negative_ceiling * (1 - neg_strength)

    return scaled.fillna(neutral_score).clip(0, 1)


def chart_layout(fig, height=420, yaxis_title="", xaxis_title=""):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
        margin=dict(l=10, r=10, t=20, b=10),
        yaxis_title=yaxis_title,
        xaxis_title=xaxis_title,
        font=dict(color="#ffffff"),
        hoverlabel=dict(
            bgcolor="rgba(8,10,14,0.95)",
            bordercolor="rgba(255,255,255,0.12)",
            font_size=13,
            font_color="#ffffff",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(color="#ffffff"),
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor="rgba(255,255,255,0.15)",
        tickfont=dict(color="#ffffff"),
        title_font=dict(color="#ffffff"),
        fixedrange=True,
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.08)",
        zeroline=False,
        linecolor="rgba(255,255,255,0.15)",
        tickfont=dict(color="#ffffff"),
        title_font=dict(color="#ffffff"),
        fixedrange=True,
    )
    return fig


def render_chart(fig, key=None):
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "scrollZoom": False,
            "doubleClick": False,
            "showTips": False,
            "responsive": True,
            "staticPlot": False,
        },
        key=key,
    )


def metric_card(title, value, subtitle=""):
    st.markdown(
        f"""
        <style>
            .metric-card {{
                position: relative;
                overflow: hidden;
                padding: 18px 20px 16px 20px;
                border-radius: 22px;
                background:
                    radial-gradient(circle at top right, rgba(0, 212, 170, 0.12), transparent 30%),
                    radial-gradient(circle at bottom left, rgba(58, 123, 213, 0.10), transparent 26%),
                    linear-gradient(135deg, rgba(10,14,22,0.98), rgba(16,22,35,0.96));
                border: 1px solid rgba(255,255,255,0.08);
                box-shadow:
                    0 18px 50px rgba(0,0,0,0.28),
                    inset 0 1px 0 rgba(255,255,255,0.03);
                min-height: 132px;
            }}

            .metric-label {{
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: rgba(208,224,240,0.72);
                margin-bottom: 10px;
                font-weight: 700;
            }}

            .metric-value {{
                font-size: 1.45rem;
                font-weight: 800;
                color: #F7FBFF;
                line-height: 1.15;
                margin-bottom: 8px;
            }}

            .metric-sub {{
                font-size: 0.88rem;
                color: rgba(220, 232, 244, 0.72);
                line-height: 1.35;
            }}
        </style>

        <div class="metric-card">
            <div class="metric-label">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_portfolio_heatmap(summary_df, money_fn, pct_fn):
    if summary_df.empty:
        return None

    heat_df = summary_df.sort_values("Return", ascending=False).copy()
    metrics = [
        {"col": "Volatility", "label": "Volatility", "fmt": pct_fn},
        {"col": "Dollar Change", "label": "$ Return", "fmt": money_fn},
        {"col": "Return", "label": "% Return", "fmt": pct_fn},
    ]

    scores = {
        "Volatility": normalize_for_heatmap(heat_df["Volatility"], invert=True),
        "Dollar Change": normalize_signed_for_heatmap(heat_df["Dollar Change"]),
        "Return": normalize_signed_for_heatmap(heat_df["Return"]),
    }

    z_matrix = []
    text_matrix = []
    hover_matrix = []

    for item in metrics:
        z_row = []
        text_row = []
        hover_row = []

        for idx, row in heat_df.iterrows():
            raw = row[item["col"]]
            score = float(scores[item["col"]].loc[idx])

            z_row.append(score)
            text_row.append(item["fmt"](raw))
            hover_row.append(
                f"<b>{row['Portfolio']}</b><br>"
                f"{item['label']}: {item['fmt'](raw)}<br>"
                f"Heatmap Score: {score:.0%}"
            )

        z_matrix.append(z_row)
        text_matrix.append(text_row)
        hover_matrix.append(hover_row)

    fig = go.Figure(
        data=go.Heatmap(
            z=z_matrix,
            x=heat_df["Portfolio"].tolist(),
            y=[item["label"] for item in metrics],
            text=text_matrix,
            customdata=hover_matrix,
            texttemplate="%{text}",
            textfont={"size": 12, "color": "#f8fafc"},
            hovertemplate="%{customdata}<extra></extra>",
            zmin=0,
            zmax=1,
            xgap=8,
            ygap=8,
            colorscale=[
                [0.00, "#2b0a0a"],
                [0.16, "#5b1520"],
                [0.32, "#8b2a3a"],
                [0.50, "#1a2333"],
                [0.62, "#12484a"],
                [0.80, "#1c7f72"],
                [1.00, "#36cfa2"],
            ],
            colorbar=dict(
                title=dict(text="Strength", font=dict(color="#e5e7eb")),
                thickness=12,
                len=0.8,
                orientation="h",
                x=0.5,
                xanchor="center",
                y=-0.1,
                yanchor="top",
                tickvals=[0, 0.5, 1],
                ticktext=["Weak", "Mid", "Strong"],
                outlinewidth=0,
                tickfont=dict(color="#cbd5e1"),
            ),
        )
    )

    fig.update_layout(
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=20, b=10),
        font=dict(color="#e5e7eb"),
    )

    fig.update_xaxes(
        side="top",
        showgrid=False,
        zeroline=False,
        tickfont=dict(size=12, color="#cbd5e1"),
        showline=False,
        fixedrange=True,
    )

    fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        tickfont=dict(size=13, color="#f8fafc"),
        showline=False,
        fixedrange=True,
    )

    return fig
