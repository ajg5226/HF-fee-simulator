import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from io import BytesIO
from feesim.engine import calculate_scheme, performance_metrics


# Streamlit App
st.title("Hedge Fund Fee Simulator")

uploaded = st.file_uploader("Upload monthly returns CSV", type=['csv'])
if uploaded:
    df = pd.read_csv(uploaded, parse_dates=['Date'])
    df.sort_values('Date', inplace=True)

    # Initial AUM input
    initial_aum_str = st.text_input("Initial AUM", value="100,000,000.00")
    try:
        initial_aum = float(initial_aum_str.replace(",", ""))
    except ValueError:
        st.error("Invalid AUM format. Please enter a number like 100,000,000.00")
        st.stop()

    # Fee schemes configuration
    n_schemes = st.number_input("Number of fee schemes", min_value=1, max_value=3, value=1)
    schemes = []
    for i in range(int(n_schemes)):
        with st.expander(f"Scheme {i+1}"):
            name = st.text_input(f"Name (scheme {i+1})", value=f"Scheme {i+1}")
            hwm = st.checkbox("High-water mark", value=True, key=f"hwm_{i}")
            tiered = st.checkbox("Tiered waterfall", key=f"tiered_{i}")
            tiers = []
            mgmt = perf = hurdle = 0.0
            if tiered:
                n_tiers = st.number_input("Number of tiers", min_value=1, max_value=5, value=3, key=f"n_tiers_{i}")
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
                mgmt = st.number_input("Mgmt fee % (annual)", min_value=0.0, max_value=5.0, value=2.0, key=f"mgmt_{i}")/100
                perf = st.number_input("Perf fee %", min_value=0.0, max_value=100.0, value=20.0, key=f"perf_{i}")/100
                hurdle = st.number_input("Hurdle rate % (annual)", min_value=0.0, max_value=10.0, value=0.0, key=f"hurdle_{i}")/100
            schemes.append({
                'name': name,
                'hwm': hwm,
                'tiered': tiered,
                'tiers': tiers,
                'mgmt': mgmt,
                'perf': perf,
                'hurdle': hurdle
            })

    # Run Simulation
    if st.button("Run Simulation"):
        results = {}
        for scheme in schemes:
            monthly_df, annual_rev = calculate_scheme(df, scheme, initial_aum)
            results[scheme['name']] = {'monthly': monthly_df, 'annual': annual_rev}

        # Downloadable Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            for name, data in results.items():
                data['monthly'].to_excel(writer, sheet_name=f"{name}_Monthly", index=False)
                data['annual'].to_excel(writer, sheet_name=f"{name}_Annual")
        st.download_button("Download Excel Results", buffer.getvalue(), file_name="fee_simulator_results.xlsx")

        # Display Tables
        for name, data in results.items():
            st.subheader(f"{name} - Monthly Results")
            st.dataframe(data['monthly'])
            st.subheader(f"{name} - Annual Fee Revenue")
            st.dataframe(data['annual'])

        # AUM Over Time
        aum_df = pd.concat([
            res['monthly'].set_index('Date')['AUM_End'].rename(name)
            for name, res in results.items()
        ], axis=1)
        st.subheader("AUM Over Time")
        st.line_chart(aum_df)

        # Cumulative Net Return
        net_df = pd.concat([
            res['monthly'].set_index('Date')['NetReturn'].add(1).cumprod().rename(name)
            for name, res in results.items()
        ], axis=1)
        st.subheader("Cumulative Net Return")
        st.line_chart(net_df)

        # Grouped bar for Total Fee Revenue
        fee_rev = pd.concat([
            res['annual']['TotalFeeRev'].rename(name)
            for name, res in results.items()
        ], axis=1)
        fee_rev.index.name = 'Year'
        rev_melt = fee_rev.reset_index().melt(id_vars='Year', var_name='Scheme', value_name='TotalFeeRev')
        st.subheader("Annual Total Fee Revenue by Scheme")
        bar = alt.Chart(rev_melt).mark_bar().encode(
            x='Year:O', y='TotalFeeRev:Q', color='Scheme:N', column='Scheme:N'
        )
        st.altair_chart(bar, use_container_width=True)

        # Annual Fee Revenue Stats
        stats = pd.DataFrame({
            'MeanFeeRev': fee_rev.mean(),
            'StdDevFeeRev': fee_rev.std(),
            'CoeffVarFeeRev': fee_rev.std() / fee_rev.mean()
        })
        stats.index.name = 'Scheme'
        st.subheader("Annual Fee Revenue Statistics")
        st.dataframe(stats)

        # Coefficient of Variation Chart
        st.subheader("Coefficient of Variation of Annual Fee Revenue")
        st.bar_chart(stats['CoeffVarFeeRev'])

        # Mean of Annual Fee Revenue
        stats_reset = stats.reset_index()
        mean_chart = alt.Chart(stats_reset).mark_bar().encode(
            x='Scheme:N', y='MeanFeeRev:Q'
        )
        st.subheader("Mean of Annual Fee Revenue")
        st.altair_chart(mean_chart, use_container_width=True)

        # Standard Deviation of Annual Fee Revenue
        std_chart = alt.Chart(stats_reset).mark_bar().encode(
            x='Scheme:N', y='StdDevFeeRev:Q'
        )
        st.subheader("Standard Deviation of Annual Fee Revenue")
        st.altair_chart(std_chart, use_container_width=True)

        # Performance Statistics Table
        rf = 0.025
        perf_list = []
        for name, data in results.items():
            net = data['monthly']['NetReturn']
            periods = len(net)
            ann_ret = (net + 1).prod() ** (12/periods) - 1
            ann_vol = net.std(ddof=0) * np.sqrt(12)
            sharpe = (ann_ret - rf) / ann_vol if ann_vol else np.nan
            downside = net[net < 0]
            if len(downside) > 0:
                dd = np.sqrt((downside**2).mean()) * np.sqrt(12)
            else:
                dd = 0.0
            sortino = (ann_ret - rf) / dd if dd else np.nan
            perf_list.append({
                'Scheme': name,
                'Annualized Return': ann_ret,
                'Annualized Volatility': ann_vol,
                'Sharpe Ratio': sharpe,
                'Sortino Ratio': sortino
            })
        perf_df = pd.DataFrame(perf_list).set_index('Scheme')
        st.subheader("Risk-Adjusted Return Statistics")
        st.dataframe(perf_df)
