"""
app.py

SupplyChain Risk & Inventory Dashboard
A Streamlit dashboard that analyzes synthetic inventory, supplier, and
order data to answer:

    "Which products are most at risk of stockout, which suppliers are
    underperforming, and what actions should a supply-chain manager take?"

Run with:
    streamlit run app.py
"""

import time

import streamlit as st
import pandas as pd
import plotly.express as px

from prometheus_client import Counter, Gauge, Histogram, start_http_server

from analysis import (
    load_data,
    build_master_table,
    calculate_stockout_risk,
    calculate_supplier_risk,
    calculate_kpis,
    generate_recommendations,
)


# ---------------------------------------------------------------------------
# PROMETHEUS MONITORING METRICS
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "supplychain_requests_total",
    "Total number of dashboard requests"
)

ERROR_COUNT = Counter(
    "supplychain_errors_total",
    "Total number of dashboard errors"
)

REQUEST_LATENCY = Histogram(
    "supplychain_request_latency_seconds",
    "Dashboard request processing latency in seconds"
)

APP_UP = Gauge(
    "supplychain_app_up",
    "SupplyChain dashboard application availability"
)

# Start Prometheus metrics server on port 8000.
# Streamlit reruns the script frequently, so ignore the error if
# the metrics server is already running.
try:
    start_http_server(8000)
except OSError:
    pass

APP_UP.set(1)
REQUEST_COUNT.inc()

request_start_time = time.perf_counter()


# ---------------------------------------------------------------------------
# STREAMLIT CONFIGURATION
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SupplyChain Risk & Inventory Dashboard",
    page_icon="📦",
    layout="wide",
)

RISK_COLORS = {
    "HIGH RISK": "#E74C3C",
    "MEDIUM RISK": "#F39C12",
    "LOW RISK": "#27AE60",
}


# ---------------------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------------------

@st.cache_data
def get_data():
    data = load_data()
    master = build_master_table(data)
    master = calculate_stockout_risk(master)
    suppliers = calculate_supplier_risk(data["suppliers"])
    orders = data["orders"]
    return master, suppliers, orders


try:
    master_df, suppliers_df, orders_df = get_data()

except FileNotFoundError:
    ERROR_COUNT.inc()

    APP_UP.set(0)

    st.error(
        "Data files not found. Please run `python generate_data.py` first "
        "to create the CSV files in the `data/` folder."
    )

    st.stop()


# ---------------------------------------------------------------------------
# KPI CALCULATIONS
# ---------------------------------------------------------------------------

kpis = calculate_kpis(
    master_df,
    suppliers_df,
    orders_df
)

recommendations = generate_recommendations(
    master_df,
    suppliers_df
)


# ---------------------------------------------------------------------------
# DASHBOARD HEADER
# ---------------------------------------------------------------------------

st.title("Supply Chain Risk Dashboard - v1.1")

st.caption(
    "Synthetic data project analyzing inventory and supplier risk to support "
    "supply-chain decision-making. All data is randomly generated for "
    "portfolio/demo purposes."
)


# ---------------------------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------------------------

st.sidebar.header("Filters")

categories = sorted(
    master_df["category"].dropna().unique()
)

warehouses = sorted(
    master_df["warehouse"].dropna().unique()
)

risk_levels = [
    "HIGH RISK",
    "MEDIUM RISK",
    "LOW RISK"
]

selected_categories = st.sidebar.multiselect(
    "Category",
    categories,
    default=categories
)

selected_warehouses = st.sidebar.multiselect(
    "Warehouse",
    warehouses,
    default=warehouses
)

selected_risk_levels = st.sidebar.multiselect(
    "Risk Level",
    risk_levels,
    default=risk_levels
)

filtered_df = master_df[
    master_df["category"].isin(selected_categories)
    & master_df["warehouse"].isin(selected_warehouses)
    & master_df["risk_level"].isin(selected_risk_levels)
]

st.sidebar.markdown("---")

st.sidebar.caption(
    f"Showing {len(filtered_df)} of {len(master_df)} products"
)


# ---------------------------------------------------------------------------
# 1. EXECUTIVE OVERVIEW
# ---------------------------------------------------------------------------

st.header("1. Executive Overview")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Total Inventory Value",
    f"${kpis['total_inventory_value']:,.0f}"
)

col2.metric(
    "Total SKUs",
    f"{kpis['total_skus']}"
)

col3.metric(
    "High-Risk SKUs",
    f"{kpis['stockout_risk_count']}"
)

col4.metric(
    "Avg. Supplier On-Time Rate",
    f"{kpis['avg_supplier_on_time_rate']:.1%}"
)

high_risk_pct = (
    kpis["stockout_risk_count"] / kpis["total_skus"]
    if kpis["total_skus"]
    else 0
)

if (
    high_risk_pct > 0.20
    or kpis["avg_supplier_on_time_rate"] < 0.75
):
    health = "🔴 Needs Attention"

elif (
    high_risk_pct > 0.10
    or kpis["avg_supplier_on_time_rate"] < 0.85
):
    health = "🟠 Fair"

else:
    health = "🟢 Healthy"

st.subheader(
    f"Supply Chain Health: {health}"
)

st.caption(
    f"{high_risk_pct:.0%} of SKUs are High Risk and average supplier "
    f"on-time delivery is {kpis['avg_supplier_on_time_rate']:.1%}."
)

st.markdown("---")


# ---------------------------------------------------------------------------
# 2. INVENTORY RISK
# ---------------------------------------------------------------------------

st.header("2. Inventory Risk")

col_a, col_b = st.columns([2, 1])

with col_a:

    st.subheader("Highest-Risk Products")

    top_risk = (
        filtered_df
        .sort_values(
            "stockout_risk_score",
            ascending=False
        )
        .head(15)
    )

    st.dataframe(
        top_risk[
            [
                "product_id",
                "product_name",
                "category",
                "current_stock",
                "reorder_point",
                "safety_stock",
                "stockout_risk_score",
                "risk_level",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


with col_b:

    st.subheader("Risk Distribution")

    risk_counts = (
        filtered_df["risk_level"]
        .value_counts()
        .reindex(risk_levels)
        .fillna(0)
    )

    fig_risk_dist = px.pie(
        names=risk_counts.index,
        values=risk_counts.values,
        color=risk_counts.index,
        color_discrete_map=RISK_COLORS,
        hole=0.4,
    )

    st.plotly_chart(
        fig_risk_dist,
        use_container_width=True
    )


col_c, col_d = st.columns(2)


with col_c:

    st.subheader("Stock vs. Reorder Point")

    chart_df = (
        filtered_df
        .sort_values(
            "stockout_risk_score",
            ascending=False
        )
        .head(20)
    )

    fig_stock = px.bar(
        chart_df,
        x="product_id",
        y=[
            "current_stock",
            "reorder_point"
        ],
        barmode="group",
        labels={
            "value": "Units",
            "product_id": "Product",
            "variable": "Metric",
        },
        title="Top 20 Highest-Risk Products: Stock vs. Reorder Point",
    )

    st.plotly_chart(
        fig_stock,
        use_container_width=True
    )


with col_d:

    st.subheader("Inventory Value by Category")

    value_by_cat = (
        filtered_df
        .groupby("category")["inventory_value"]
        .sum()
        .reset_index()
    )

    fig_value = px.bar(
        value_by_cat.sort_values(
            "inventory_value",
            ascending=False
        ),
        x="category",
        y="inventory_value",
        labels={
            "inventory_value": "Inventory Value ($)",
            "category": "Category",
        },
        title="Inventory Value by Category",
    )

    st.plotly_chart(
        fig_value,
        use_container_width=True
    )


st.markdown("---")


# ---------------------------------------------------------------------------
# 3. SUPPLIER PERFORMANCE
# ---------------------------------------------------------------------------

st.header("3. Supplier Performance")

col_e, col_f = st.columns(2)


with col_e:

    st.subheader("On-Time Rate by Supplier")

    fig_ontime = px.bar(
        suppliers_df.sort_values("on_time_rate"),
        x="supplier_name",
        y="on_time_rate",
        color="supplier_risk_level",
        color_discrete_map=RISK_COLORS,
        labels={
            "on_time_rate": "On-Time Rate",
            "supplier_name": "Supplier",
        },
    )

    fig_ontime.update_yaxes(
        tickformat=".0%"
    )

    st.plotly_chart(
        fig_ontime,
        use_container_width=True
    )


with col_f:

    st.subheader("Defect Rate by Supplier")

    fig_defect = px.bar(
        suppliers_df.sort_values(
            "defect_rate",
            ascending=False
        ),
        x="supplier_name",
        y="defect_rate",
        color="supplier_risk_level",
        color_discrete_map=RISK_COLORS,
        labels={
            "defect_rate": "Defect Rate",
            "supplier_name": "Supplier",
        },
    )

    fig_defect.update_yaxes(
        tickformat=".1%"
    )

    st.plotly_chart(
        fig_defect,
        use_container_width=True
    )


st.subheader(
    "Supplier Lead Time & Risk Classification"
)

st.dataframe(
    suppliers_df[
        [
            "supplier_id",
            "supplier_name",
            "lead_time_days",
            "on_time_rate",
            "defect_rate",
            "supplier_risk_score",
            "supplier_risk_level",
        ]
    ].sort_values(
        "supplier_risk_score",
        ascending=False
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown("---")


# ---------------------------------------------------------------------------
# 4. DEMAND / ORDERS
# ---------------------------------------------------------------------------

st.header("4. Demand / Orders")

col_g, col_h = st.columns(2)


with col_g:

    st.subheader("Orders Over Time")

    orders_by_month = (
        orders_df
        .assign(
            month=orders_df["order_date"]
            .dt
            .to_period("M")
            .astype(str)
        )
        .groupby("month")["quantity"]
        .sum()
        .reset_index()
    )

    fig_time = px.line(
        orders_by_month,
        x="month",
        y="quantity",
        labels={
            "quantity": "Total Units Ordered",
            "month": "Month",
        },
        markers=True,
    )

    st.plotly_chart(
        fig_time,
        use_container_width=True
    )


with col_h:

    st.subheader("Order Quantity by Category")

    orders_with_cat = orders_df.merge(
        master_df[
            [
                "product_id",
                "category"
            ]
        ],
        on="product_id",
        how="left",
    )

    qty_by_cat = (
        orders_with_cat
        .groupby("category")["quantity"]
        .sum()
        .reset_index()
    )

    fig_qty_cat = px.bar(
        qty_by_cat.sort_values(
            "quantity",
            ascending=False
        ),
        x="category",
        y="quantity",
        labels={
            "quantity": "Total Units Ordered",
            "category": "Category",
        },
    )

    st.plotly_chart(
        fig_qty_cat,
        use_container_width=True
    )


st.metric(
    "Average Order Delivery Time",
    f"{kpis['avg_order_delivery_days']:.1f} days"
)

st.markdown("---")


# ---------------------------------------------------------------------------
# 5. ACTION CENTER
# ---------------------------------------------------------------------------

st.header("5. Action Center")

st.caption(
    "Recommendations below are generated dynamically from the calculated "
    "risk scores and KPIs -- not hard-coded to any specific product or supplier."
)

if not recommendations:

    st.success(
        "No urgent actions detected based on current data."
    )

else:

    rec_df = pd.DataFrame(
        recommendations
    )

    priority_order = {
        "HIGH": 0,
        "MEDIUM": 1,
        "LOW": 2,
    }

    rec_df["_sort"] = (
        rec_df["priority"]
        .map(priority_order)
    )

    rec_df = (
        rec_df
        .sort_values("_sort")
        .drop(columns="_sort")
    )

    for rec_type in rec_df["type"].unique():

        st.subheader(rec_type)

        subset = rec_df[
            rec_df["type"] == rec_type
        ]

        for _, r in subset.iterrows():

            icon = (
                "🔴"
                if r["priority"] == "HIGH"
                else "🟠"
            )

            st.markdown(
                f"{icon} **[{r['priority']}]** {r['message']}"
            )


# ---------------------------------------------------------------------------
# FINAL DASHBOARD INFORMATION
# ---------------------------------------------------------------------------

st.markdown("---")

st.caption(
    "SupplyChain Risk & Inventory Dashboard — built with Streamlit, "
    "Pandas, NumPy, and Plotly. All data is synthetic and generated "
    "for demonstration purposes."
)


# ---------------------------------------------------------------------------
# RECORD APPLICATION LATENCY
# ---------------------------------------------------------------------------

request_latency = (
    time.perf_counter()
    - request_start_time
)

REQUEST_LATENCY.observe(
    request_latency
)