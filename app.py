import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

from feesim.utils import read_validate_csv, parse_aum
from feesim.benchmark import fetch_monthly_prices, align_to_dates
from feesim.engine import calculate_scheme, performance_metrics
from feesim.metrics import (
    tracking_error,
    information_ratio,
    beta as calc_beta,
    annualize_return,
    yearly_returns
)
from app_ui import (
    input_benchmark,
    input_fee_schemes,
    download_button,
    show_chart,
    show_altair,
    show_table
)
import config

st.title("Hedge Fund Fee Simulator")

with st.expander("ℹ️ Instructions", expanded=True):
    st.markdown("""
    **What this tool does:**  
    Simulates hedge‐fund net returns and fee revenue under up to three different fee structures, and compares performance to a benchmark.

    **How to use:**  
    1. **Upload** a CSV of monthly returns with columns:
       - `Date` in **YYYY-MM-DD** format  
       - `GrossReturn` as a decimal (e.g. `0.015` for 1.5%)  
    2. **Benchmark ticker:** (default SPY) – used to compute tracking error, beta, information ratio.  
    3. **Initial AUM:** starting assets under management (formatted with commas).  
    4. **Configure fee schemes:** up to 3, with options for management fees, performance fees, hurdles, tiered waterfalls, and high-water marks.  
    5. Click **Run Simulation** to generate:
       - Net‐return & fee‐revenue tables  
       - AUM & cumulative-return charts  
       - Risk-adjusted metrics (Sharpe, Sortino, Beta, IR)  
       - Yearly net returns vs. benchmark  
    6. **Download** your results as an Excel file for further analysis.
    """)

# 1) Upload & validate CSV
uploaded = st.file_uploader("Upload monthly returns CSV", type=['csv'])
if not uploaded:
    st.stop()

try:
    df = read_validate_csv(uploaded, config.REQUIRED_COLUMNS)
except ValueError as e:
    st.error(str(e))
    st.stop()

# 2) Inputs
bench_ticker = input_benchmark()
schemes      = input_fee_schemes()

# 3) Fetch & align benchmark **returns**, not just prices
start_date = df['Date'].min().strftime("%Y-%m-%d")
end_date   = df['Date'].max().strftime("%Y-%m-%d")
try:
    raw_prices    = fetch_monthly_prices(bench_ticker, start_date, end_date)
    bench_returns = raw_prices.pct_change().dropna()
    monthly_bench = align_to_dates(bench_returns, df['Date'])
except ValueError as e:
    st.error(str(e))
    st.stop()

ann_ret_bench = annualize_return(monthly_bench)
bench_arr     = monthly_bench.to_numpy()

# 4) Initial AUM
initial_aum_str = st.text_input("Initial AUM", value=f"{config.DEFAULT_AUM:,.2f}")
try:
    initial_aum = parse_aum(initial_aum_str)
except ValueError as e:
    st.error(str(e))
    st.stop()

# 5) Run simulation
if st.button("Run Simulation"):
    # 5a) Core simulation
    results = {}
    for scheme in schemes:
        monthly_df, annual_rev = calculate_scheme(df, scheme, initial_aum)
        results[scheme['name']] = {'monthly': monthly_df, 'annual': annual_rev}

    # 5b) Download
    download_button(results)

    # 5c) Charts & tables
    # AUM Over Time
    aum_df = pd.concat([
        res['monthly'].set_index('Date')['AUM_End'].rename(name)
        for name, res in results.items()
    ], axis=1)
    show_chart("AUM Over Time", aum_df, chart_type='line')

    # Cumulative Net Return
    net_df = pd.concat([
        res['monthly'].set_index('Date')['NetReturn'].add(1).cumprod().rename(name)
        for name, res in results.items()
    ], axis=1)
    show_chart("Cumulative Net Return", net_df, chart_type='line')

    # Annual Total Fee Revenue (Altair grouped bar)
    fee_rev = pd.concat([
        res['annual']['TotalFeeRev'].rename(name)
        for name, res in results.items()
    ], axis=1)
    fee_rev.index.name = 'Year'
    rev_melt = fee_rev.reset_index().melt(
        id_vars='Year', var_name='Scheme', value_name='TotalFeeRev'
    )
    chart = alt.Chart(rev_melt).mark_bar().encode(
        x='Year:O', y='TotalFeeRev:Q', color='Scheme:N', column='Scheme:N'
    )
    show_altair(chart)

    # Annual Fee Revenue Stats
    stats = pd.DataFrame({
        'MeanFeeRev':    fee_rev.mean(),
        'StdDevFeeRev':  fee_rev.std(),
        'CoeffVarFeeRev': fee_rev.std() / fee_rev.mean()
    })
    stats.index.name = 'Scheme'
    show_table("Annual Fee Revenue Statistics", stats)

    # Performance Statistics
    rf = config.RISK_FREE_RATE
    perf_list = []
    for name, data in results.items():
        net_ser = data['monthly']['NetReturn']
        net_arr = net_ser.to_numpy()

        # Use engine for Sharpe/Sortino etc.
        metrics = performance_metrics(net_ser, rf=rf)

        # Tracking error, Information Ratio, Beta
        te = tracking_error(net_arr, bench_arr)
        ir = information_ratio(metrics['Annualized Return'], ann_ret_bench, te)
        b  = calc_beta(net_arr, bench_arr)

        metrics['Beta']              = b
        metrics['Information Ratio'] = ir
        metrics['Scheme']            = name
        perf_list.append(metrics)

    perf_df = pd.DataFrame(perf_list).set_index('Scheme')[[
        'Annualized Return',
        'Annualized Volatility',
        'Beta',
        'Sharpe Ratio',
        'Sortino Ratio',
        'Information Ratio'
    ]]
    show_table("Risk-Adjusted Return Statistics", perf_df)

    # Yearly Net Returns vs Benchmark
    st.markdown("---")
    st.subheader("Yearly Net Returns vs Benchmark")
    
    # 1) Fund: compound each year's NetReturn
    yearly_dict = {
        name: yearly_returns(
            data['monthly'].set_index('Date')['NetReturn']
        )
        for name, data in results.items()
    }
    
    # 2) Benchmark: compound the raw monthly returns by year
    #    bench_returns = raw_prices.pct_change().dropna()
    bench_yearly = bench_returns.groupby(bench_returns.index.year) \
                                .apply(lambda x: (x + 1).prod() - 1)
    bench_yearly.index.name = 'Year'
    
    yearly_dict['Benchmark'] = bench_yearly
    
    # 3) Build & display
    yearly_df = pd.concat(yearly_dict, axis=1).sort_index()
    show_table("Yearly Net Returns vs Benchmark", yearly_df)
