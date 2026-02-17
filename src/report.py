from pathlib import Path
from datetime import datetime
import pandas as pd

def _safe_to_excel(df: pd.DataFrame, writer: pd.ExcelWriter, sheet_name: str):
    if df is None or (hasattr(df, "empty") and df.empty):
        pd.DataFrame({"note": [f"No data returned for {sheet_name}"]}).to_excel(
            writer, sheet_name=sheet_name, index=False
        )
    else:
        df.to_excel(writer, sheet_name=sheet_name)

def write_report(pkg: dict, ratios: dict, dcf: dict) -> str:
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    ticker = pkg.get("ticker", "TICKER")
    out = reports_dir / f"{ticker}_{ts}.xlsx"

    with pd.ExcelWriter(out, engine="openpyxl") as w:
        _safe_to_excel(pkg.get("income"), w, "Income")
        _safe_to_excel(pkg.get("balance"), w, "Balance")
        _safe_to_excel(pkg.get("cashflow"), w, "CashFlow")

        flat = {
            "asof": ratios.get("asof"),
            "revenue": ratios.get("revenue"),
            "net_income": ratios.get("net_income"),
            "fcf": ratios.get("fcf"),
            **{f"margin_{k}": v for k, v in (ratios.get("margins") or {}).items()},
            **{f"ret_{k}": v for k, v in (ratios.get("returns") or {}).items()},
            **{f"liq_{k}": v for k, v in (ratios.get("liquidity") or {}).items()},
            **{f"lev_{k}": v for k, v in (ratios.get("leverage") or {}).items()},
            **{f"yoy_{k}": v for k, v in (ratios.get("growth_yoy") or {}).items()},
            "net_debt": ratios.get("net_debt"),
        }
        if dcf and dcf.get("per_share") is not None:
            flat["dcf_per_share"] = dcf.get("per_share")

        pd.DataFrame([flat]).to_excel(w, sheet_name="Summary", index=False)

        # DCF detail
        if dcf and dcf.get("table") is not None and not getattr(dcf["table"], "empty", True):
            dcf["table"].to_excel(w, sheet_name="DCF", index=False)

        # DCF assumptions summary
        if dcf and dcf.get("assumptions"):
            assump = dcf["assumptions"].copy()
            assump.update({
                "enterprise_value": dcf.get("ev"),
                "equity_value": dcf.get("equity"),
                "terminal_value": dcf.get("tv"),
                "pv_terminal_value": dcf.get("pv_tv"),
                "per_share": dcf.get("per_share"),
            })
            pd.DataFrame([assump]).to_excel(w, sheet_name="DCF_Summary", index=False)

        # Sensitivity table (if included)
        sens = dcf.get("sensitivity") if isinstance(dcf, dict) else None
        if sens is not None and hasattr(sens, "to_excel"):
            sens.to_excel(w, sheet_name="Sensitivity")

    return str(out)
