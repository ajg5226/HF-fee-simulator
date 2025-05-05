import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from io import BytesIO
import yfinance as yf

from feesim.engine import calculate_scheme, performance_metrics
import config

# Streamlit App
st.title("Hedge Fund Fee Simulator")

uploaded = st.file_uploader("Upload monthly returns CSV", type=['csv'])
if uploaded:
    # Load and validate CSV
    try:
        df = pd.read_csv(uploaded, parse_dates=['Date'])
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        st.stop()
    df.sort_values('Date', inplace=True)
    missing = [c for c in config.REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        st.error(f"CSV missing required columns: {', '.join(missing)}")
        st.stop()

    # Benchmark ticker input
    bench_ticker = st.text_input("Benchmark ticker", value="SPY")

    # Download and compute monthly benchmark returns
    start_date = df['Date'].min().strftime("%Y-%m-%d")
    end_date   = df['Date'].max().strftime("%Y-%m-%d")
    try:
        bench_data = yf.download(
            bench_ticker,
            start=start_date,
            end=end_date,
            interval="1mo",
            auto_adjust=True,
            progress=False
        )
        if bench_data.empty or 'Close' not in bench_data.columns:
            raise ValueError("No Close price data returned.")
        bench_prices = bench_data['Close']
        bench_returns = bench_prices.pct_change().dropna()
        # Align to fund dates
        bench_returns.index = pd.to_datetime(bench_returns.index).normalize()
        monthly_bench = bench_returns.reindex(
            df['Date'].dt.normalize()
        ).ffill().fillna(0)
    except Exception as e:
        st.error(f"Error fetching benchmark data for {bench_ticker}: {e}")
        st.stop()

    # Annualized benchmark return
    n_periods = len(monthly_bench)
    ann_ret_bench = (monthly_bench + 1).prod() ** (12 / n_periods) - 1
    # Raw array for tracking error
    bench_arr = monthly_bench.values

    # Initial AUM input
    initial_aum_str = st.text_input(
        "Initial AUM",
        value=f"{config.DEFAULT_AUM:,.2f}"
    )
    try:
        initial_aum = float(initial_aum_str.replace(",", ""))
    except ValueError:
        st.error("Invalid AUM format. Please enter a number like 100,000,000.00")
        st.stop()

    # Fee schemes configuration
    n_schemes = st.number_input(
        "Number of fee schemes", min_value=1, max_value=3, value=1
    )
    schemes = []
    for i in range(int(n_schemes)):
        with st.expander(f"Scheme {i+1}"):
            name   = st.text_input(f"Name (scheme {i+1})", value=f"Scheme {i+1}")
            hwm    = st.checkbox("High-water mark", value=True, key=f"hwm_{i}")
            tiered = st.checkbox("Tiered waterfall",    key=f"tiered_{i}")

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
                mgmt   = st.number_input(
                    "Mgmt fee % (annual)", min_value=0.0, max_value=5.0,
                    value=2.0, key=f"mgmt_{i}"
                ) / 100
                perf   = st.number_input(
                    "Perf fee %", min_value=0.0, max_value=100.0,
                    value=20.0, key=f"perf_{i}"
                ) / 100
                hurdle = st.number_input(
                    "Hurdle rate % (annual)", min_value=0.0, max_value=10.0,
                    value=0.0, key=f"hurdle_{i}"
                ) / 100

            schemes.append({
                'name':   name,
                'hwm':    hwm,
                'tiered': tiered,
                'tiers':  tiers,
                'mgmt':   (mgmt   if not tiered else 0.0),
                'perf':   (perf   if not tiered else 0.0),
                'hurdle': (hurdle if not tiered else 0.0)
            })

    # Run Simulation
    if st.button("Run Simulation"):
        results = {}
        try:
            for scheme in schemes:
                monthly_df, annual_rev = calculate_scheme(
                    df, scheme, initial_aum
                )
                results[scheme['name']] = {
                    'monthly': monthly_df,
                    'annual':  annual_rev
                }
        except Exception as e:
            st.error(f"Simulation error: {e}")
            st.stop()

        # Downloadable Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            for name, data in results.items():
                data['monthly'].to_excel(
                    writer, sheet_name=f"{name}_Monthly", index=False
                )
                data['annual'].to_excel(
                    writer, sheet_name=f"{name}_Annual"
                )
        st.download_button(
            "Download Excel Results",
            buffer.getvalue(),
            file_name="fee_simulator_results.xlsx"
        )

        # Display Tables and Charts
        for name, data in results.items():
            st.subheader(f"{name} – Monthly Results")
            st.dataframe(data['monthly'])
            st.subheader(f"{name} – Annual Fee Revenue")
            st.dataframe(data['annual'])

        st.subheader("AUM Over Time")
        aum_df = pd.concat([
            res['monthly'].set_index('Date')['AUM_End'].rename(name)
            for name, res in results.items()
        ], axis=1)
        st.line_chart(aum_df)

        st.subheader("Cumulative Net Return")
        net_df = pd.concat([
            res['monthly'].set_index('Date')['NetReturn'].add(1).cumprod().rename(name)
            for name, res in results.items()
        ], axis=1)
        st.line_chart(net_df)

        fee_rev = pd.concat([
            res['annual']['TotalFeeRev'].rename(name)
            for name, res in results.items()
        ], axis=1)
        fee_rev.index.name = 'Year'
        rev_melt = fee_rev.reset_index().melt(
            id_vars='Year', var_name='Scheme', value_name='TotalFeeRev'
        )
        st.subheader("Annual Total Fee Revenue by Scheme")
        bar = alt.Chart(rev_melt).mark_bar().encode(
            x='Year:O', y='TotalFeeRev:Q', color='Scheme:N', column='Scheme:N'
        )
        st.altair_chart(bar, use_container_width=True)

        stats = pd.DataFrame({
            'MeanFeeRev':     fee_rev.mean(),
            'StdDevFeeRev':   fee_rev.std(),
            'CoeffVarFeeRev': fee_rev.std() / fee_rev.mean()
        })
        stats.index.name = 'Scheme'
        st.subheader("Annual Fee Revenue Statistics")
        st.dataframe(stats)

        st.subheader("Coefficient of Variation of Annual Fee Revenue")
        st.bar_chart(stats['CoeffVarFeeRev'])

        stats_reset = stats.reset_index()
        mean_chart = alt.Chart(stats_reset).mark_bar().encode(
            x='Scheme:N', y='MeanFeeRev:Q'
        )
        st.subheader("Mean of Annual Fee Revenue")
        st.altair_chart(mean_chart, use_container_width=True)

        std_chart = alt.Chart(stats_reset).mark_bar().encode(
            x='Scheme:N', y='StdDevFeeRev:Q'
        )
        st.subheader("Standard Deviation of Annual Fee Revenue")
        st.altair_chart(std_chart, use_container_width=True)

        # Performance Statistics Table
        rf = config.RISK_FREE_RATE
        perf_list = []
        for name, data in results.items():
            monthly_net = data['monthly']['NetReturn']
            metrics = performance_metrics(monthly_net, rf=rf)
            # Tracking error and Information Ratio
            net_arr = monthly_net.values
            diff_arr = net_arr - bench_arr
            tracking_err = np.std(diff_arr, ddof=0) * np.sqrt(12)
            if tracking_err != 0:
                info_ratio = (metrics['Annualized Return'] - ann_ret_bench) / tracking_err
            else:
                info_ratio = np.nan
            metrics['Information Ratio'] = info_ratio
            metrics['Scheme'] = name
            perf_list.append(metrics)

        perf_df = pd.DataFrame(perf_list).set_index('Scheme')
        st.subheader("Risk-Adjusted Return Statistics")
        st.dataframe(perf_df)

