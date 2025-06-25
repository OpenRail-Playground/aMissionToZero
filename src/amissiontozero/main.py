"""Main Description."""

import logging
from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from sklearn.linear_model import LinearRegression

from amissiontozero import utils

LOGGER = logging.getLogger(__name__)


def display_content(data) -> None:
    """Function to display charts.

    params:
    data (pd.DataFrame)."""
    # user inputs
    geschaeftspartner_selected: str = st.multiselect(
        "Select Geschäftspartner", data["Geschäftspartner"].unique()
    )
    zeitraum_selected: str = st.segmented_control(
        "Select Zeitraum", ["All", "Year To Date", "3 months"]
    )

    data_filtered = data[data["Geschäftspartner"].isin(geschaeftspartner_selected)]
    data_filtered = utils.filter_zeitraum(data_filtered, zeitraum_selected)
    if len(geschaeftspartner_selected) == 1:
        geschaeftspartner_selected = geschaeftspartner_selected[0]

    col1, col2 = st.columns(2)

    with col1:
        plot_year_to_date_widget(data_filtered, zeitraum_selected)

    with col2:
        plot_emissions_trend(data_filtered, zeitraum_selected)
    plot_progress_bar(data, zeitraum_selected)
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader(f"📋Summary table for Geschäftspartner {geschaeftspartner_selected}")
    plot_summary_table(data_filtered, geschaeftspartner_selected)


@st.cache_data
def load_process_data():
    """Load and process the data.

    returns: pd.Dataframe
    """
    data = pd.read_csv("/home/u243650/aMissionToZero/data/sap_data.csv")
    lookup_table_ticket_types = pd.read_excel(
        "/home/u243650/aMissionToZero/data/Basic Emissions Report.xlsx",
        sheet_name="Artikel Prüfung",
    )
    data = data.merge(
        lookup_table_ticket_types,
        left_on="NOVA Produktbezeichnung",
        right_on="Artikelname",
    )
    data["Geschäftspartner"] = data["Geschäftspartner"].round().astype("category")
    data["Betrag"] = pd.to_numeric(data["Betrag"], errors="coerce")
    data["Hinreisedatum"] = pd.to_datetime(data["Hinreisedatum"])
    # calculate kilometer from Betrag as done in Basic Emissions Report
    data["kilometer"] = data.apply(utils.calculate_kilometer, axis=1)
    data["co2_equivalent_kg"] = data.apply(utils.calculate_emission, axis=1)
    data["co2_savings_vs_miv"] = (data["kilometer"] * 118.64 / 1000) - data[
        "co2_equivalent_kg"
    ]
    data["number_trees"] = data["co2_savings_vs_miv"] / 24.62

    data = utils.calculate_energy_mj_equiv_per_km(data)
    return data


def plot_year_to_date_widget(data, zeitraum_selected):
    """Plot progress on current year.

    params:
    data (pd.DataFrame):
    zeitraum_selected (str): string for labeling
    """
    total_co2 = data["co2_equivalent_kg"].sum().round()

    total_co2_savings = data["co2_savings_vs_miv"].sum().round()
    total_trees = data["number_trees"].sum().round()

    total_co2_string = f"""
    <h3 style='text-align: center;'>🚂 {zeitraum_selected} CO₂ Total</h3>
    <h3 style='text-align: center; color: green;'>{int(total_co2):,} kg</h3>
    """

    total_savings_string = f"""
    <h3 style='text-align: center;'>🌍 {zeitraum_selected} CO₂ Savings versus car</h3>
    <h3 style='text-align: center; color: green;'>{int(total_co2_savings):,} kg</h3>
    """
    total_trees_string = f"""
    <h3 style='text-align: center;'>🌳 {zeitraum_selected} Trees</h3>
    <h3 style='text-align: center; color: green;'>{int(total_trees):,} kg</h3>
    """

    st.markdown(total_co2_string, unsafe_allow_html=True)
    st.markdown(total_savings_string, unsafe_allow_html=True)
    st.markdown(total_trees_string, unsafe_allow_html=True)


def plot_progress_bar(data, zeitraum_selected):
    """Plot progress bar.

    params:
    data (pd.DataFrame):
    zeitraum_selected (str): string for labeling
    """
    total_co2_savings = data["co2_savings_vs_miv"].sum().round()
    goal_co2 = total_co2_savings * 2.5
    progress = total_co2_savings / goal_co2
    st.markdown(f"### 🎯 CO₂ Target Progress {zeitraum_selected}")
    st.markdown(
        f"""
    <div style="background-color: #eee; border-radius: 10px; padding: 3px;">
    <div style="width: {progress * 100:.1f}%; background-color: orange; padding: 8px 0; border-radius: 10px; text-align: center; font-size: 20px; color: white;">
        {progress * 100:.1f}%
    </div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def plot_emissions_trend(data, zeitraum_selected):
    """Plot emissions over time and trend.

    params:
    data (pd.DataFrame):
    zeitraum_selected (str): string for labeling
    """
    st.subheader(f"📈 {zeitraum_selected} cumulative CO2 with 3-Month Forecast")

    co2_over_time = (
        data.groupby("Hinreisedatum")["co2_equivalent_kg"]
        .sum()
        .reset_index()
        .sort_values("Hinreisedatum")
    )

    # Step 3: Add cumulative sum column
    co2_over_time["cumulative_co2_kg"] = co2_over_time["co2_equivalent_kg"].cumsum()

    # Convert dates to ordinal for regression
    x = co2_over_time["Hinreisedatum"].map(pd.Timestamp.toordinal).values.reshape(-1, 1)
    y = co2_over_time["cumulative_co2_kg"].values

    # Fit linear regression
    model = LinearRegression()
    model.fit(x, y)

    # Predict original trend line
    co2_over_time["trend"] = model.predict(x)

    # Predict 3 months into future
    last_date = co2_over_time["Hinreisedatum"].max()
    future_dates = pd.date_range(
        start=last_date + timedelta(days=1),
        end=last_date + pd.DateOffset(months=3),
        freq="D",
    )

    future_ordinals = future_dates.map(pd.Timestamp.toordinal).values.reshape(-1, 1)
    future_preds = model.predict(future_ordinals)

    # Create future DataFrame
    df_future = pd.DataFrame(
        {
            "Hinreisedatum": future_dates,
            "cumulative_co2_kg": np.nan,  # optional: hide actual points
            "trend": future_preds,
        }
    )

    # Combine original + future for full trend
    df_combined = pd.concat([co2_over_time, df_future], ignore_index=True)

    fig = px.line(
        df_combined,
        x="Hinreisedatum",
        y="trend",
        labels={"trend": "Cumulative CO₂ (kg)"},
    )
    fig.add_scatter(
        x=co2_over_time["Hinreisedatum"],
        y=co2_over_time["cumulative_co2_kg"],
        mode="markers",
        name="Actual",
    )

    st.plotly_chart(fig)


def plot_summary_table(data, geschaeftspartner_selected):
    """Plot summary table for download. TODO: should add label for zeitraum.

    params:
    data (pd.DataFrame):
    geschaeftspartner (str): string for labeling
    """
    summary_table = (
        data.groupby("RUMBA-Artikel")
        .agg(
            Count=("kilometer", "count"),
            Total_Kilometers=("kilometer", "sum"),
            Total_Energy_MJ_per_km=("energy_mj_equiv_per_km", "sum"),
            Total_CO2_kg=("co2_equivalent_kg", "sum"),
            total_betrag=("Betrag", "sum"),
        )
        .reset_index()
        .sort_values("Count", ascending=False)
    )
    totals = pd.DataFrame(
        [
            {
                "RUMBA-Artikel": "TOTAL",
                "Count": summary_table["Count"].sum(),
                "Total_Kilometers": summary_table["Total_Kilometers"].sum(),
                "Total_Energy_MJ_per_km": summary_table["Total_Energy_MJ_per_km"].sum(),
                "Total_CO2_kg": summary_table["Total_CO2_kg"].sum(),
                "total_betrag": summary_table["total_betrag"].sum(),
            }
        ]
    )

    # Append totals to the summary table
    summary_table = pd.concat([summary_table, totals], ignore_index=True)

    # Optional: rename columns for display
    summary_table.columns = [
        "RUMBA-Artikel",
        "Anzahl von Artikelbezeichnung",
        "Total Kilometers",
        "Total Energy (MJ/km)",
        "Total CO₂ Equivalent (kg)",
        "Betrag",
    ]

    st.dataframe(summary_table, use_container_width=True)
    csv_data = summary_table.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Summary as CSV",
        data=csv_data,
        file_name=f"summary_geschaeftspartner_{geschaeftspartner_selected}.csv",
        mime="text/csv",
    )


def main() -> None:
    """Main entry point for the application."""
    LOGGER.info("Executing Streamlit Application")
    st.set_page_config(layout="wide", page_title="A Mission To Zero")
    st.title("A Mission To Zero")
    data = load_process_data()
    display_content(data)


if __name__ == "__main__":
    main()
