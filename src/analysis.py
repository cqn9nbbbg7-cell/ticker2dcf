import numpy as np
import pandas as pd

def _get(df: pd.DataFrame, name: str, col):
    if df is None or df.empty or name not in df.index:
        return np.nan
    try:
        return float(df.loc[name, col])
    except Exception:
        return np.nan

def _first_available(df: pd.DataFrame, names, col):
    for name in names:
        if df is not None and not df.empty and name in df.index:
            v = _get(df, name, col)
            if not pd.isna(v):
                return v
    return np.nan

def _div(a, b):
    if a is None or b is None or pd.isna(a) or pd.isna(b) or b == 0:
        return np.nan
    return a / b

def compute_ratios(pkg: dict) -> dict:
    inc = pkg.get("income")
    bal = pkg.get("balance")
    cf  = pkg.get("cashflow")

    # choose latest column available
    col = None
    for df in (inc, bal, cf):
        if df is not None and not df.empty:
            col = df.columns[0]
            break
    if col is None:
        return {"error": "No annual statement data returned for this ticker."}

    # --- Income ---
    revenue = _first_available(inc, ["Total Revenue", "Operating Revenue"], col)
    gross_profit = _first_available(inc, ["Gross Profit"], col)
    ebit = _first_available(inc, ["EBIT", "Ebit", "Operating Income"], col)
    net_income = _first_available(inc, ["Net Income", "Net Income Common Stockholders"], col)

    # --- Balance ---
    total_assets = _first_available(bal, ["Total Assets"], col)
    total_liab = _first_available(bal, ["Total Liabilities Net Minority Interest", "Total Liabilities"], col)
    total_equity = _first_available(
        bal,
        ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest", "Total Stockholder Equity"],
        col
    )

    curr_assets = _first_available(bal, ["Current Assets", "Total Current Assets"], col)
    curr_liab = _first_available(bal, ["Current Liabilities", "Total Current Liabilities"], col)

    # debt + net debt (best available)
    total_debt = _first_available(
        bal,
        ["Total Debt", "Long Term Debt And Capital Lease Obligation", "Long Term Debt", "Current Debt And Capital Lease Obligation"],
        col
    )
    net_debt = _first_available(bal, ["Net Debt"], col)

    # If Net Debt missing, approximate using cash if possible
    cash = _first_available(bal, ["Cash And Cash Equivalents", "Cash", "Cash Cash Equivalents And Short Term Investments"], col)
    if pd.isna(net_debt) and not pd.isna(total_debt) and not pd.isna(cash):
        net_debt = total_debt - cash

    # --- Cash Flow (FCF) ---
    op_cf = _first_available(
        cf,
        [
            "Operating Cash Flow",
            "Net Cash Provided By Operating Activities",
            "Total Cash From Operating Activities",
        ],
        col
    )
    capex = _first_available(
        cf,
        [
            "Capital Expenditure",
            "Capital Expenditures",
            "Purchase Of PPE",
            "Purchase Of Property Plant Equipment",
            "Payments For Property Plant And Equipment",
        ],
        col
    )

    # capex often negative already; if it comes in positive, treat as outflow
    if not pd.isna(capex) and capex > 0:
        capex = -capex

    fcf = op_cf + capex if (not pd.isna(op_cf) and not pd.isna(capex)) else np.nan

    # --- YoY growth ---
    def yoy(series_names, df):
        if df is None or df.empty or df.shape[1] < 2:
            return np.nan
        # pick first series that exists
        name = None
        for s in series_names:
            if s in df.index:
                name = s
                break
        if name is None:
            return np.nan
        latest = _get(df, name, df.columns[0])
        prev = _get(df, name, df.columns[1])
        return _div(latest - prev, prev)

    return {
        "asof": str(col.date()) if hasattr(col, "date") else str(col),
        "revenue": revenue,
        "net_income": net_income,
        "fcf": fcf,
        "margins": {
            "gross_margin": _div(gross_profit, revenue),
            "ebit_margin": _div(ebit, revenue),
            "net_margin": _div(net_income, revenue),
            "fcf_margin": _div(fcf, revenue),
        },
        "returns": {
            "ROA": _div(net_income, total_assets),
            "ROE": _div(net_income, total_equity),
        },
        "liquidity": {
            "current_ratio": _div(curr_assets, curr_liab),
        },
        "leverage": {
            "debt_to_equity": _div(total_debt, total_equity),
            "liab_to_assets": _div(total_liab, total_assets),
        },
        "growth_yoy": {
            "rev_yoy": yoy(["Total Revenue", "Operating Revenue"], inc),
            "ni_yoy": yoy(["Net Income", "Net Income Common Stockholders"], inc),
        },
        "net_debt": net_debt,
    }
