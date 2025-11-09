
import os
from io import BytesIO
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

st.set_page_config(
    page_title="Daridorexant / Quviviq UK Dashboard",
    page_icon="💊",
    layout="wide",
)

# -------------------------
# Helpers & Data Loading
# -------------------------
@st.cache_data(show_spinner=False)
def load_csv(path, parse_dates=None):
    if not os.path.exists(path):
        st.warning(f"⚠️ Missing file: {path}")
        return None
    return pd.read_csv(path, parse_dates=parse_dates)

@st.cache_data(show_spinner=False)
def load_data():
    # Base directory for all data files
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

    # Candidate files for long format (try in order)
    candidates = [
        "Input_File_Long_Format_Data_With_Postcode.csv",
        "Input_File_Long_Format_Data.csv",
        "Input_File_Cleaned.csv"
    ]

    long_path = None
    for fname in candidates:
        test_path = os.path.join(base, fname)
        if os.path.exists(test_path):
            long_path = test_path
#            st.info(f"✅ Using {fname} as long-format dataset.")
            break

    if long_path is None:
        st.error("❌ No suitable data file found. Please ensure one of these exists:\n"
                 "Input_File_Long_Format_Data_With_Postcode.csv, Input_File_Long_Format_Data.csv, or Input_File_Cleaned.csv")
        st.stop()

    # Optional supporting files
    monthly_path = os.path.join(base, "monthly_summary.csv")
    forecast_summary_path = os.path.join(base, "forecast_summary.csv")
    geo_path = os.path.join(base, "Input_File_Postcode_Geo_With_Latlon.csv")

    data = {
        "long": load_csv(long_path, parse_dates=["Month"]),
        "monthly": load_csv(monthly_path, parse_dates=["Month"]),
        "forecast_summary": load_csv(forecast_summary_path, parse_dates=["Month"]),
        "geo": load_csv(geo_path)
    }
    return data

data = load_data()
df = data["long"].copy()
df["Month"] = pd.to_datetime(df["Month"], errors="coerce")
df = df.sort_values("Month")

# -------------------------
# Sidebar Controls
# -------------------------
with st.sidebar:
    st.title("💊 Filters")

    min_month = df["Month"].min()
    max_month = df["Month"].max()
    date_range = st.slider(
        "Month range",
        min_value=min_month.to_pydatetime(),
        max_value=max_month.to_pydatetime(),
        value=(min_month.to_pydatetime(), max_month.to_pydatetime()),
        format="MMM YYYY",
    )

    settings = sorted(df["Quviviq_Type"].dropna().unique().tolist())
    selected_settings = st.multiselect("Setting", settings, default=settings)

    doses = sorted(df["Product_Group"].dropna().unique().tolist())
    selected_doses = st.multiselect("Dose", doses, default=doses)

    brands = sorted(df.get("BNF_Name", pd.Series(["BNF_Name", "Generic"])).dropna().unique().tolist())
    selected_brands = st.multiselect("Brand vs Generic", brands, default=brands)
    
    regions = sorted(df["ICB_Name"].dropna().unique().tolist())
    selected_regions = st.multiselect("ICB (Region)", regions, default=regions)

# -------------------------
# Filtered Data
# -------------------------
mask = (
    (df["Month"] >= pd.to_datetime(date_range[0])) &
    (df["Month"] <= pd.to_datetime(date_range[1])) &
    (df["ICB_Name"].isin(selected_regions)) &
    (df["Quviviq_Type"].isin(selected_settings)) &
    (df["Product_Group"].isin(selected_doses)) &
    (df["BNF_Name"].isin(selected_brands))
)
fdf = df.loc[mask].copy()

# -------------------------
# Overview Header
# -------------------------
st.markdown("# Daridorexant / Quviviq Dashboard")
st.markdown(
    """
*Product overview:* Daridorexant (brand name **Quviviq**) is perscribed for insomnia (short term use when symptoms persist for at least 3 months). Available in **25mg** and **50mg** tablets. 
Each **pack of 30 tablets = 1 ITEM**. Price is **£42 per pack** in this dataset (no brand/generic price difference). 
"""
)

# -------------------------
# KPI Metrics
# -------------------------
kpi = fdf.groupby("Month")[["QTY", "NIC", "ITEMS"]].sum().reset_index()

col1, col2, col3 = st.columns(3)
col1.metric("Total Quantity (selected)", f"{int(kpi['QTY'].sum()):,}")
col2.metric("Total Cost (£, selected)", f"£{kpi['NIC'].sum():,.0f}")
col3.metric("Total Items (selected)", f"{int(kpi['ITEMS'].sum()):,}")

st.markdown("---")
# -------------------------
# 8) Geographic Heat Maps
st.markdown("### 🌍 Geographic Distribution of Usage")

geo = data.get("geo")
if geo is not None and not geo.empty:
    st.markdown("Select which map type to display:")
    map_type = st.radio(
        "Map Type",
        ["Animated Adoption Map (by Setting)", "Setting & Dose Scattermap", "NIC Heat Map (static)"],
        index=0,
        horizontal=True
    )

    # Ensure date format and sizes
    geo["Month"] = pd.to_datetime(geo["Month"], errors="coerce")
    geo["QTY_display"] = np.where(geo["QTY"] > 0, geo["QTY"], 0.1)
    geo["QTY_display"] = (geo["QTY_display"] / geo["QTY_display"].max()) * 40  # normalize size

    # --- 1️⃣ NIC Heat Map (Cell 239) ---
    if map_type == "NIC Heat Map (static)":
        fig_map = px.scatter_mapbox(
            geo,
            lat="Latitude",
            lon="Longitude",
            size="QTY_display",
            color="NIC",
            color_continuous_scale="Viridis",
            hover_name="ICB_Name",
            hover_data={
                "Post_Code": True,
                "Product_Group": True,
                "NIC": ":,.0f",
                "QTY": ":,.0f"
            },
            zoom=5.5,
            center={"lat": 54.2, "lon": -2.8},
            mapbox_style="carto-positron",
            title="💷 Daridorexant / Quviviq UK Usage by Postcode<br><sup>Bubble Size = Quantity, Colour = NIC (£)</sup>",
            height=700
        )
        st.plotly_chart(fig_map, use_container_width=True)

    # --- 2️⃣ Animated Adoption Map (Cell 232) ---
    elif map_type == "Animated Adoption Map (by Setting)":
        setting_colors = {
            "Primary": "#1f77b4",
            "Hosp_Community": "#ff7f0e",
            "Hospital": "#2ca02c"
        }
        geo["Month_str"] = geo["Month"].dt.strftime("%b-%Y")
        fig_anim = px.scatter_mapbox(
            geo,
            lat="Latitude",
            lon="Longitude",
            size="QTY_display",
            color="Quviviq_Type",
            color_discrete_map=setting_colors,
            hover_name="ICB_Name",
            hover_data={
                "Post_Code": True,
                "Product_Group": True,
                "QTY": ":,.0f",
                "NIC": ":,.0f",
                "ITEMS": ":,.0f"
            },
            animation_frame="Month_str",
            zoom=5.5,
            center={"lat": 54.2, "lon": -2.8},
            mapbox_style="carto-positron",
            title="💊 Daridorexant / Quviviq UK Adoption Over Time<br><sup>Bubble Size = Quantity, Colour = Setting</sup>",
            height=700
        )
        fig_anim.update_layout(
            margin=dict(l=0, r=0, t=80, b=0),
            legend=dict(
                title="Setting",
                orientation="h",
                yanchor="bottom",
                y=-0.15,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.8)"
            )
        )
        st.plotly_chart(fig_anim, use_container_width=True)

    # --- 3️⃣ Setting & Dose Scattermap (Cell 258) ---
    elif map_type == "Setting & Dose Scattermap":
        import plotly.graph_objects as go

        geo["Product_Group"] = geo["Product_Group"].astype(str).str.strip()
        geo["Quviviq_Type"] = geo["Quviviq_Type"].astype(str).str.strip()

        setting_colors = {
            "Primary": "#1f77b4",
            "Hosp_Community": "#ff7f0e",
            "Hospital": "#2ca02c"
        }
        dose_symbols = {"25mg": "circle", "50mg": "square"}

        fig_custom = go.Figure()
        for setting in geo["Quviviq_Type"].unique():
            for dose in geo["Product_Group"].unique():
                df_subset = geo[
                    (geo["Quviviq_Type"] == setting)
                    & (geo["Product_Group"] == dose)
                ]
                fig_custom.add_trace(go.Scattermapbox(
                    lat=df_subset["Latitude"],
                    lon=df_subset["Longitude"],
                    mode="markers",
                    name=f"{setting} | {dose}",
                    marker=dict(
                        size=(df_subset["QTY_display"] / df_subset["QTY_display"].max()) * 25,
                        color=setting_colors.get(setting, "#888"),
                        symbol=dose_symbols.get(dose, "circle"),
                        opacity=0.75
                    ),
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Setting: %{customdata[1]}<br>"
                        "Dose: %{customdata[2]}<br>"
                        "QTY: %{customdata[3]:,.0f}<br>"
                        "NIC: £%{customdata[4]:,.0f}<br>"
                        "ITEMS: %{customdata[5]:,.0f}<extra></extra>"
                    ),
                    customdata=df_subset[
                        ["ICB_Name", "Quviviq_Type", "Product_Group", "QTY", "NIC", "ITEMS"]
                    ],
                ))

        fig_custom.update_layout(
            mapbox=dict(
                style="carto-positron",
                zoom=5.5,
                center={"lat": 54.2, "lon": -2.8}
            ),
            title="💊 Daridorexant / Quviviq UK Adoption<br><sup>Colour = Setting, Shape = Dose, Size = Quantity</sup>",
            height=700,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.15,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.8)"
            ),
            margin=dict(l=0, r=0, t=80, b=0)
        )
        st.plotly_chart(fig_custom, use_container_width=True)

else:
    st.info("📍 Geographic data not available. Please include Input_File_Postcode_Geo_With_Latlon.csv in the data folder.")
# -------------------------
# 1) Overall Trends
# -------------------------
monthly = fdf.groupby("Month")[["QTY", "NIC", "ITEMS"]].sum().reset_index().sort_values("Month")
fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=monthly["Month"], y=monthly["QTY"], mode="lines+markers", name="QTY"))
fig1.add_trace(go.Scatter(x=monthly["Month"], y=monthly["NIC"], mode="lines+markers", name="NIC"))
fig1.add_trace(go.Scatter(x=monthly["Month"], y=monthly["ITEMS"], mode="lines+markers", name="ITEMS"))
fig1.update_layout(title="Overall Monthly Usage Trends", xaxis_title="Month", yaxis_title="Value")
st.plotly_chart(fig1, use_container_width=True)

# -------------------------
# 2) Setting Trends
# -------------------------
setting_trends = fdf.groupby(["Month", "Quviviq_Type"])[["QTY"]].sum().reset_index().sort_values("Month")
fig2 = px.line(setting_trends, x="Month", y="QTY", color="Quviviq_Type",
               title="Quantity by Setting (Primary, Hosp_Community, Hospital)",
               labels={"QTY": "Quantity", "Quviviq_Type": "Setting"})
st.plotly_chart(fig2, use_container_width=True)

# -------------------------
# 3) Dose Trends
# -------------------------
dose_trends = fdf.groupby(["Month", "Product_Group"])[["QTY"]].sum().reset_index().sort_values("Month")
fig3 = px.line(dose_trends, x="Month", y="QTY", color="Product_Group",
               title="Daridorexant Usage by Dose (25mg vs 50mg)",
               labels={"QTY": "Quantity", "Product_Group": "Dose"})
st.plotly_chart(fig3, use_container_width=True)

# -------------------------
# 4) Brand vs Generic
# -------------------------
brand_trends = fdf.groupby(["Month", "BNF_Name"])[["QTY"]].sum().reset_index().sort_values("Month")
fig4 = px.line(brand_trends, x="Month", y="QTY", color="BNF_Name",
               title="Brand vs Generic (Usage over time)",
               labels={"QTY": "Quantity", "Brand": "Brand/Generic"})
st.plotly_chart(fig4, use_container_width=True)

# -------------------------
# 5) Top ICBs
# -------------------------
if not fdf.empty:
    latest_month = fdf["Month"].max()
    regional_latest = fdf[fdf["Month"] == latest_month].groupby("ICB_Name")[["QTY", "NIC", "ITEMS"]].sum().sort_values("QTY", ascending=False).reset_index()
    fig5 = px.bar(regional_latest.head(15), x="QTY", y="ICB_Name", orientation="h",
                  title=f"Top 15 ICBs by Quantity — {latest_month.strftime('%b %Y')}",
                  labels={"QTY": "Quantity", "ICB_Name": "ICB"})
    fig5.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig5, use_container_width=True)
else:
    st.info("No data available for selected filters.")

# -------------------------
# 6) Forecast (QTY, NIC & ITEMS)
# -------------------------
st.markdown("### Forecast (next 12 months)")

fcast = data.get("forecast_summary")
if fcast is not None and not fcast.empty:
    fcast = fcast.copy()
    fcast["Month"] = pd.to_datetime(fcast["Month"])

    # Historical totals
    hist_totals = (
        df.groupby("Month")[["QTY", "NIC", "ITEMS"]]
        .sum()
        .reset_index()
        .sort_values("Month")
    )

    # Create figure
    fig6 = go.Figure()

    # --- Historical lines ---
    fig6.add_trace(go.Scatter(
        x=hist_totals["Month"], y=hist_totals["QTY"],
        mode="lines", name="Historical QTY", line=dict(color="royalblue")
    ))
    fig6.add_trace(go.Scatter(
        x=hist_totals["Month"], y=hist_totals["NIC"],
        mode="lines", name="Historical NIC (£)", line=dict(color="darkorange")
    ))
    fig6.add_trace(go.Scatter(
        x=hist_totals["Month"], y=hist_totals["ITEMS"],
        mode="lines", name="Historical ITEMS", line=dict(color="green")
    ))

    # --- Forecast lines ---
    if "Forecast_QTY" in fcast.columns:
        fig6.add_trace(go.Scatter(
            x=fcast["Month"], y=fcast["Forecast_QTY"],
            mode="lines+markers", name="Forecast QTY", line=dict(dash="dash", color="royalblue")
        ))
    if "Forecast_NIC" in fcast.columns:
        fig6.add_trace(go.Scatter(
            x=fcast["Month"], y=fcast["Forecast_NIC"],
            mode="lines+markers", name="Forecast NIC (£)", line=dict(dash="dash", color="darkorange")
        ))
    if "Forecast_ITEMS" in fcast.columns:
        fig6.add_trace(go.Scatter(
            x=fcast["Month"], y=fcast["Forecast_ITEMS"],
            mode="lines+markers", name="Forecast ITEMS", line=dict(dash="dash", color="green")
        ))

    # --- Layout ---
    fig6.update_layout(
        title="Forecast (QTY, NIC & ITEMS) — Next 12 Months",
        xaxis_title="Month",
        yaxis_title="Value",
        legend_title="Metric",
        template="plotly_white"
    )

    st.plotly_chart(fig6, use_container_width=True)

else:
    st.info("Forecast file not found (forecast_summary.csv).")
# -------------------------
# 9) Summary & Key Insights
# -------------------------
st.markdown("---")
st.markdown("## 🧠 Final Summary & Insights")

st.markdown(
    """
<style>
.summary-card {
    background-color: #f9fafc;
    padding: 25px;
    border-radius: 15px;
    border-left: 6px solid #4A90E2;
    margin-bottom: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.summary-card h4 {
    color: #1f3b73;
    margin-top: 0;
}
</style>
""",
    unsafe_allow_html=True
)

# ---- Product ----
st.markdown(
    """
<div class='summary-card'>
<h4>Product</h4>
<p>The adoption over time shows <b>Daridorexant (Quviviq)</b> prescriptions distributed across NHS regions, confirming national dispersion.</p>
<ul>
<li>🗺️ Bubbles across England, Wales, and Scotland indicate product penetration.</li>
<li>🏥 Likely initially launched in specialist locations (sleep clinics / major teaching hospitals).</li>
</ul>
</div>
""",
    unsafe_allow_html=True
)

# ---- Overall Growth ----
st.markdown(
    """
<div class='summary-card'>
<h4> Overall Growth</h4>
<p>From <b>quarter 1 2024 to Jun 2025</b>, total monthly quantity dispensed increased steadily, reflecting market adoption post-launch. Forecast suggests continued moderate growth through mid-2026, consistent with a maturing product entering broader NHS uptake.</p>


<ul>
</ul>
<p><b>Primary Care</b> dominates usage (>80%), followed by small but growing uptake in <b>hospital/community dispensing</b>.</p>
</div>
""",
    unsafe_allow_html=True
)
# ---- Dosage & Brand Mix ----
st.markdown(
    """
<div class='summary-card'>
<h4> Dosage & Brand Mix</h4>
<ul>
<li>💊 <b>50mg dose</b> now accounts for majority usage.</li>
<li>🧾 <b>Quviviq (brand)</b> slightly leads over <b>Daridorexant (generic)</b>.</li>
<li>💷 Price sensitivity absent due to flat pricing (£42 per pack).</li>
</ul>
</div>
""",
    unsafe_allow_html=True
)

# ---- Regional Insight ----
st.markdown(
    """
<div class='summary-card'>
<h4> Regional Insight</h4>
<p>Top ICBs indicate early adoption across <b>high-prescribing sleep medicine centres</b>.</p>
<p>Smaller ICBs show <b>gradual uptake</b>.</p>
</div>
""",
    unsafe_allow_html=True
)

# ---- Forward Outlook ----
st.markdown(
    """
<div class='summary-card'>
<h4> Forward Outlook</h4>
<p>📈 12-month forecast indicates <b>steady growth</b> with no strong seasonal pattern.</p>
<p>Forecast Indicates <b>continuing clinician adoption</b> and integration into treatment guidelines.</p>
</div>
""",
    unsafe_allow_html=True
)
# -------------------------
# 7) Data Explorer
# -------------------------
st.subheader("Raw Data Explorer")
st.dataframe(fdf, use_container_width=True)

csv_bytes = fdf.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download filtered data (CSV)", data=csv_bytes, file_name="filtered_data.csv", mime="text/csv")

filtered_monthly = fdf.groupby("Month")[["QTY", "NIC", "ITEMS"]].sum().reset_index().sort_values("Month")
csv_monthly = filtered_monthly.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download filtered monthly summary (CSV)", data=csv_monthly, file_name="filtered_monthly_summary.csv", mime="text/csv")
