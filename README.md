# 📦 SupplyChain Risk & Inventory Dashboard

A Streamlit dashboard that analyzes synthetic inventory, supplier, and order data to identify supply-chain risk and recommend actions for a supply-chain manager.

## Overview

This project simulates the kind of analysis a supply-chain or product analyst might build to answer: *which products are at risk of stockout, which suppliers are underperforming, and what should we do about it?* It uses a reproducible synthetic dataset (no external APIs or database), a transparent rule-based risk-scoring model, and an interactive Streamlit dashboard with filterable charts and a dynamically generated set of recommendations. It was built as a scoped portfolio project, not a production system.

## Business Problem

Supply-chain teams need a fast way to answer three questions:

1. **Which products are most at risk of stockout**, and how urgent is the risk?
2. **Which suppliers are underperforming** on delivery reliability or quality?
3. **What should a manager actually do** about it — replenish, review a supplier, or cut back on excess stock?

This dashboard turns raw inventory, supplier, and order data into those answers.

## Key Features

- **Executive Overview** — headline KPIs and an at-a-glance supply chain health indicator
- **Inventory Risk** — highest-risk products, stock vs. reorder point, inventory value by category, risk distribution, with sidebar filters (category, warehouse, risk level)
- **Supplier Performance** — on-time rate, defect rate, lead time, and a supplier risk classification
- **Demand / Orders** — order volume over time, order quantity by category, average delivery time
- **Action Center** — recommendations generated dynamically from the data (not hard-coded), covering replenishment, supplier review, inventory reduction, and sourcing strategy

## Tech Stack

- Python 3
- Streamlit — dashboard UI
- Pandas / NumPy — data processing and scoring
- Plotly — interactive charts
- CSV files — no database, no external APIs

## Project Structure

```
supplychain-risk-dashboard/
│
├── app.py                 # Streamlit dashboard (UI + charts)
├── generate_data.py        # Generates the synthetic dataset
├── analysis.py              # Reusable KPI, risk-scoring, and recommendation logic
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   ├── products.csv
│   ├── inventory.csv
│   ├── suppliers.csv
│   └── orders.csv
│
└── screenshots/
    ├── dashboard.png
    ├── inventory-risk.png
    └── supplier-analysis.png
```

## How the Analysis Works

1. `generate_data.py` creates four related CSVs (products, suppliers, inventory, orders) with a fixed random seed (`42`) so the dataset is reproducible. Deliberate patterns are injected — some products pushed below safety stock, some pushed into excess inventory, a couple of suppliers made deliberately unreliable — so the risk logic has realistic signal to work with.
2. `analysis.py` loads the CSVs, joins them into a single product-level table, and calculates:
   - A **stockout risk score** per product
   - A **supplier risk score** per supplier
   - Headline **KPIs**
   - A list of **dynamically generated recommendations**
3. `app.py` loads this analysis into a filterable, multi-section Streamlit dashboard.

## KPI Definitions

| KPI | Definition |
|---|---|
| Total Inventory Value | Sum of `current_stock × unit_cost` across all products |
| Total SKUs | Count of unique products |
| Stockout Risk Count | Number of products classified as HIGH RISK |
| Avg. Supplier On-Time Rate | Mean `on_time_rate` across all suppliers |
| Avg. Supplier Lead Time | Mean `lead_time_days` across all suppliers |
| Avg. Order Delivery Time | Mean `delivery_days` across all non-cancelled orders |
| Supplier Defect Rate | Mean `defect_rate` across all suppliers |

## Risk Methodology

**This is a simple, transparent scoring model built for this project — it is not an industry-standard formula.** It's designed so every score can be explained and sanity-checked by hand.

**Product stockout risk score (0–100):**
- 40% — how far current stock is below the reorder point (normalized 0–1)
- 40% — how far current stock is below safety stock (normalized 0–1)
- 20% — relative demand percentile (higher demand = higher risk)

Products are then classified as **LOW RISK** (0–30), **MEDIUM RISK** (30–60), or **HIGH RISK** (60–100).

**Supplier risk score (0–100):**
- 50% — 1 minus on-time delivery rate
- 30% — defect rate (normalized against the highest defect rate in the dataset)
- 20% — lead time (normalized against the longest lead time in the dataset)

Suppliers are classified the same way: **LOW / MEDIUM / HIGH RISK**.

## How to Run Locally

```bash
# 1. Clone the repo and move into it
git clone <your-repo-url>
cd supplychain-risk-dashboard

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate the synthetic dataset
python generate_data.py

# 4. Launch the dashboard
streamlit run app.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`.

## Screenshots

*(Add screenshots to the `screenshots/` folder and reference them here.)*

| Executive Overview | Inventory Risk | Supplier Performance |
|---|---|---|
| ![Dashboard](screenshots/dashboard.png) | ![Inventory Risk](screenshots/inventory-risk.png) | ![Supplier Analysis](screenshots/supplier-analysis.png) |

## Example Business Insights

*(Actual numbers will vary slightly depending on when the dataset is generated, since it draws from a fixed seed but the seed date affects the order date range.)*

- A small subset of products (typically ~5–10% of SKUs) are consistently flagged HIGH RISK because they sit below both reorder point and safety stock.
- Two suppliers are deliberately modeled as underperforming (on-time rate below 65%, defect rate above 6%), and the dashboard's supplier risk logic correctly surfaces them as HIGH RISK.
- Several products carry excess inventory relative to demand, representing working capital that could be redeployed.

## Limitations

- **All data is synthetic**, generated by `generate_data.py` for demonstration purposes only. It does not represent any real company, supplier, or product.
- The risk-scoring formulas are intentionally simple and transparent, not validated against real-world outcomes or industry benchmarks.
- Demand is approximated using historical order quantities; there is no forecasting model.
- No database, authentication, or deployment layer — this is a local, single-user analytical tool.

## Future Improvements

- Add basic demand forecasting (e.g., moving average or exponential smoothing) to better anticipate stockouts
- Support uploading a user's own CSVs instead of only the synthetic dataset
- Add a supplier scorecard export (PDF/CSV) for sharing with stakeholders
- Track risk scores over time to show trend direction, not just a snapshot
