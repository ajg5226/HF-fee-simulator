import numpy as np
import pandas as pd


def tracking_error(net_returns: np.ndarray, bench_returns: np.ndarray) -> float:
    """
    Compute the annualized tracking error between strategy net returns and benchmark returns.

    Tracking error = std(net - bench) * sqrt(12)

    Args:
        net_returns:   1D numpy array of monthly net returns.
        bench_returns: 1D numpy array of monthly benchmark returns.

    Returns:
        Annualized tracking error as a float.
    """
    diff = net_returns - bench_returns
    return float(np.std(diff, ddof=0) * np.sqrt(12))


def information_ratio(net_ann: float, bench_ann: float, te: float) -> float:
    """
    Compute the Information Ratio.

    IR = (net_ann - bench_ann) / tracking_error

    Args:
        net_ann:   Annualized strategy return.
        bench_ann: Annualized benchmark return.
        te:        Annualized tracking error.

    Returns:
        Information Ratio, or NaN if te == 0.
    """
    if te == 0:
        return np.nan
    return float((net_ann - bench_ann) / te)


def beta(net_returns: np.ndarray, bench_returns: np.ndarray) -> float:
    """
    Compute the sample Beta of the strategy versus the benchmark.

    Beta = Cov(net, bench) / Var(bench), using ddof=1 (sample covariance).

    Args:
        net_returns:   1D numpy array of monthly net returns.
        bench_returns: 1D numpy array of monthly benchmark returns.

    Returns:
        Beta as a float, or NaN if benchmark variance is zero.
    """
    # sample covariance
    net_mean = np.mean(net_returns)
    bench_mean = np.mean(bench_returns)
    cov = np.sum((net_returns - net_mean) * (bench_returns - bench_mean)) / (len(net_returns) - 1)
    var_bench = np.sum((bench_returns - bench_mean) ** 2) / (len(bench_returns) - 1)
    if var_bench == 0:
        return np.nan
    return float(cov / var_bench)


def annualize_return(monthly_returns: pd.Series) -> float:
    """
    Annualize a series of monthly returns.

    Annualized return = (prod(1 + r) ** (12 / N)) - 1

    Args:
        monthly_returns: pandas Series of monthly returns.

    Returns:
        Annualized return as a float.
    """
    n = len(monthly_returns)
    growth = (monthly_returns + 1).prod()
    return float(growth ** (12 / n) - 1)


def yearly_returns(monthly_returns: pd.Series) -> pd.Series:
    """
    Compute yearly compounded returns from monthly returns.

    Groups by year and compounds each year's returns: (prod(1+r) - 1).

    Args:
        monthly_returns: pandas Series with a DatetimeIndex.

    Returns:
        pandas Series indexed by year, containing each year's compounded return.
    """
    yearly = (
        monthly_returns
          .groupby(monthly_returns.index.year)
          .apply(lambda x: (x + 1).prod() - 1)
    )
    yearly.index.name = 'Year'
    return yearly
