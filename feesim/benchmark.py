import pandas as pd
import yfinance as yf


def fetch_monthly_prices(ticker: str, start: str, end: str) -> pd.Series:
    """
    Download monthly adjusted-close prices for `ticker` between `start` and `end`.

    Args:
        ticker: Stock ticker symbol (e.g. 'SPY').
        start:  Start date in 'YYYY-MM-DD' format.
        end:    End date in 'YYYY-MM-DD' format.

    Returns:
        A pandas Series of monthly prices, indexed by normalized Timestamp.

    Raises:
        ValueError: If no data is returned or the 'Close' column is missing.
    """
    data = yf.download(
        ticker,
        start=start,
        end=end,
        interval="1mo",
        auto_adjust=True,
        progress=False
    )
    if data.empty or 'Close' not in data.columns:
        raise ValueError(f"No Close price data returned for ticker '{ticker}'")
    prices = data['Close'].copy()
    # Normalize index to midnight for consistent alignment
    prices.index = pd.to_datetime(prices.index).normalize()
    return prices


def align_to_dates(prices: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """
    Reindex the monthly `prices` Series to match the exact set of `dates`.
    Forward-fills missing values and fills any gaps with zeros.

    Args:
        prices: pandas Series of prices with a DatetimeIndex.
        dates:  DatetimeIndex from the fund's returns DataFrame.

    Returns:
        A pandas Series aligned to `dates`, with no NaNs.
    """
    # Normalize both index sets
    target_index = pd.to_datetime(dates).normalize()
    aligned = prices.reindex(target_index).ffill().fillna(0)
    return aligned
