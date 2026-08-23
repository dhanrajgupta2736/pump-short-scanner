# Pump Short Scanner

A specialized cryptocurrency scanner designed to detect heavily pumped crypto assets that meet rigorous market capitalization, fully diluted valuation (FDV), and price-multiple thresholds for potential short-side research and trading strategies.

> **Status**: 🧪 **Manual / Experimental Testing Phase** (Not live-traded).

---

## 🎯 Purpose

The primary objective of `pump-short-scanner` is to filter the crypto universe for extreme pump events where high valuation and extended price multiples may offer asymmetric short opportunities. The scanner identifies assets that satisfy specific criteria:
1. **Market Cap Threshold**: Sufficient liquidity and size (e.g. $\ge \$500\text{M}$).
2. **FDV Threshold**: Significant fully diluted valuation (e.g. $\ge \$1\text{B}$).
3. **ATH Multiple Threshold**: Significant multiple from all-time highs / base prices (e.g. $\ge 10\times$).
4. **30-Day Multiple Threshold**: Rapid short-term expansion (e.g. $\ge 5\times$ over 30 days).

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- `pip`

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/<your-username>/pump-short-scanner.git
   cd pump-short-scanner
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Copy environment template:
   ```bash
   cp .env.example .env
   ```

### Running the Scanner
Execute the scanner entry point:
```bash
python main.py
```

---

## 📊 Current Status & Roadmap
- [x] Initial repository setup & Git workflow
- [x] CoinGecko free public API integration
- [x] 4-criteria filtering engine
- [ ] Expanded asset universe scanning
- [ ] Open Interest (OI) and Funding Rate tracking integration
- [ ] Telegram alert bot notifications
