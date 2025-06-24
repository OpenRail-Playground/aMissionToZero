"""Utils for streamlit."""

import logging
import os

import numpy as np
import pandas as pd
import snowflake
import streamlit as st
from snowflake.snowpark import Session

LOGGER = logging.getLogger(__name__)


# based on Betrag, done as in Basic Emissions Report excel
def calculate_kilometer(row):
    betrag = row["Betrag"]
    reiseklasse = row["Reiseklasse"]
    reduktion = row["Reduktion"]

    if betrag < 0:
        return betrag / 0.3
    if reiseklasse == 0 and pd.isna(reduktion):
        return 0
    if reiseklasse == 0 and reduktion == "KEINE":
        return 0
    if reiseklasse == 2 and reduktion == "GA1KL":
        return betrag / 0.2
    if reiseklasse == 1 and reduktion == "GA1KL":
        return betrag / 0.36
    if reiseklasse == 1 and reduktion == "GA2KL":
        return betrag / 0.36
    if reiseklasse == 0 and reduktion == "HTA123":
        return 0
    if reiseklasse == 1 and reduktion == "HTA123":
        return betrag / 0.36
    if reiseklasse == 2 and reduktion == "HTA123":
        return betrag / 0.2
    if reiseklasse == 1 and reduktion == "KEINE":
        return betrag / 0.287
    if reiseklasse == 1 and pd.isna(reduktion):
        return betrag / 0.287
    if reiseklasse == 2 and pd.isna(reduktion):
        return betrag / 0.239
    if reiseklasse == 2 and reduktion == "KEINE":
        return betrag / 0.239
    return betrag  # fallback


def calculate_emission(row):
    artikel = row["RUMBA-Artikel"]
    km = row["kilometer"]

    if artikel in ["Tickets Inland", "GA", "Ausschluss", "Erstattung", "#NV"]:
        return km * 7.02 / 1000
    elif artikel == "Tickets Ausland":
        return km * 40.82 / 1000
    elif artikel == "Tickets Verkehrsverbund":
        return km * 8.04 / 1000
    else:
        return np.nan  # or 0 if you'd prefer to default


def calculate_energy_mj_equiv_per_km(data):
    conditions = [
        data["RUMBA-Artikel"] == "Tickets Inland",
        data["RUMBA-Artikel"] == "GA",
        data["RUMBA-Artikel"] == "Tickets Ausland",
        data["RUMBA-Artikel"] == "Ausschluss",
        data["RUMBA-Artikel"] == "Erstattung",
        data["RUMBA-Artikel"] == "Tickets Verkehrsverbund",
        data["RUMBA-Artikel"] == "#NV",
    ]

    # Define corresponding multipliers
    multipliers = [0.5, 0.5, 0.75, 0.5, 0.5, 0.73, 0.5]

    # Apply conditions to compute new column
    data["energy_mj_equiv_per_km"] = (
        np.select(conditions, multipliers, default=np.nan) * data["kilometer"]
    )
    return data


####################### below: snowflake utils for bootcamp
def _get_access_token() -> str:
    """Getting access token."""
    headers = st.context.headers
    access_token = headers.get("X-Forwarded-Access-Token") if headers else None
    if access_token is None:
        # for local testing
        access_token = os.environ["ACCESS_TOKEN"]
    return access_token


def connect_to_snowflake() -> Session:
    """Creates a Snowpark connection using access token."""
    token = _get_access_token()
    snowflake_account = os.environ["SNOWFLAKE_ACCOUNT"]
    snowflake_warehouse = os.environ["SNOWFLAKE_WAREHOUSE"]
    snowflake_database = os.environ["SNOWFLAKE_DATABASE"]
    snowflake_schema = os.environ["SNOWFLAKE_SCHEMA"]
    snowflake_role = os.environ["SNOWFLAKE_ROLE"]

    conn = snowflake.connector.connect(
        account=snowflake_account,
        authenticator="oauth",
        token=token,
        warehouse=snowflake_warehouse,
        database=snowflake_database,
        schema=snowflake_schema,
        role=snowflake_role,
    )

    session: Session = Session.builder.configs({"connection": conn}).create()
    user = session.sql("select current_user()").collect()[0][0]
    LOGGER.info("Created Snowpark session for user %s", user)
    return session
