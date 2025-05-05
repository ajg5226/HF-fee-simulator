import pandas as pd


def read_validate_csv(uploaded, required_columns=None) -> pd.DataFrame:
    """
    Read an uploaded CSV file into a DataFrame, parse dates, sort by Date, and validate required columns.

    Args:
        uploaded:   File-like object (e.g. Streamlit UploadedFile).
        required_columns: list of column names that must be present (default ['Date','GrossReturn']).

    Returns:
        Cleaned pandas DataFrame.

    Raises:
        ValueError: If the file cannot be read or required columns are missing.
    """
    # Default required columns if not provided
    if required_columns is None:
        required_columns = ['Date', 'GrossReturn']

    try:
        df = pd.read_csv(uploaded, parse_dates=['Date'])
    except Exception as e:
        raise ValueError(f"Error reading CSV: {e}")

    # Ensure chronological order
    df.sort_values('Date', inplace=True)

    # Validate presence of required columns
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

    return df


def parse_aum(aum_str: str) -> float:
    """
    Parse a formatted AUM string (with commas) into a float.

    Args:
        aum_str: String representing AUM, e.g. '100,000,000.00'.

    Returns:
        A float value of the AUM.

    Raises:
        ValueError: If the input cannot be converted to a float.
    """
    try:
        # Remove commas and convert to float
        value = float(aum_str.replace(",", ""))
    except Exception:
        raise ValueError("Invalid AUM format. Please enter a number like 100,000,000.00")
    return value
