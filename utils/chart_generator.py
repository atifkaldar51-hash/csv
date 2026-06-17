"""
utils/chart_generator.py
========================

Matplotlib wrapper that produces Bar / Line / Pie chart PNGs and
returns a URL-safe path that the Flask layer can serve.

All charts are saved into the `static/charts/` directory of the
running Flask app. Each saved file gets a unique timestamped name
so the user can keep a history of generated charts.

Public API:
    ChartGenerationError
    generate_bar_chart(df, x_col, y_col, out_dir)   -> url path
    generate_line_chart(df, x_col, y_col, out_dir)  -> url path
    generate_pie_chart(df, cat_col, out_dir)        -> url path
"""

import os
import uuid
from datetime import datetime

import matplotlib
matplotlib.use('Agg')  # headless backend for server-side rendering
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

import pandas as pd
import numpy as np


# ------------------------------------------------------------------
# Font setup (Apple-inspired system look)
# ------------------------------------------------------------------
# Try to register a clean sans-serif font if available; fall back
# silently to Matplotlib defaults otherwise.
_FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
]
for _f in _FONT_CANDIDATES:
    if os.path.exists(_f):
        try:
            fm.fontManager.addfont(_f)
        except Exception:
            pass

plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Liberation Sans', 'Arial']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 120
plt.rcParams['savefig.dpi'] = 120
plt.rcParams['axes.edgecolor'] = '#E5E5EA'
plt.rcParams['axes.labelcolor'] = '#1D1D1F'
plt.rcParams['xtick.color'] = '#3C3C43'
plt.rcParams['ytick.color'] = '#3C3C43'


# Apple-inspired palette
APPLE_BLUE = '#007AFF'
APPLE_COLORS = [
    '#007AFF', '#FF3B30', '#34C759', '#FF9500',
    '#AF52DE', '#5AC8FA', '#FFD60A', '#FF2D55',
    '#5856D6', '#00C7BE'
]


class ChartGenerationError(Exception):
    """Raised when chart generation fails due to bad input/data."""


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _safe_out_path(out_dir, prefix='chart'):
    """Return a unique file path inside `out_dir` plus its URL path."""
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    uid = uuid.uuid4().hex[:6]
    filename = f'{prefix}_{ts}_{uid}.png'
    full_path = os.path.join(out_dir, filename)
    url_path = f'/static/charts/{filename}'
    return full_path, url_path


def _require_columns(df, *cols):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ChartGenerationError(
            f'Column(s) not found in dataset: {", ".join(missing)}'
        )


def _aggregate(df, x_col, y_col):
    """
    If multiple rows share the same X value, aggregate the Y values
    using mean so the chart is meaningful even for raw record lists.
    """
    sub = df[[x_col, y_col]].copy()
    sub[x_col] = sub[x_col].astype(str)

    if sub[y_col].dtype.kind in 'biufc':  # numeric
        agg = sub.groupby(x_col, dropna=False)[y_col].mean().reset_index()
    else:
        # Fall back to counts if the Y column is non-numeric
        agg = sub.groupby(x_col, dropna=False)[y_col].count().reset_index()

    return agg


def _style_axes(ax):
    """Apply the clean Apple-style look to an Axes object."""
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    ax.spines['left'].set_color('#E5E5EA')
    ax.spines['bottom'].set_color('#E5E5EA')
    ax.grid(axis='y', linestyle='--', linewidth=0.6, color='#E5E5EA', alpha=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


# ------------------------------------------------------------------
# Bar chart
# ------------------------------------------------------------------
def generate_bar_chart(df, x_col, y_col, out_dir):
    if not x_col or not y_col:
        raise ChartGenerationError('Please select both X and Y columns.')
    _require_columns(df, x_col, y_col)

    if df[y_col].dtype.kind not in 'biufc':
        raise ChartGenerationError(
            f'Y column "{y_col}" must be numeric for a bar chart.'
        )

    agg = _aggregate(df, x_col, y_col)
    if agg.empty:
        raise ChartGenerationError('No data available to plot.')

    # Limit very long categorical axes for readability
    if len(agg) > 30:
        agg = agg.sort_values(y_col, ascending=False).head(30)

    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    bars = ax.bar(
        agg[x_col].astype(str), agg[y_col],
        color=APPLE_BLUE, edgecolor='none', width=0.6
    )

    # Soft gradient-like effect: highlight the tallest bar
    if len(bars):
        tallest = max(bars, key=lambda b: b.get_height())
        tallest.set_color('#0051D5')

    ax.set_title(f'Bar Chart: {y_col} by {x_col}',
                 fontsize=14, color='#1D1D1F', pad=12, loc='left')
    ax.set_xlabel(x_col, fontsize=11)
    ax.set_ylabel(y_col, fontsize=11)
    _style_axes(ax)

    # Rotate X labels if many categories
    if len(agg) > 8:
        plt.setp(ax.get_xticklabels(), rotation=35, ha='right')

    full_path, url_path = _safe_out_path(out_dir, prefix='bar')
    fig.savefig(full_path, facecolor='white')
    plt.close(fig)
    return url_path


# ------------------------------------------------------------------
# Line chart
# ------------------------------------------------------------------
def generate_line_chart(df, x_col, y_col, out_dir):
    if not x_col or not y_col:
        raise ChartGenerationError('Please select both X and Y columns.')
    _require_columns(df, x_col, y_col)

    if df[y_col].dtype.kind not in 'biufc':
        raise ChartGenerationError(
            f'Y column "{y_col}" must be numeric for a line chart.'
        )

    # Sort by X if X is numeric or datetime-like, else preserve order
    sub = df[[x_col, y_col]].copy()
    sub[x_col] = sub[x_col].astype(str)

    # Try numeric sort on X for nicer line plotting
    try:
        sub['_x_num'] = pd.to_numeric(df[x_col], errors='coerce')
        if sub['_x_num'].notnull().mean() > 0.8:
            sub = sub.sort_values('_x_num')
        else:
            sub = sub.sort_values(x_col)
    except Exception:
        sub = sub.sort_values(x_col)

    # Downsample very long series so the chart stays readable and
    # renders quickly. We take every Nth row, preserving the overall
    # shape of the curve. 5,000 points is plenty for a line chart.
    MAX_LINE_POINTS = 5000
    if len(sub) > MAX_LINE_POINTS:
        step = max(1, len(sub) // MAX_LINE_POINTS)
        sub = sub.iloc[::step].copy()

    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    ax.plot(
        sub[x_col], sub[y_col],
        color=APPLE_BLUE, linewidth=2.4, marker='o',
        markersize=6, markerfacecolor='white',
        markeredgecolor=APPLE_BLUE, markeredgewidth=1.8
    )

    # Fill below the line for an elegant area effect
    ax.fill_between(sub[x_col], sub[y_col],
                    color=APPLE_BLUE, alpha=0.08)

    ax.set_title(f'Line Chart: {y_col} over {x_col}',
                 fontsize=14, color='#1D1D1F', pad=12, loc='left')
    ax.set_xlabel(x_col, fontsize=11)
    ax.set_ylabel(y_col, fontsize=11)
    _style_axes(ax)

    if len(sub) > 10:
        plt.setp(ax.get_xticklabels(), rotation=35, ha='right')

    full_path, url_path = _safe_out_path(out_dir, prefix='line')
    fig.savefig(full_path, facecolor='white')
    plt.close(fig)
    return url_path


# ------------------------------------------------------------------
# Pie chart
# ------------------------------------------------------------------
def generate_pie_chart(df, cat_col, out_dir):
    if not cat_col:
        raise ChartGenerationError('Please select a category column.')
    _require_columns(df, cat_col)

    series = df[cat_col].astype(str).value_counts()
    if series.empty:
        raise ChartGenerationError('No data available to plot.')

    # Keep top 8 slices, group the rest into "Other"
    if len(series) > 8:
        top = series.head(7)
        other = series.iloc[7:].sum()
        series = pd.concat([top, pd.Series({'Other': other})])

    fig, ax = plt.subplots(figsize=(7, 7), constrained_layout=True)
    wedges, texts, autotexts = ax.pie(
        series.values,
        labels=series.index,
        colors=APPLE_COLORS[:len(series)],
        autopct='%1.1f%%',
        startangle=90,
        wedgeprops={'edgecolor': 'white', 'linewidth': 2},
        textprops={'fontsize': 10, 'color': '#1D1D1F'},
        pctdistance=0.78,
    )
    for at in autotexts:
        at.set_color('white')
        at.set_fontweight('bold')

    # Donut effect
    centre_circle = plt.Circle((0, 0), 0.55, fc='white')
    ax.add_artist(centre_circle)

    ax.set_title(f'Pie Chart: distribution of {cat_col}',
                 fontsize=14, color='#1D1D1F', pad=12, loc='left')
    ax.axis('equal')

    full_path, url_path = _safe_out_path(out_dir, prefix='pie')
    fig.savefig(full_path, facecolor='white')
    plt.close(fig)
    return url_path
