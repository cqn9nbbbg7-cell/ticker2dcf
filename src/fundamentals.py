import pandas as pd
import yfinance as yf

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df = df.loc[~df.index.duplicated(keep="first")]
    df = df.reindex(sorted(df.columns, reverse=True), axis=1)
    return df

def get_pkg(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info or {}
    return {
        "ticker": ticker.upper(),
        "info": info,
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "income": _clean(t.financials),
        "balance": _clean(t.balance_sheet),
        "cashflow": _clean(t.cashflow),
    }
