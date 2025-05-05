import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from io import BytesIO

from feesim.engine import calculate_scheme, performance_metrics
import config
from feesim.benchmark import fetch_monthly_prices, align_to_dates
from feesim.metrics import (
    tracking_error,
    information_ratio,
    beta as calc_beta,
    annualize_return,
    yearly_returns
)
from feesim.utils import read_validate_csv, parse_aum


# Streamlit App
st.title("Hedge Fund Fee Simulator")

uploaded = st.file_uploader("Upload monthly returns CSV", type=['csv'])
if uploaded:
    # Load and validate CSV
     try:
         df = read_validate_csv(uploaded, config.REQUIRED_COLUMNS)
     except ValueError as e:
         st.error(str(e))
         st.stop()

    # Benchmark ticker input
    bench_ticker = st.text_input("Benchmark ticker", value="SPY")

    # Fetch and align benchmark returns
    start_date = df['Date'].min().strftime("%Y-%m-%d")
    end_date   = df['Date'].max().strftime("%Y-%m-%d")
    raw_prices    = fetch_monthly_prices(bench_ticker, start_date, end_date)
    monthly_bench = align_to_dates(raw_prices, df['Date'])

    # Annualized benchmark return
    ann_ret_bench = annualize_return(monthly_bench)
    bench_arr = monthly_bench.to_numpy()

    # Initial AUM input
    initial_aum_str = st.text_input("Initial AUM", value=f"{config.DEFAULT_AUM:,.2f}")
     try:
         initial_aum = parse_aum(initial_aum_str)
     except ValueError as e:
         st.error(str(e))
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
                            "Upper threshold (decimal)",
                            min_value=0.0, max_value=1.0,
                            value=0.01*(t+1),
                            key=f"thresh_{i}_{t}"
                        )
                    else:
                        thresh = None
                    share = st.number_input(
                        "Manager share (0-1)",
                        min_value=0.0, max_value=1.0,
                        value=0.5,
                        key=f"share_{i}_{t}"
                    )
                    tiers.append({'threshold': thresh, 'manager_share': share})
            else:
                mgmt   = st.number_input(
                    "Mgmt fee % (annual)",
                    min_value=0.0, max_value=5.0,
                    value=2.0, key=f"mgmt_{i}"
                ) / 100
                perf   = st.number_input(
                    "Perf fee %",
                    min_value=0.0, max_value=100.0,
                    value=20.0, key=f"perf_{i}"
                ) / 100
                hurdle = st.number_input(
                    "Hurdle rate % (annual)",
                    min_value=0.0, max_value=10.0,
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
            # 1) Compute tracking error
            te = tracking_error(net_arr, bench_arr)

            # 2) Compute Information Ratio
            ir = information_ratio(metrics['Annualized Return'], ann_ret_bench, te)

            # 3) Compute Beta
            b  = calc_beta(net_arr, bench_arr)

            metrics['Information Ratio'] = ir
            metrics['Beta']              = b
            metrics['Tracking Error'] = te

            metrics['Scheme'] = name
            perf_list.append(metrics)

        perf_df = pd.DataFrame(perf_list).set_index('Scheme')
        perf_df = perf_df[
            ['Annualized Return',
             'Annualized Volatility',
             'Beta',
             'Sharpe Ratio',
             'Sortino Ratio',
             'Information Ratio']
        ]
        st.subheader("Risk-Adjusted Return Statistics")
        st.dataframe(perf_df)

        # Yearly Net Returns vs Benchmark
        st.markdown("---")
        st.subheader("Yearly Net Returns vs Benchmark")
        
        # Yearly Net Returns vs Benchmark
        st.markdown("---")
        st.subheader("Yearly Net Returns vs Benchmark")
        
        yearly_dict = {
            name: yearly_returns(data['monthly']['NetReturn'])
            for name, data in results.items()
        }
        yearly_dict['Benchmark'] = yearly_returns(monthly_bench)
        
        # Build and display
        yearly_df = pd.concat(yearly_dict, axis=1).sort_index()
        st.dataframe(yearly_df)

        # Ensure each entry is 1-D:
        for k, v in yearly_dict.items():
            if isinstance(v, pd.DataFrame):
                yearly_dict[k] = v.squeeze()
            elif isinstance(v, np.ndarray) and v.ndim == 2:
                yearly_dict[k] = v.flatten()
        
        # Build via concat
        yearly_df = pd.concat(yearly_dict, axis=1).sort_index()
        st.dataframe(yearly_df)

