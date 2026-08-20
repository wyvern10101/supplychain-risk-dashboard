"""
generate_data.py

Generates realistic, reproducible synthetic data for the SupplyChain Risk &
Inventory Dashboard project.

Creates four CSV files inside the data/ folder:
    - products.csv
    - suppliers.csv
    - inventory.csv
    - orders.csv

Run with:
    python generate_data.py
"""

import numpy as np
import pandas as pd
import os

# Fixed seed so the dataset is reproducible every time this script runs.
SEED = 42
rng = np.random.default_rng(SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

N_PRODUCTS = 50
N_SUPPLIERS = 10
N_ORDERS = 2000

CATEGORIES = [
    "Electronics", "Packaging", "Raw Materials", "Hardware",
    "Textiles", "Chemicals", "Automotive Parts"
]

WAREHOUSES = ["North DC", "South DC", "East DC", "West DC"]


# ---------------------------------------------------------------------------
# SUPPLIERS
# ---------------------------------------------------------------------------
def generate_suppliers():
    supplier_ids = [f"SUP-{i+1:03d}" for i in range(N_SUPPLIERS)]
    supplier_names = [f"Supplier {chr(65 + i)}" for i in range(N_SUPPLIERS)]

    # Deliberately create a spread of good, average, and poor-performing
    # suppliers so the risk logic has something meaningful to surface.
    lead_time_days = rng.integers(3, 30, size=N_SUPPLIERS)

    # Most suppliers perform reasonably; a few are made deliberately poor.
    on_time_rate = np.clip(rng.normal(0.90, 0.08, size=N_SUPPLIERS), 0.45, 0.99)
    defect_rate = np.clip(rng.normal(0.02, 0.015, size=N_SUPPLIERS), 0.001, 0.12)

    # Force at least 2 suppliers to be clearly poor performers (for realism
    # and so the dashboard always has something in the "high risk" bucket).
    poor_idx = rng.choice(N_SUPPLIERS, size=2, replace=False)
    on_time_rate[poor_idx] = rng.uniform(0.45, 0.65, size=2)
    defect_rate[poor_idx] = rng.uniform(0.06, 0.12, size=2)
    lead_time_days[poor_idx] = rng.integers(20, 35, size=2)

    df = pd.DataFrame({
        "supplier_id": supplier_ids,
        "supplier_name": supplier_names,
        "lead_time_days": lead_time_days,
        "defect_rate": np.round(defect_rate, 4),
        "on_time_rate": np.round(on_time_rate, 4),
    })
    return df


# ---------------------------------------------------------------------------
# PRODUCTS
# ---------------------------------------------------------------------------
def generate_products(suppliers_df):
    product_ids = [f"PRD-{i+1:04d}" for i in range(N_PRODUCTS)]
    categories = rng.choice(CATEGORIES, size=N_PRODUCTS)
    unit_cost = np.round(rng.uniform(2, 500, size=N_PRODUCTS), 2)

    # Assign each product to a random supplier.
    supplier_ids = rng.choice(suppliers_df["supplier_id"], size=N_PRODUCTS)

    product_names = [
        f"{cat.split()[0]} Item {i+1:03d}"
        for i, cat in enumerate(categories)
    ]

    df = pd.DataFrame({
        "product_id": product_ids,
        "product_name": product_names,
        "category": categories,
        "unit_cost": unit_cost,
        "supplier_id": supplier_ids,
    })
    return df


# ---------------------------------------------------------------------------
# INVENTORY
# ---------------------------------------------------------------------------
def generate_inventory(products_df):
    n = len(products_df)

    reorder_point = rng.integers(20, 200, size=n)
    safety_stock = np.round(reorder_point * rng.uniform(0.3, 0.6, size=n)).astype(int)

    # Baseline stock is somewhat correlated with reorder point (bigger
    # products tend to be stocked in bigger quantities), then we inject
    # deliberate patterns on top of that baseline.
    current_stock = np.round(reorder_point * rng.uniform(0.5, 2.5, size=n)).astype(int)

    # Deliberately push ~15% of products into a low-stock / stockout-risk
    # situation (below safety stock).
    low_stock_idx = rng.choice(n, size=max(1, int(n * 0.15)), replace=False)
    current_stock[low_stock_idx] = np.round(
        safety_stock[low_stock_idx] * rng.uniform(0.1, 0.8, size=len(low_stock_idx))
    ).astype(int)

    # Deliberately push ~15% of products into excess inventory (well above
    # reorder point) to support "reduce inventory" recommendations.
    remaining = np.setdiff1d(np.arange(n), low_stock_idx)
    excess_idx = rng.choice(remaining, size=max(1, int(n * 0.15)), replace=False)
    current_stock[excess_idx] = np.round(
        reorder_point[excess_idx] * rng.uniform(3, 6, size=len(excess_idx))
    ).astype(int)

    current_stock = np.clip(current_stock, 0, None)

    warehouse = rng.choice(WAREHOUSES, size=n)

    inventory_value = np.round(current_stock * products_df["unit_cost"].values, 2)

    df = pd.DataFrame({
        "product_id": products_df["product_id"],
        "current_stock": current_stock,
        "reorder_point": reorder_point,
        "safety_stock": safety_stock,
        "warehouse": warehouse,
        "inventory_value": inventory_value,
    })
    return df


# ---------------------------------------------------------------------------
# ORDERS
# ---------------------------------------------------------------------------
def generate_orders(products_df, suppliers_df):
    n = N_ORDERS

    order_ids = [f"ORD-{i+1:06d}" for i in range(n)]

    # Orders spread over the last 12 months.
    start_date = pd.Timestamp.today().normalize() - pd.Timedelta(days=365)
    order_dates = start_date + pd.to_timedelta(rng.integers(0, 365, size=n), unit="D")

    # Give some products deliberately higher demand (more frequent orders)
    # by weighting the random choice of product per order.
    product_ids_all = products_df["product_id"].values
    weights = rng.gamma(shape=2.0, scale=1.0, size=len(product_ids_all))
    weights = weights / weights.sum()
    chosen_products = rng.choice(product_ids_all, size=n, p=weights)

    quantity = rng.integers(1, 250, size=n)

    # Map each order's product back to its supplier so delivery performance
    # can be linked realistically to that supplier's characteristics.
    product_to_supplier = dict(zip(products_df["product_id"], products_df["supplier_id"]))
    supplier_lookup = suppliers_df.set_index("supplier_id")

    order_supplier_ids = [product_to_supplier[p] for p in chosen_products]
    base_lead_times = supplier_lookup.loc[order_supplier_ids, "lead_time_days"].values
    on_time_rates = supplier_lookup.loc[order_supplier_ids, "on_time_rate"].values

    # Delivery days = supplier's base lead time +/- noise. Late suppliers
    # (low on_time_rate) get a wider, right-skewed delay distribution.
    noise = rng.normal(0, 2, size=n)
    late_penalty = (1 - on_time_rates) * rng.uniform(2, 10, size=n)
    delivery_days = np.round(base_lead_times + noise + late_penalty).astype(int)
    delivery_days = np.clip(delivery_days, 1, None)

    # Status: on-time if delivery_days <= supplier's lead time (+1 day grace),
    # otherwise late. A small fraction are cancelled at random.
    is_late = delivery_days > (base_lead_times + 1)
    status = np.where(is_late, "Late", "On Time")
    cancel_mask = rng.random(n) < 0.03
    status = np.where(cancel_mask, "Cancelled", status)

    df = pd.DataFrame({
        "order_id": order_ids,
        "order_date": order_dates.strftime("%Y-%m-%d"),
        "product_id": chosen_products,
        "quantity": quantity,
        "delivery_days": delivery_days,
        "status": status,
    })
    return df


def main():
    print("Generating synthetic supply chain dataset...")

    suppliers_df = generate_suppliers()
    products_df = generate_products(suppliers_df)
    inventory_df = generate_inventory(products_df)
    orders_df = generate_orders(products_df, suppliers_df)

    suppliers_df.to_csv(os.path.join(OUTPUT_DIR, "suppliers.csv"), index=False)
    products_df.to_csv(os.path.join(OUTPUT_DIR, "products.csv"), index=False)
    inventory_df.to_csv(os.path.join(OUTPUT_DIR, "inventory.csv"), index=False)
    orders_df.to_csv(os.path.join(OUTPUT_DIR, "orders.csv"), index=False)

    print(f"Done. Files written to: {OUTPUT_DIR}")
    print(f"  suppliers.csv  -> {len(suppliers_df)} rows")
    print(f"  products.csv   -> {len(products_df)} rows")
    print(f"  inventory.csv  -> {len(inventory_df)} rows")
    print(f"  orders.csv     -> {len(orders_df)} rows")


if __name__ == "__main__":
    main()
