"""Main Description."""

import logging

import pandas as pd
import plotly.express as px
import snowflake.connector.errors as sf_errors
import snowflake.snowpark.exceptions as sp_errors
import streamlit as st

from amissiontozero import utils

LOGGER = logging.getLogger(__name__)


def display_content(data) -> None:
    """Function to display charts."""
    # user inputs
    geschaeftspartner_selected: str = st.multiselect(
        "Select Geschäftspartner", data["Geschäftspartner"].unique()
    )
    data_filtered = data[data["Geschäftspartner"].isin(geschaeftspartner_selected)]
    if len(geschaeftspartner_selected) == 1:
        geschaeftspartner_selected = geschaeftspartner_selected[0]

    col1, col2 = st.columns(2)

    with col1:
        plot_abos(data_filtered, geschaeftspartner_selected)

    with col2:
        plot_emissions_time(data_filtered, geschaeftspartner_selected)
    st.subheader(f"Summary table for Geschäftspartner {geschaeftspartner_selected}")
    plot_summary_table(data_filtered, geschaeftspartner_selected)


@st.cache_data
def load_process_data():
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
    # calculate kilometer from Betrag as done in Basic Emissions Report
    data["kilometer"] = data.apply(utils.calculate_kilometer, axis=1)
    data["co2_equivalent_kg_per_pkm"] = data.apply(utils.calculate_kilometer, axis=1)
    data = utils.calculate_energy_mj_equiv_per_km(data)
    return data


def plot_abos(data, geschaeftspartner_selected):

    color_sequence = px.colors.qualitative.Plotly

    # will plot the distribution of Abos for a given geschäftspartner: only a proof of concept for now
    data_filtered_unique = (
        data.drop_duplicates(subset=["WebShop Benutzer Name", "Reduktion"])
        .groupby("Reduktion")
        .size()
        .reset_index(name="Count")
    )
    data_filtered_unique["Overall"] = "Overall"
    data_filtered_unique["Reduktion"] = data_filtered_unique["Reduktion"].astype(str)

    # Create a filled (100% stacked) bar chart using barnorm='percent'
    fig_abos = px.bar(
        data_filtered_unique,
        x="Overall",
        y="Count",
        color="Reduktion",
        title=f"Distribution of Abo subscriptions for Geschäftspartner {geschaeftspartner_selected}",
        labels={"Overall": "", "Reduktion": "Discount"},
        color_discrete_sequence=color_sequence,
    )

    st.plotly_chart(fig_abos, use_container_width=True)


def plot_emissions_time(data, geschaeftspartner_selected):

    df_time = data.dropna(subset=["Hinreisedatum"])  # Remove rows with missing dates
    sales_over_time = (
        df_time.groupby("Hinreisedatum")[["kilometer", "co2_equivalent_kg_per_pkm"]]
        .sum()
        .reset_index()
    )

    sales_long = sales_over_time.melt(
        id_vars="Hinreisedatum",
        value_vars=["kilometer", "co2_equivalent_kg_per_pkm"],
        var_name="Metric",
        value_name="Value",
    )

    # Plot
    fig_emissions = px.line(
        sales_long[sales_long["Metric"] == "co2_equivalent_kg_per_pkm"],
        x="Hinreisedatum",
        y="Value",
        color="Metric",
        title=f"CO₂ Equivalents Over Time for Geschäftspartner {geschaeftspartner_selected}",
        labels={
            "Hinreisedatum": "Departure Date",
            "Value": "Value",
            "Metric": "Metric",
        },
    )

    st.plotly_chart(fig_emissions, use_container_width=True)


def plot_summary_table(data, geschaeftspartner_selected):
    summary_table = (
        data.groupby("RUMBA-Artikel")
        .agg(
            Count=("kilometer", "count"),
            Total_Kilometers=("kilometer", "sum"),
            Total_Energy_MJ_per_km=("energy_mj_equiv_per_km", "sum"),
            Total_CO2_kg=("co2_equivalent_kg_per_pkm", "sum"),
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
    st.set_page_config(layout="wide", page_title="CO2 Emissions Dashboard")
    st.title("CO2 Emissions")
    data = load_process_data()
    display_content(data)


if __name__ == "__main__":
    main()
