# From Noise to Action

A Streamlit-based portfolio dashboard that tracks a custom set of portfolios using daily **Yahoo Finance close prices** via `yfinance`.

The app recreates a portfolio comparison dashboard with:
- portfolio-level return tracking
- benchmark comparison
- cumulative return analysis
- portfolio heatmaps
- holdings drilldowns
- AI-generated performance commentary

---

## What this app does

This app:
1. defines portfolios directly in Python
2. pulls daily market close prices from Yahoo Finance
3. calculates portfolio values from a fixed inception date
4. compares all portfolios against each other and against benchmarks
5. displays the results in a modern Streamlit dashboard

The current inception date is controlled in `config.py`.

---

## Project structure

```text
.
├── app.py
├── config.py
├── data_loader.py
├── calculations.py
├── charts.py
└── requirements.txt
