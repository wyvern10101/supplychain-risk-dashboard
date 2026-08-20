"""
analysis.py

Reusable, transparent analysis functions for the SupplyChain Risk &
Inventory Dashboard.

Nothing in this file is machine learning -- everything is simple,
explainable arithmetic on top of pandas DataFrames, on purpose. The goal
is a scoring model a supply-chain manager could sanity-check by hand.
"""

import os
import pandas as pd
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# ---------------------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------------------
def load_data(data_dir: str = DATA_DIR):
    """Load all four source CSVs and return them as a dict of DataFrames."""
    products = pd.read_csv(os.path.join(data_dir, "products.csv"))
    suppliers = pd.read_csv(os.path.join(data_dir, "suppliers.csv"))
    inventory = pd.read_csv(os.path.join(data_dir, "inventory.csv"))
    orders = pd.read_csv(os.path.join(data_dir, "orders.csv"))
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    return {
        "products": products,
        "suppliers": suppliers,
        "inventory": inventory,
        "orders": orders,
    }


def build_master_table(data: dict) -> pd.DataFrame:
    """
    Join products + inventory + suppliers + per-product demand into a single
    "master" table that most of the dashboard reads from.
    """
    products = data["products"]
    inventory = data["inventory"]
    suppliers = data["suppliers"]
    orders = data["orders"]

    demand = (
        orders[orders["status"] != "Cancelled"]
        .groupby("product_id")["quantity"]
        .sum()
        .rename("total_demand")
        .reset_index()
    )

    df = products.merge(inventory, on="product_id", how="left")
    df = df.merge(suppliers, on="supplier_id", how="left")
    df = df.merge(demand, on="product_id", how="left")
    df["total_demand"] = df["total_demand"].fillna(0)

    return df


# ---------------------------------------------------------------------------
# STOCKOUT RISK SCORE (products)
# ---------------------------------------------------------------------------
def calculate_stockout_risk(master_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a `stockout_risk_score` (0-100) and `risk_level` column to the
    master product table.

    This is a simple, transparent weighted formula for portfolio purposes.
    It is NOT an industry-standard model -- just a clear, explainable way
    to combine three signals:

        1. How far current stock is below the reorder point (40%)
        2. How far current stock is below safety stock          (40%)
        3. How high demand is relative to other products        (20%)

    Each component is normalized to a 0-1 scale before weighting so that no
    single input dominates just because of its raw units.
    """
    df = master_df.copy()

    # Component 1: below reorder point (0 if at/above, scaled 0-1 if below)
    below_reorder = (df["reorder_point"] - df["current_stock"]).clip(lower=0)
    max_below_reorder = below_reorder.max() if below_reorder.max() > 0 else 1
    reorder_component = below_reorder / max_below_reorder

    # Component 2: below safety stock (0 if at/above, scaled 0-1 if below)
    below_safety = (df["safety_stock"] - df["current_stock"]).clip(lower=0)
    max_below_safety = below_safety.max() if below_safety.max() > 0 else 1
    safety_component = below_safety / max_below_safety

    # Component 3: relative demand (percentile rank, 0-1)
    demand_component = df["total_demand"].rank(pct=True)

    df["stockout_risk_score"] = (
        0.4 * reorder_component + 0.4 * safety_component + 0.2 * demand_component
    ) * 100
    df["stockout_risk_score"] = df["stockout_risk_score"].round(1)

    df["risk_level"] = pd.cut(
        df["stockout_risk_score"],
        bins=[-0.01, 30, 60, 100],
        labels=["LOW RISK", "MEDIUM RISK", "HIGH RISK"],
    )

    return df


# ---------------------------------------------------------------------------
# SUPPLIER RISK SCORE
# ---------------------------------------------------------------------------
def calculate_supplier_risk(suppliers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a `supplier_risk_score` (0-100) and `supplier_risk_level` column.

    Simple weighted formula combining:
        1. On-time delivery rate (lower on-time = higher risk)   50%
        2. Defect rate (higher defect rate = higher risk)        30%
        3. Lead time (longer lead time = higher risk)            20%

    As with the product score, this is a transparent, explainable
    scoring approach built for this project -- not an industry standard.
    """
    df = suppliers_df.copy()

    late_component = 1 - df["on_time_rate"]  # already 0-1

    max_defect = df["defect_rate"].max() if df["defect_rate"].max() > 0 else 1
    defect_component = df["defect_rate"] / max_defect

    max_lead = df["lead_time_days"].max() if df["lead_time_days"].max() > 0 else 1
    lead_component = df["lead_time_days"] / max_lead

    df["supplier_risk_score"] = (
        0.5 * late_component + 0.3 * defect_component + 0.2 * lead_component
    ) * 100
    df["supplier_risk_score"] = df["supplier_risk_score"].round(1)

    df["supplier_risk_level"] = pd.cut(
        df["supplier_risk_score"],
        bins=[-0.01, 30, 60, 100],
        labels=["LOW RISK", "MEDIUM RISK", "HIGH RISK"],
    )

    return df


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
def calculate_kpis(master_df: pd.DataFrame, suppliers_df: pd.DataFrame, orders_df: pd.DataFrame) -> dict:
    """Return a dict of headline KPIs used in the Executive Overview."""
    valid_orders = orders_df[orders_df["status"] != "Cancelled"]

    kpis = {
        "total_inventory_value": master_df["inventory_value"].sum(),
        "total_skus": master_df["product_id"].nunique(),
        "stockout_risk_count": int((master_df["risk_level"] == "HIGH RISK").sum()),
        "avg_supplier_on_time_rate": suppliers_df["on_time_rate"].mean(),
        "avg_supplier_lead_time": suppliers_df["lead_time_days"].mean(),
        "avg_order_delivery_days": valid_orders["delivery_days"].mean(),
        "avg_supplier_defect_rate": suppliers_df["defect_rate"].mean(),
    }
    return kpis


# ---------------------------------------------------------------------------
# RECOMMENDATIONS (Action Center)
# ---------------------------------------------------------------------------
def generate_recommendations(master_df: pd.DataFrame, suppliers_df: pd.DataFrame) -> list:
    """
    Dynamically generate plain-English recommendations from the calculated
    data. Nothing here is hard-coded to a specific product or supplier name
    -- every recommendation is triggered by a data condition.
    """
    recs = []

    # 1. Products below safety stock -> immediate replenishment
    below_safety = master_df[master_df["current_stock"] < master_df["safety_stock"]]
    for _, row in below_safety.sort_values("stockout_risk_score", ascending=False).head(10).iterrows():
        recs.append({
            "type": "Replenishment",
            "priority": "HIGH",
            "message": (
                f"{row['product_name']} ({row['product_id']}) is below safety stock "
                f"({int(row['current_stock'])} on hand vs {int(row['safety_stock'])} safety stock). "
                f"Recommend immediate replenishment."
            ),
        })

    # 2. Suppliers with low on-time rate AND high defect rate -> supplier review
    risky_suppliers = suppliers_df[
        (suppliers_df["on_time_rate"] < 0.75) & (suppliers_df["defect_rate"] > 0.05)
    ]
    for _, row in risky_suppliers.iterrows():
        recs.append({
            "type": "Supplier Review",
            "priority": "HIGH",
            "message": (
                f"{row['supplier_name']} ({row['supplier_id']}) has a low on-time rate "
                f"({row['on_time_rate']:.0%}) and a high defect rate ({row['defect_rate']:.1%}). "
                f"Recommend a formal supplier performance review."
            ),
        })

    # 3. High inventory but low demand -> reduce inventory
    demand_median = master_df["total_demand"].median()
    excess = master_df[
        (master_df["current_stock"] > master_df["reorder_point"] * 2.5)
        & (master_df["total_demand"] <= demand_median)
    ]
    for _, row in excess.sort_values("inventory_value", ascending=False).head(10).iterrows():
        recs.append({
            "type": "Inventory Reduction",
            "priority": "MEDIUM",
            "message": (
                f"{row['product_name']} ({row['product_id']}) is carrying "
                f"{int(row['current_stock'])} units against low relative demand "
                f"(tying up ${row['inventory_value']:,.0f} in inventory value). "
                f"Recommend reducing future order quantities."
            ),
        })

    # 4. Suppliers with long lead times -> consider dual sourcing
    slow_suppliers = suppliers_df[suppliers_df["lead_time_days"] > suppliers_df["lead_time_days"].quantile(0.85)]
    for _, row in slow_suppliers.iterrows():
        recs.append({
            "type": "Sourcing Strategy",
            "priority": "MEDIUM",
            "message": (
                f"{row['supplier_name']} ({row['supplier_id']}) has a long average lead time "
                f"({int(row['lead_time_days'])} days), which is in the slowest 15% of suppliers. "
                f"Recommend evaluating a backup supplier for products sourced here."
            ),
        })

    return recs
