# Pump Short Scanner

A specialized cryptocurrency scanner designed to detect heavily pumped crypto assets that meet rigorous market capitalization, fully diluted valuation (FDV), and price-multiple thresholds for short-side research.

> **Status**: 🧪 **Forward-Testing Phase** (Active tracking and validation in progress).

---

## 🎯 Purpose & Strategy Overview

The primary objective of `pump-short-scanner` is to scan the crypto market for extreme parabolic pump events where high valuations and stretched price multiples create high-probability mean-reversion short opportunities.

### The 4 Core Filter Criteria (`config.py`):
1. **Min Market Cap**: $\ge \$500,000,000$ (Ensures sufficient liquidity).
2. **Min Fully Diluted Valuation (FDV)**: $\ge \$1,000,000,000$.
3. **ATH Multiple Threshold**: $\ge 10\times$ multiple from base/ATL with active ATH proximity (OR)
4. **30-Day Multiple Threshold**: $\ge 5\times$ multiple (+400% gain) over the last 30 days.

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

---

## 🖥️ Running the Tools

### 1. Market Scanner (`main.py`)
Fetches real-time CoinGecko market data across the **Top 1000 coins by market cap** to evaluate the 4-criteria filter and surface liquid 30-day gainers:
```bash
python main.py
```

### 2. Automated Forward-Test Logger (`scanner/auto_logger.py`)
Fetches live **Price**, **Open Interest (OI)**, and **Funding Rate** directly from Binance USDT-M Perpetual Futures public endpoints (no API key required) for candidate coins and appends a snapshot row to `data/oi_funding_manual_log.csv`:
```bash
python scanner/auto_logger.py
```

> [!NOTE]
> **Data Retention Limitation**: Binance's free public Open Interest history endpoint only retains 30 days of data. The auto-logger records **current live values** on each run going forward and cannot backfill older historical OI.

---

## 📁 Forward-Test Log Structure (`data/oi_funding_manual_log.csv`)

| Column | Description |
| :--- | :--- |
| `date` | UTC timestamp of the snapshot (`YYYY-MM-DDTHH:MM:SSZ`) |
| `coin` | Asset symbol (e.g. `BTW`, `BOME`, `DOGE`) |
| `price` | Current market price in USD |
| `open_interest` | Total Open Interest in contract units |
| `funding_rate` | Current 8h funding rate (e.g. `0.0001` = $+0.01\%$) |
| `notes` | `"auto"` for script logs, or custom notes for manual entries |

---

## 📊 Current Status & Roadmap
- [x] Initial repository setup & Git workflow
- [x] CoinGecko free public API client with Top 1000 pagination
- [x] 4-criteria filtering engine with active ATH gating
- [x] Tradeable volume floor on Top 30-Day Gainers ($1M USD)
- [x] Automated daily forward-test logger for Binance Futures (`scanner/auto_logger.py`)
- [ ] Forward-test data collection (daily snapshots over 1–2 weeks)
- [ ] Post-validation evaluation (automated alert bot design if validated)
