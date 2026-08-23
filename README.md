# Pump Short Scanner

A specialized cryptocurrency scanner designed to detect heavily pumped crypto assets that meet rigorous market capitalization, fully diluted valuation (FDV), and price-multiple thresholds for short-side research.

> **Status**: 🧪 **Manual Forward-Testing Phase** (Validation in progress).

---

## 🎯 Purpose & Strategy Overview

The primary objective of `pump-short-scanner` is to scan the crypto market for extreme parabolic pump events where high valuations and stretched price multiples create high-probability mean-reversion short opportunities.

### The 4 Core Filter Criteria (`config.py`):
1. **Min Market Cap**: $\ge \$500,000,000$ (Ensures sufficient liquidity).
2. **Min Fully Diluted Valuation (FDV)**: $\ge \$1,000,000,000$.
3. **ATH Multiple Threshold**: $\ge 10\times$ multiple from base/ATL (OR)
4. **30-Day Multiple Threshold**: $\ge 5\times$ multiple (+400% gain) over the last 30 days.

---

## 🧪 Current Focus: Manual Forward-Testing (`data/oi_funding_manual_log.csv`)

Before building automated derivatives ingestion, alert bots, or exchange execution connectors, we are conducting a **manual forward-test** to validate whether Open Interest (OI) and funding rate metrics reliably lead or diverge before a price top forms:

1. Run `python main.py` to identify coins meeting the 4-criteria filter and top 30-day gainers.
2. Select 2–3 active candidates.
3. Manually record daily price, Open Interest, and funding rates in [`data/oi_funding_manual_log.csv`](file:///c:/Users/HP/Desktop/pump-short-scanner/data/oi_funding_manual_log.csv).
4. Track whether OI/funding divergences precede tops in real-time.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- `pip`

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/dhanrajgupta2736/pump-short-scanner.git
   cd pump-short-scanner
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Scanner
Execute the scanner to pull real-time CoinGecko market data across the **Top 1000 coins by market cap** and evaluate the 4-criteria filter:
```bash
python main.py
```

---

## 📊 Current Status & Roadmap
- [x] Initial repository setup & Git workflow
- [x] CoinGecko free public API client with Top 1000 pagination
- [x] 4-criteria filtering engine
- [x] Manual forward-testing log template (`data/oi_funding_manual_log.csv`)
- [ ] Manual forward-test validation (1–2 weeks of daily OI/funding observations)
- [ ] Post-validation evaluation (automated OI/funding & alert bot design if validated)
