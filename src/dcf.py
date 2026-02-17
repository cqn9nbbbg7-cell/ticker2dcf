import numpy as np
import pandas as pd

def _rate(x: float) -> float:
    """Allow users to pass 10 meaning 10%."""
    if x is None:
        return None
    return x / 100.0 if x > 1.5 else x

def simple_dcf(fcf0, shares, net_debt, wacc=0.10, g=0.06, tg=0.03, years=5):
    wacc = _rate(wacc)
    g = _rate(g)
    tg = _rate(tg)

    if fcf0 is None or shares is None or shares == 0:
        return {"error": "Missing FCF or shares."}
    if wacc is None or g is None or tg is None:
        return {"error": "Missing rate assumptions."}
    if wacc <= tg:
        return {"error": "WACC must be greater than terminal growth."}

    years = int(years)

    fcf = [fcf0 * ((1 + g) ** t) for t in range(1, years + 1)]
    disc = [(1 / ((1 + wacc) ** t)) for t in range(1, years + 1)]
    pv_fcf = [fcf[i] * disc[i] for i in range(years)]

    tv = (fcf[-1] * (1 + tg)) / (wacc - tg)
    pv_tv = tv / ((1 + wacc) ** years)

    ev = sum(pv_fcf) + pv_tv
    equity = ev - (0.0 if net_debt is None or np.isnan(net_debt) else net_debt)
    per_share = equity / shares

    table = pd.DataFrame({
        "Year": list(range(1, years + 1)),
        "FCF": fcf,
        "Discount_Factor": disc,
        "PV_FCF": pv_fcf,
    })

    return {
        "assumptions": {"wacc": wacc, "g": g, "tg": tg, "years": years},
        "ev": ev,
        "equity": equity,
        "per_share": per_share,
        "tv": tv,
        "pv_tv": pv_tv,
        "table": table,
    }

def dcf_sensitivity(fcf0, shares, net_debt, wacc_list, g_list, tg=0.03, years=5):
    tg = _rate(tg)
    years = int(years)

    cols = [ _rate(g) for g in g_list ]
    idx = [ _rate(w) for w in wacc_list ]

    grid = []
    for w in idx:
        row = []
        for g in cols:
            out = simple_dcf(fcf0, shares, net_debt, wacc=w, g=g, tg=tg, years=years)
            row.append(np.nan if "error" in out else out["per_share"])
        grid.append(row)

    df = pd.DataFrame(grid, index=idx, columns=cols)
    df.index.name = "WACC"
    df.columns.name = "5Y_Growth"
    return df
