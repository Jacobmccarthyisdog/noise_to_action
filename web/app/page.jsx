"use client";

import { useEffect, useMemo, useState } from "react";

const FALLBACK_DATA = {
  as_of_date: "2026-06-17",
  start_date: "2026-02-05",
  benchmarks: { SPY: "SPY", DIA: "DIA" },
  portfolio_names: [
    "Google 10",
    "Google 50",
    "Google 100",
    "OpenAI 10",
    "OpenAI 50",
    "OpenAI 100",
    "Random A",
    "Random B",
  ],
  summary: [],
  holdings: [],
  portfolio_history: [],
  benchmark_history: [],
  daily_insight: {
    headline: "Portfolio dashboard ready for exported data",
    summary:
      "Run the Python export job to populate live portfolio history, holdings, benchmark comparisons, and daily commentary for this dashboard.",
    takeaways: [
      "The frontend is wired to /data/dashboard.json.",
      "The existing Python analytics layer remains the source of truth.",
      "Vercel can serve this as a polished web dashboard once the JSON artifact is generated.",
    ],
  },
};

const COLORS = {
  coral: "#D85A30",
  sage: "#5DCAA5",
  brick: "#A32D2D",
  spy: "#173B73",
  dia: "#2F80C2",
  randomA: "#EBCB6A",
  randomB: "#F4D98A",
};

function toNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function money(value) {
  const number = toNumber(value);
  if (number === null) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(number);
}

function pct(value) {
  const number = toNumber(value);
  if (number === null) return "-";
  return `${(number * 100).toFixed(2)}%`;
}

function compactPct(value) {
  const number = toNumber(value);
  if (number === null) return "-";
  return `${(number * 100).toFixed(1)}%`;
}

function parseDate(value) {
  return value ? new Date(`${value}T00:00:00`) : null;
}

function groupBy(items, key) {
  return items.reduce((acc, item) => {
    const group = item[key];
    if (!acc[group]) acc[group] = [];
    acc[group].push(item);
    return acc;
  }, {});
}

function lineStyle(name) {
  const upper = String(name).toUpperCase();

  if (upper === "SPY") return COLORS.spy;
  if (upper === "DIA") return COLORS.dia;
  if (upper === "RANDOM A") return COLORS.randomA;
  if (upper === "RANDOM B") return COLORS.randomB;
  if (upper.includes("GOOGLE")) {
    const palette = ["#6E5A33", "#826A3D", "#9A7E4A", "#B49359", "#C9A66A"];
    const index = Number(upper.match(/\d+/)?.[0] || 10) / 10 - 1;
    return palette[Math.max(0, Math.min(palette.length - 1, index))];
  }
  if (upper.includes("OPENAI")) {
    const palette = ["#993C1D", "#B94322", "#C94A24", "#D85A30", "#E06A3D"];
    const index = Number(upper.match(/\d+/)?.[0] || 10) / 10 - 1;
    return palette[Math.max(0, Math.min(palette.length - 1, index))];
  }

  return "#9A9386";
}

function buildSummary(history) {
  const groups = groupBy(history, "Portfolio");

  return Object.entries(groups)
    .map(([portfolio, rows]) => {
      const sorted = rows
        .filter((row) => toNumber(row["Portfolio Value"]) !== null)
        .sort((a, b) => String(a.Date).localeCompare(String(b.Date)));

      if (sorted.length < 2) return null;

      const values = sorted.map((row) => Number(row["Portfolio Value"]));
      const start = values[0];
      const current = values[values.length - 1];
      const high = Math.max(...values);
      const low = Math.min(...values);

      let runningMax = values[0];
      const drawdowns = values.map((value) => {
        runningMax = Math.max(runningMax, value);
        return value / runningMax - 1;
      });

      const dailyReturns = values
        .slice(1)
        .map((value, index) => value / values[index] - 1)
        .filter(Number.isFinite);
      const average =
        dailyReturns.reduce((sum, value) => sum + value, 0) /
        Math.max(1, dailyReturns.length);
      const variance =
        dailyReturns.reduce((sum, value) => sum + (value - average) ** 2, 0) /
        Math.max(1, dailyReturns.length - 1);

      return {
        Portfolio: portfolio,
        "Start Value": start,
        "Current Value": current,
        "Dollar Change": current - start,
        Return: current / start - 1,
        "High Value": high,
        "Low Value": low,
        "Max Drawdown": Math.min(...drawdowns),
        Volatility: Math.sqrt(variance),
      };
    })
    .filter(Boolean)
    .sort((a, b) => b.Return - a.Return);
}

function buildBenchmarkSummary(history, benchmark) {
  const rows = history
    .filter((row) => row.Benchmark === benchmark)
    .filter((row) => toNumber(row["Benchmark Value"]) !== null)
    .sort((a, b) => String(a.Date).localeCompare(String(b.Date)));

  if (rows.length < 2) return null;

  const start = Number(rows[0]["Benchmark Value"]);
  const end = Number(rows[rows.length - 1]["Benchmark Value"]);
  return { Benchmark: benchmark, Return: end / start - 1 };
}

function buildCumulativeSeries(history, valueKey, groupKey, outputKey) {
  return Object.entries(groupBy(history, groupKey)).flatMap(([name, rows]) => {
    const sorted = rows
      .filter((row) => toNumber(row[valueKey]) !== null)
      .sort((a, b) => String(a.Date).localeCompare(String(b.Date)));

    if (!sorted.length) return [];

    const firstValue = Number(sorted[0][valueKey]);
    return sorted.map((row) => ({
      Date: row.Date,
      name,
      value: firstValue ? Number(row[valueKey]) / firstValue - 1 : null,
      [outputKey]: name,
    }));
  });
}

function normalize(value, min, max) {
  if (!Number.isFinite(value) || !Number.isFinite(min) || !Number.isFinite(max)) return 0.5;
  if (Math.abs(max - min) < 0.0000001) return 0.5;
  return Math.max(0, Math.min(1, (value - min) / (max - min)));
}

function signedScore(value, maxPositive, minNegative) {
  if (!Number.isFinite(value) || value === 0) return 0.5;
  if (value > 0) return 0.62 + (value / Math.max(maxPositive, value)) * 0.38;
  return 0.38 * (1 - value / Math.min(minNegative, value));
}

function mix(a, b, t) {
  const clamped = Math.max(0, Math.min(1, t));
  return a.map((value, index) => Math.round(value + (b[index] - value) * clamped));
}

function heatColor(score) {
  const brick = [252, 235, 235];
  const neutral = [245, 241, 232];
  const sage = [225, 245, 238];
  const strongSage = [93, 202, 165];
  const rgb =
    score < 0.5
      ? mix(brick, neutral, score / 0.5)
      : mix(sage, strongSage, (score - 0.5) / 0.5);

  return `rgb(${rgb.join(", ")})`;
}

function MetricCard({ label, value, sub, tone = "neutral" }) {
  return (
    <section className="metric-card">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone}`}>{value}</div>
      <div className="metric-sub">{sub}</div>
    </section>
  );
}

function cleanInsightHeadline(headline, benchmark) {
  if (!headline) return "Daily insight";

  if (headline === "Portfolio outperforms benchmark YTD") {
    return benchmark ? `Portfolios lead ${benchmark} YTD` : "Portfolios lead benchmark YTD";
  }

  return headline.replace(/^Portfolio /, "Portfolios ");
}

function TrendChart({ series }) {
  const width = 960;
  const height = 390;
  const padding = { top: 22, right: 24, bottom: 38, left: 58 };
  const values = series.map((point) => point.value).filter(Number.isFinite);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const byName = groupBy(series, "name");

  if (!series.length || !values.length) {
    return <div className="empty-state">No cumulative return data available.</div>;
  }

  const dates = [...new Set(series.map((point) => point.Date))].sort();
  const xFor = (date) => {
    const index = dates.indexOf(date);
    return padding.left + (index / Math.max(1, dates.length - 1)) * (width - padding.left - padding.right);
  };
  const yFor = (value) =>
    padding.top +
    (1 - normalize(value, min, max)) * (height - padding.top - padding.bottom);
  const zeroY = yFor(0);

  return (
    <div className="chart-scroll">
      <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img">
        <line x1={padding.left} x2={width - padding.right} y1={zeroY} y2={zeroY} className="zero-line" />
        {[0.25, 0.5, 0.75].map((tick) => {
          const y = padding.top + tick * (height - padding.top - padding.bottom);
          return <line key={tick} x1={padding.left} x2={width - padding.right} y1={y} y2={y} className="grid-line" />;
        })}
        {Object.entries(byName).map(([name, rows]) => {
          const path = rows
            .sort((a, b) => String(a.Date).localeCompare(String(b.Date)))
            .map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(point.Date)} ${yFor(point.value)}`)
            .join(" ");
          return (
            <path
              key={name}
              d={path}
              fill="none"
              stroke={lineStyle(name)}
              strokeWidth={name === "SPY" || name === "DIA" ? 4 : 3}
              strokeDasharray={name === "SPY" || name === "DIA" ? "7 7" : "0"}
              strokeLinecap="round"
            />
          );
        })}
      </svg>
    </div>
  );
}

function Heatmap({ summary }) {
  if (!summary.length) return <div className="empty-state">No heatmap data available.</div>;

  const rows = [
    { key: "Volatility", label: "Volatility", format: pct, invert: true },
    { key: "Dollar Change", label: "$ Return", format: money, signed: true },
    { key: "Return", label: "% Return", format: pct, signed: true },
  ];
  const positives = summary.map((row) => Number(row.Return)).filter((value) => value > 0);
  const negatives = summary.map((row) => Number(row.Return)).filter((value) => value < 0);
  const dollarPositives = summary.map((row) => Number(row["Dollar Change"])).filter((value) => value > 0);
  const dollarNegatives = summary.map((row) => Number(row["Dollar Change"])).filter((value) => value < 0);
  const volatilityValues = summary.map((row) => Number(row.Volatility)).filter(Number.isFinite);

  return (
    <div className="heatmap" style={{ "--columns": summary.length }}>
      <div className="heatmap-row header">
        <div />
        {summary.map((row) => (
          <div key={row.Portfolio}>{row.Portfolio}</div>
        ))}
      </div>
      {rows.map((metric) => (
        <div className="heatmap-row" key={metric.key}>
          <div className="heat-label">{metric.label}</div>
          {summary.map((row) => {
            const value = Number(row[metric.key]);
            let score;
            if (metric.key === "Volatility") {
              score = 1 - normalize(value, Math.min(...volatilityValues), Math.max(...volatilityValues));
            } else if (metric.key === "Dollar Change") {
              score = signedScore(value, Math.max(...dollarPositives, 0), Math.min(...dollarNegatives, 0));
            } else {
              score = signedScore(value, Math.max(...positives, 0), Math.min(...negatives, 0));
            }
            return (
              <div className="heat-cell" style={{ background: heatColor(score) }} key={`${metric.key}-${row.Portfolio}`}>
                {metric.format(value)}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function RankingBars({ summary }) {
  const maxAbs = Math.max(...summary.map((row) => Math.abs(Number(row.Return) || 0)), 0.01);

  if (!summary.length) return <div className="empty-state">No ranking data available.</div>;

  return (
    <div className="ranking-list">
      {summary.map((row, index) => {
        const value = Number(row.Return) || 0;
        const dollarChange = Number(row["Dollar Change"]) || 0;
        return (
          <div className="ranking-row" key={row.Portfolio}>
            <div className="ranking-identity">
              <span className="ranking-badge">{index + 1}</span>
              <div>
                <div className="ranking-name">{row.Portfolio}</div>
                <div className={dollarChange >= 0 ? "ranking-delta positive" : "ranking-delta negative"}>
                  {dollarChange >= 0 ? "+" : ""}
                  {money(dollarChange)}
                </div>
              </div>
            </div>
            <div className="ranking-bar-zone">
              <div className="ranking-track">
                <div
                  className={value >= 0 ? "ranking-fill positive" : "ranking-fill negative"}
                  style={{ width: `${Math.max(5, (Math.abs(value) / maxAbs) * 100)}%` }}
                />
              </div>
            </div>
            <div className={value >= 0 ? "ranking-value positive" : "ranking-value negative"}>
              {compactPct(value)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState(FALLBACK_DATA);
  const [selected, setSelected] = useState(FALLBACK_DATA.portfolio_names);
  const [benchmark, setBenchmark] = useState("SPY");
  const [startDate, setStartDate] = useState(FALLBACK_DATA.start_date);
  const [endDate, setEndDate] = useState(FALLBACK_DATA.as_of_date);
  const [chosenPortfolio, setChosenPortfolio] = useState(FALLBACK_DATA.portfolio_names[0]);

  useEffect(() => {
    fetch("/data/dashboard.json", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : FALLBACK_DATA))
      .then((payload) => {
        const names = payload.portfolio_names?.length ? payload.portfolio_names : FALLBACK_DATA.portfolio_names;
        setData(payload);
        setSelected(names);
        setBenchmark(Object.keys(payload.benchmarks || { SPY: "SPY" })[0] || "SPY");
        setStartDate(payload.start_date || FALLBACK_DATA.start_date);
        setEndDate(payload.as_of_date || FALLBACK_DATA.as_of_date);
        setChosenPortfolio(names[0]);
      })
      .catch(() => setData(FALLBACK_DATA));
  }, []);

  const portfolioNames = data.portfolio_names?.length ? data.portfolio_names : FALLBACK_DATA.portfolio_names;
  const benchmarkOptions = Object.keys(data.benchmarks || { SPY: "SPY" });

  const filteredHistory = useMemo(() => {
    const start = parseDate(startDate);
    const end = parseDate(endDate);
    return (data.portfolio_history || []).filter((row) => {
      const date = parseDate(row.Date);
      return selected.includes(row.Portfolio) && (!start || date >= start) && (!end || date <= end);
    });
  }, [data, selected, startDate, endDate]);

  const filteredBenchmarkHistory = useMemo(() => {
    const start = parseDate(startDate);
    const end = parseDate(endDate);
    return (data.benchmark_history || []).filter((row) => {
      const date = parseDate(row.Date);
      return row.Benchmark === benchmark && (!start || date >= start) && (!end || date <= end);
    });
  }, [data, benchmark, startDate, endDate]);

  const summary = useMemo(() => buildSummary(filteredHistory), [filteredHistory]);
  const benchmarkSummary = useMemo(
    () => buildBenchmarkSummary(filteredBenchmarkHistory, benchmark),
    [filteredBenchmarkHistory, benchmark]
  );
  const holdings = useMemo(
    () => (data.holdings || []).filter((row) => selected.includes(row.Portfolio)),
    [data, selected]
  );
  const chosenHoldings = holdings.filter((row) => row.Portfolio === chosenPortfolio);
  const chosenSummary = summary.find((row) => row.Portfolio === chosenPortfolio);

  const trendSeries = useMemo(() => {
    const portfolioSeries = buildCumulativeSeries(
      filteredHistory,
      "Portfolio Value",
      "Portfolio",
      "Portfolio"
    );
    const benchmarkSeries = buildCumulativeSeries(
      filteredBenchmarkHistory,
      "Benchmark Value",
      "Benchmark",
      "Benchmark"
    );
    return [...portfolioSeries, ...benchmarkSeries];
  }, [filteredHistory, filteredBenchmarkHistory]);

  const topPortfolio = summary[0];
  const bottomPortfolio = summary[summary.length - 1];
  const averageReturn = summary.length
    ? summary.reduce((sum, row) => sum + Number(row.Return || 0), 0) / summary.length
    : null;
  const averageAlpha =
    averageReturn !== null && benchmarkSummary ? averageReturn - benchmarkSummary.Return : null;
  const insight = data.daily_insight || FALLBACK_DATA.daily_insight;
  const selectedStartValue = summary.reduce((sum, row) => sum + Number(row["Start Value"] || 0), 0);
  const selectedCurrentValue = summary.reduce((sum, row) => sum + Number(row["Current Value"] || 0), 0);
  const selectedDollarChange = selectedCurrentValue - selectedStartValue;
  const selectedReturn =
    selectedStartValue > 0 ? selectedCurrentValue / selectedStartValue - 1 : null;

  function togglePortfolio(name) {
    setSelected((current) => {
      const next = current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name];
      if (!next.includes(chosenPortfolio)) setChosenPortfolio(next[0] || name);
      return next;
    });
  }

  return (
    <main>
      <section className="hero">
        <div className="hero-kicker">From Noise to Action</div>
        <h1>Can AI beat the market?</h1>
        <p>
          Eight portfolios, two benchmarks, and one simple test: whether AI-picked baskets
          can create real separation from SPY and DIA once the noise settles into numbers.
        </p>
        <div className="hero-meta">
          <span><b>As of</b> {data.as_of_date || "-"}</span>
          <span><b>Start</b> {data.start_date || "-"}</span>
          <span><b>Portfolios</b> {portfolioNames.length}</span>
          <span className={selectedDollarChange >= 0 ? "performance-pill positive" : "performance-pill negative"}>
            <b>Portfolio to date</b> {selectedDollarChange >= 0 ? "+" : ""}
            {money(selectedDollarChange)}
          </span>
          <span className={selectedReturn >= 0 ? "performance-pill positive" : "performance-pill negative"}>
            <b>Total return</b> {pct(selectedReturn)}
          </span>
        </div>
      </section>

      <details className="settings-panel">
        <summary>
          <span>Portfolio Settings</span>
          <small>{selected.length} selected · {benchmark}</small>
        </summary>
        <section className="control-panel">
          <div className="control-group portfolio-picker">
            <div className="control-label">Portfolios</div>
            <div className="portfolio-chips">
              {portfolioNames.map((name) => (
                <button
                  className={selected.includes(name) ? "chip active" : "chip"}
                  key={name}
                  onClick={() => togglePortfolio(name)}
                  type="button"
                >
                  {name}
                </button>
              ))}
            </div>
          </div>
          <label className="control-group">
            <span className="control-label">Benchmark</span>
            <select value={benchmark} onChange={(event) => setBenchmark(event.target.value)}>
              {benchmarkOptions.map((name) => (
                <option value={name} key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label className="control-group">
            <span className="control-label">Start</span>
            <input type="date" value={startDate || ""} onChange={(event) => setStartDate(event.target.value)} />
          </label>
          <label className="control-group">
            <span className="control-label">End</span>
            <input type="date" value={endDate || ""} onChange={(event) => setEndDate(event.target.value)} />
          </label>
        </section>
      </details>

      <details className="settings-panel about-panel">
        <summary>
          <span>About This Experiment</span>
          <small>Methodology · 2026 test</small>
        </summary>
        <section className="about-content">
          <p>
            This is a simple 2026 experiment: give AI systems the same portfolio challenge,
            compare the resulting baskets against SPY and DIA, and see what actually holds up by
            December 31.
          </p>
          <div className="about-grid">
            <div>
              <h3>AI portfolios</h3>
              <p>
                OpenAI and Google cohorts used the same system prompt: pick five stocks with
                $1,000 and the only goal of beating the benchmarks in 2026. The 10, 50, and 100
                portfolios reflect repeated prompt runs that were aggregated into final baskets.
              </p>
            </div>
            <div>
              <h3>Random controls</h3>
              <p>
                Random A and Random B were built by a Python randomizer over an available S&P 500
                stock list. They are here as a clean baseline: no model, no thesis, just chance.
              </p>
            </div>
          </div>
          <p className="about-note">
            This dashboard is for tracking the experiment, not investment advice.
          </p>
        </section>
      </details>

      <section className="ticker-shell">
        <div className="ticker-track">
          {[...summary, ...summary].map((row, index) => (
            <div className="ticker-card" key={`${row.Portfolio}-${index}`}>
              <div className="ticker-name">{row.Portfolio}</div>
              <div className="ticker-price">{money(row["Current Value"])}</div>
              <div className="ticker-stats">
                <span className={row.Return >= 0 ? "up" : "down"}>{compactPct(row.Return)}</span>
                <span>{money(row["Dollar Change"])}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="ai-card">
        <div className="ai-kicker">Daily commentary</div>
        <h2>{cleanInsightHeadline(insight.headline, benchmark)}</h2>
        <p>{insight.summary || insight.insight_text}</p>
        <div className="takeaways">
          {(insight.takeaways || []).slice(0, 5).map((item) => (
            <div className="takeaway-item" key={item}>{item}</div>
          ))}
        </div>
      </section>

      <section className="section-block">
        <div className="section-label">Performance</div>
        <h2>Benchmark-relative readout</h2>
        <div className="metric-grid">
          <MetricCard
            label="Best portfolio"
            value={topPortfolio?.Portfolio || "-"}
            sub={topPortfolio ? `${pct(topPortfolio.Return)} / ${money(topPortfolio["Current Value"])}` : "-"}
          />
          <MetricCard
            label="Average alpha"
            value={pct(averageAlpha)}
            sub={`Average portfolio return ${pct(averageReturn)} vs ${benchmark} ${pct(benchmarkSummary?.Return)}`}
            tone={averageAlpha >= 0 ? "positive" : "negative"}
          />
          <MetricCard
            label="Softest portfolio"
            value={bottomPortfolio?.Portfolio || "-"}
            sub={bottomPortfolio ? `${pct(bottomPortfolio.Return)} / max drawdown ${pct(bottomPortfolio["Max Drawdown"])}` : "-"}
          />
        </div>
      </section>

      <section className="section-block">
        <div className="section-label">Portfolio ranking</div>
        <h2>Total return by portfolio</h2>
        <RankingBars summary={summary} />
      </section>

      <section className="section-block">
        <div className="section-label">Signal map</div>
        <h2>Portfolio heatmap</h2>
        <p className="small-note">
          Warmer cells indicate softer relative performance. Cooler green cells indicate stronger relative performance.
          Lower volatility is rewarded.
        </p>
        <Heatmap summary={summary} />
      </section>

      <section className="section-block">
        <div className="section-label">Trend</div>
        <h2>Cumulative return comparison</h2>
        <p className="small-note">Percent return since the start of the selected date range.</p>
        <TrendChart series={trendSeries} />
        <div className="legend">
          {[...selected, benchmark].map((name) => (
            <span key={name}><i style={{ background: lineStyle(name) }} />{name}</span>
          ))}
        </div>
      </section>

      <section className="section-block detail-grid">
        <div>
          <div className="section-label">Drilldown</div>
          <h2>Portfolio detail</h2>
          <select className="detail-select" value={chosenPortfolio} onChange={(event) => setChosenPortfolio(event.target.value)}>
            {selected.map((name) => (
              <option value={name} key={name}>{name}</option>
            ))}
          </select>
          <div className="detail-metrics">
            <MetricCard label="Current value" value={money(chosenSummary?.["Current Value"])} sub="Latest portfolio value" />
            <MetricCard label="Return" value={pct(chosenSummary?.Return)} sub={`Dollar change ${money(chosenSummary?.["Dollar Change"])}`} tone={chosenSummary?.Return >= 0 ? "positive" : "negative"} />
          </div>
        </div>
        <div className="table-card">
          <table>
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Initial</th>
                <th>Current</th>
                <th>Return</th>
              </tr>
            </thead>
            <tbody>
              {chosenHoldings.map((row) => (
                <tr key={`${row.Portfolio}-${row.Ticker}`}>
                  <td>{row.Ticker}</td>
                  <td>{money(row["Initial Investment"])}</td>
                  <td>{money(row["Current Value"])}</td>
                  <td className={row.Return >= 0 ? "positive-text" : "negative-text"}>{pct(row.Return)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
