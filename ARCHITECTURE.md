Functional data flow

1. Configuration layer - config.py defines:
-what portfolios exist
-what tickers belong to them
-what benchmarks exist
-what colors/styles are used

2. Data ingestion layer - data_loader.py:
-downloads historical close prices
-repairs missing ticker data where possible
-finds the first valid close after inception
-converts dollar allocations into share counts

3. Analytics layer - calculations.py:
-computes daily portfolio values
-builds cumulative returns
-builds holdings snapshots
-calculates summary metrics
-compares portfolios to benchmarks
-generates AI commentary

4. Presentation layer - charts.py:
-applies visual styling
-creates chart-ready outputs
-renders cards and Plotly charts

5. App orchestration layer - app.py:
-wires all modules together
-controls filtering and interactions
-displays final output to the user

---------------------------------------------------------------------

# Architecture Map
config.py
   ↓
data_loader.py
   ↓
calculations.py
   ↓
charts.py
   ↓
app.py
-----------------------------------------------------------------------
#Dependency map
config.py
├── used by data_loader.py
├── used by calculations.py
├── used by charts.py
└── used by app.py

data_loader.py
└── used by app.py

calculations.py
└── used by app.py

charts.py
└── used by app.py
-----------------------------------

Settings / portfolios / CSS → config.py

API / price history / ticker issues → data_loader.py

Math / metrics / AI summary text → calculations.py

Charts / cards / color logic → charts.py

Page layout / filters / display order → app.py
