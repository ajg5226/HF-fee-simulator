import streamlit as st
import pandas as pd
import altair as alt
from io import BytesIO


def input_benchmark(default_ticker: str = "SPY") -> str:
    """
    Render a text input for benchmark ticker and return the user-entered value.
    """
    return st.text_input("Benchmark ticker", value=default_ticker)


def input_fee_schemes(max_schemes: int = 3) -> list[dict]:
    """
    Render UI for configuring up to `max_schemes` fee schemes and return a list of scheme dicts.
    """
    n_schemes = st.number_input(
        "Number of fee schemes", min_value=1, max_value=max_schemes, value=1
    )
    schemes = []
    for i in range(int(n_schemes)):
        with st.expander(f"Scheme {i+1}"):
            name = st.text_input(f"Name (scheme {i+1})", value=f"Scheme {i+1}")
            hwm = st.checkbox("High-water mark", value=True, key=f"hwm_{i}")
            tiered = st.checkbox("Tiered waterfall", key=f"tiered_{i}")
            tiers = []
            if tiered:
                n_tiers = st.number_input(
                    "Number of tiers", min_value=1, max_value=5, value=3, key=f"n_tiers_{i}"
                )
                for t in range(int(n_tiers)):
                    st.markdown(f"**Tier {t+1}**")
                    if t < n_tiers - 1:
                        thresh = st.number_input(
                            "Upper threshold (decimal)", min_value=0.0, max_value=1.0,
                            value=0.01*(t+1), key=f"thresh_{i}_{t}"
                        )
                    else:
                        thresh = None
                    share = st.number_input(
                        "Manager share (0-1)", min_value=0.0, max_value=1.0,
                        value=0.5, key=f"share_{i}_{t}"
                    )
                    tiers.append({'threshold': thresh, 'manager_share': share})
            else:
                mgmt = st.number_input(
                    "Mgmt fee % (annual)", min_value=0.0, max_value=5.0,
                    value=2.0, key=f"mgmt_{i}"
                ) / 100
                perf = st.number_input(
                    "Perf fee %", min_value=0.0, max_value=100.0,
                    value=20.0, key=f"perf_{i}"
                ) / 100
                hurdle = st.number_input(
                    "Hurdle rate % (annual)", min_value=0.0, max_value=10.0,
                    value=0.0, key=f"hurdle_{i}"
                ) / 100
            schemes.append({
                'name': name,
                'hwm': hwm,
                'tiered': tiered,
                'tiers': tiers,
                'mgmt': mgmt if not tiered else 0.0,
                'perf': perf if not tiered else 0.0,
                'hurdle': hurdle if not tiered else 0.0
            })
    return schemes


def download_button(results: dict, filename: str = "fee_simulator_results.xlsx"):
    """
    Render an Excel download button for the results dict, where each key has 'monthly' and 'annual' DataFrames.
    """
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for name, data in results.items():
            data['monthly'].to_excel(writer, sheet_name=f"{name}_Monthly", index=False)
            data['annual'].to_excel(writer, sheet_name=f"{name}_Annual")
    st.download_button("Download Excel Results", buffer.getvalue(), file_name=filename)


def show_chart(title: str, df: pd.DataFrame, chart_type: str = 'line', **kwargs):
    """
    Generic chart renderer: 'line' or 'bar'.
    """
    st.subheader(title)
    if chart_type == 'line':
        st.line_chart(df, **kwargs)
    elif chart_type == 'bar':
        st.bar_chart(df, **kwargs)


def show_altair(chart, use_container_width: bool = True):
    """
    Display an Altair chart.
    """
    st.altair_chart(chart, use_container_width=use_container_width)


def show_table(title: str, df: pd.DataFrame):
    """
    Render a subheader and a dataframe.
    """
    st.subheader(title)
    st.dataframe(df)
