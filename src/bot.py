import os
import numpy as np
import discord
from dotenv import load_dotenv

from fundamentals import get_pkg
from analysis import compute_ratios
from dcf import simple_dcf, dcf_sensitivity
from report import write_report

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

def _pct(x):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "n/a"
    return f"{x*100:.1f}%"

def _num(x):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "n/a"
    ax = abs(x)
    if ax >= 1e12: return f"{x/1e12:.2f}T"
    if ax >= 1e9:  return f"{x/1e9:.2f}B"
    if ax >= 1e6:  return f"{x/1e6:.2f}M"
    if ax >= 1e3:  return f"{x/1e3:.2f}K"
    return f"{x:.2f}"

def _rate(x):
    # allow 10 meaning 10%
    return x / 100.0 if x is not None and x > 1.5 else x

@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user} (slash commands synced)")

@tree.command(name="ping", description="Test that the bot is working.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Bot is working.", ephemeral=False)

@tree.command(name="val", description="Statements, ratios, DCF + Excel export. Optional DCF inputs.")
@discord.app_commands.describe(
    ticker="Stock ticker (e.g., AAPL)",
    wacc="Discount rate (e.g., 0.10 or 10)",
    g="5-year FCF growth (e.g., 0.06 or 6)",
    tg="Terminal growth (e.g., 0.03 or 3)",
    years="Forecast years (e.g., 5, 7, 10)"
)
async def val(
    interaction: discord.Interaction,
    ticker: str,
    wacc: float = 0.10,
    g: float = 0.06,
    tg: float = 0.03,
    years: int = 5,
):
    t = ticker.strip().upper()
    await interaction.response.defer(thinking=True)

    pkg = get_pkg(t)
    ratios = compute_ratios(pkg)
    if "error" in ratios:
        await interaction.followup.send(f"Error for **{t}**: {ratios['error']}")
        return

    info = pkg.get("info", {}) or {}
    shares = info.get("sharesOutstanding")
    price = pkg.get("price")
    fcf = ratios.get("fcf")
    net_debt = ratios.get("net_debt") or 0.0

    dcf = {}
    if shares and fcf is not None and not (isinstance(fcf, float) and np.isnan(fcf)):
        dcf = simple_dcf(
            fcf0=float(fcf),
            shares=float(shares),
            net_debt=float(net_debt) if net_debt is not None else 0.0,
            wacc=_rate(wacc),
            g=_rate(g),
            tg=_rate(tg),
            years=int(years),
        )

        # Add sensitivity grid (WACC x Growth)
        if "error" not in dcf:
            w_list = [max(0.01, _rate(wacc) - 0.02), max(0.01, _rate(wacc) - 0.01), _rate(wacc), _rate(wacc) + 0.01, _rate(wacc) + 0.02]
            g_list = [max(-0.20, _rate(g) - 0.03), max(-0.20, _rate(g) - 0.01), _rate(g), _rate(g) + 0.01, _rate(g) + 0.03]
            dcf["sensitivity"] = dcf_sensitivity(float(fcf), float(shares), float(net_debt), w_list, g_list, tg=_rate(tg), years=int(years))

    report_path = write_report(pkg, ratios, dcf)

    m = ratios.get("margins", {})
    gr = ratios.get("growth_yoy", {})
    lev = ratios.get("leverage", {})

    msg = "\n".join([
        f"**{t}** | Price: `{price if price is not None else 'n/a'}` | As of: `{ratios.get('asof','n/a')}`",
        f"Revenue: `{_num(ratios.get('revenue'))}` | Net Income: `{_num(ratios.get('net_income'))}` | FCF: `{_num(ratios.get('fcf'))}`",
        f"Margins — Gross `{_pct(m.get('gross_margin'))}` | EBIT `{_pct(m.get('ebit_margin'))}` | Net `{_pct(m.get('net_margin'))}` | FCF `{_pct(m.get('fcf_margin'))}`",
        f"Growth YoY — Rev `{_pct(gr.get('rev_yoy'))}` | NI `{_pct(gr.get('ni_yoy'))}`",
        f"Leverage — Debt/Equity `{_num(lev.get('debt_to_equity'))}` | Liab/Assets `{_num(lev.get('liab_to_assets'))}`",
    ])

    if dcf and dcf.get("per_share") is not None and "error" not in dcf:
        if isinstance(price, (int, float)) and price:
            upside = (dcf["per_share"] / price) - 1
            msg += f"\nDCF (simple): `{dcf['per_share']:.2f}` per share | Upside `{_pct(upside)}` | (WACC {100*_rate(wacc):.1f}%, g {100*_rate(g):.1f}%, tg {100*_rate(tg):.1f}%, years {int(years)})"
        else:
            msg += f"\nDCF (simple): `{dcf['per_share']:.2f}` per share | (WACC {100*_rate(wacc):.1f}%, g {100*_rate(g):.1f}%, tg {100*_rate(tg):.1f}%, years {int(years)})"
    elif dcf and dcf.get("error"):
        msg += f"\nDCF: n/a ({dcf['error']})"
    else:
        msg += "\nDCF: `n/a` (missing FCF or shares)."

    await interaction.followup.send(msg)
    await interaction.followup.send(file=discord.File(report_path))

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN missing in .env")
    client.run(TOKEN)
