# feesim/engine.py
"""
Core fee-simulation and performance analytics engine.
Extracted from Streamlit app for reuse and testability.
"""
import pandas as pd
import numpy as np


def calculate_scheme(df: pd.DataFrame, scheme: dict, initial_aum: float):
    """
    Given a DataFrame `df` with Date and GrossReturn, a fee scheme dict, and initial AUM,
    returns (monthly_df, annual_rev_df).
    """
    records = []
    aum = initial_aum
    hwm_value = initial_aum

    for row in df.itertuples(index=False):
        aum_start = aum
        gross = float(row.GrossReturn)

        # Management fee (prorated monthly)
        mgmt_rev = scheme.get('mgmt', 0) / 12 * aum_start
        aum_after = aum_start * (1 + gross)

        # Determine gain subject to HWM or baseline
        gain_excess = max(0, aum_after - (hwm_value if scheme.get('hwm', False) else aum_start))

        # Performance fee
        perf_rev = 0.0
        if scheme.get('tiered', False) and gain_excess > 0:
            prop = gain_excess / aum_start
            remaining = prop
            fee_prop = 0.0
            lower = 0.0
            for tier in scheme['tiers']:
                upper = tier['threshold'] if tier['threshold'] is not None else float('inf')
                slice_width = min(upper - lower, remaining)
                if slice_width <= 0:
                    break
                fee_prop += slice_width * tier['manager_share']
                remaining -= slice_width
                lower = upper
            perf_rev = fee_prop * aum_start
        elif not scheme.get('tiered', False) and gain_excess > 0:
            monthly_hurdle = scheme.get('hurdle', 0) / 12
            perf_rev = scheme.get('perf', 0) * max(0, gross - monthly_hurdle) * aum_start

        # Deduct fees & update AUM
        aum_end = aum_after - mgmt_rev - perf_rev
        if scheme.get('hwm', False):
            hwm_value = max(hwm_value, aum_end)

        # Net return after fees
        net_return = (aum_end / aum_start) - 1

        records.append({
            'Date': row.Date,
            'GrossReturn': gross,
            'NetReturn': net_return,
            'MgmtFeeRevenue': mgmt_rev,
            'PerfFeeRevenue': perf_rev,
            'AUM_End': aum_end
        })
        aum = aum_end

    monthly_df = pd.DataFrame(records)
    monthly_df['Year'] = monthly_df['Date'].dt.year
    annual_rev = monthly_df.groupby('Year').agg({
        'MgmtFeeRevenue': 'sum',
        'PerfFeeRevenue': 'sum'
    }).rename(columns={'MgmtFeeRevenue': 'AnnualMgmtRev', 'PerfFeeRevenue': 'AnnualPerfRev'})
    annual_rev['TotalFeeRev'] = annual_rev['AnnualMgmtRev'] + annual_rev['AnnualPerfRev']
    return monthly_df, annual_rev


def performance_metrics(monthly_net: pd.Series, rf: float = 0.025):
    """
    Calculate annualized return, volatility, Sharpe, and Sortino for a series of monthly net returns.
    """
    # Annualized return
    periods = len(monthly_net)
    ann_ret = (monthly_net.add(1).prod()) ** (12/periods) - 1
    # Annualized volatility
    ann_vol = monthly_net.std(ddof=0) * np.sqrt(12)
    # Sharpe
    sharpe = (ann_ret - rf) / ann_vol if ann_vol else np.nan
    # Downside deviation
    downside = monthly_net[monthly_net < 0]
    dd = np.sqrt((downside**2).mean()) * np.sqrt(12) if len(downside) > 0 else 0.0
    sortino = (ann_ret - rf) / dd if dd else np.nan
    return {
        'Annualized Return': ann_ret,
        'Annualized Volatility': ann_vol,
        'Sharpe Ratio': sharpe,
        'Sortino Ratio': sortino
    }
