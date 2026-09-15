"""Expected figures for the Against Plan page, computed in pandas from the star schema.

The page compares actuals for January to the October close with one of two comparisons: the
budget for the same months, or the prior year's actuals for the same months. Amounts are signed
as posted - income positive, costs negative - so for any account or line, actual minus comparison
is the effect on profit: positive is favourable whether the line is income or cost.

    python etl/comparison_expected.py                    # 2020 against budget
    python etl/comparison_expected.py 2020 prior         # 2020 against 2019
    python etl/comparison_expected.py 2020 budget West   # unused third arg ignored
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
TOP_N = 8


def load() -> tuple[pd.DataFrame, dict[str, list[int]]]:
    fact = pd.read_csv(DATA / "fact_pl.csv", parse_dates=["Date"])
    fact["Year"] = fact.Date.dt.year
    fact["Month"] = fact.Date.dt.month
    dates = pd.read_csv(DATA / "dim_date.csv", parse_dates=["Date"])
    fact = fact.merge(dates[["Date", "Is YTD"]], on="Date")
    fact = (fact.merge(pd.read_csv(DATA / "dim_business_unit.csv"), on="Territory_key")
                .merge(pd.read_csv(DATA / "dim_account.csv")[["Account_key", "SubAccount"]], on="Account_key"))
    lines = pd.read_csv(DATA / "dim_pl_line.csv", encoding="utf-8")
    bridge = pd.read_csv(DATA / "bridge_pl_account.csv")
    lines["PL Line"] = lines["PL Line"].str.replace(" ", "").str.strip()
    accounts = {row["PL Line"]: bridge.loc[bridge["PL Sort"] == row["PL Sort"], "Account_key"].tolist()
                for _, row in lines.iterrows()}
    return fact, accounts


def main() -> None:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2020
    choice = sys.argv[2] if len(sys.argv) > 2 else "budget"

    fact, accounts = load()
    ytd = fact[fact["Is YTD"] == 1]
    actual = ytd[(ytd.Scenario == "Actual") & (ytd.Year == year)]
    if choice == "budget":
        comp = ytd[(ytd.Scenario == "Budget") & (ytd.Year == year)]
        label = "budget"
    else:
        comp = ytd[(ytd.Scenario == "Actual") & (ytd.Year == year - 1)]
        label = str(year - 1)

    def line(df: pd.DataFrame, name: str) -> float:
        return float(df[df.Account_key.isin(accounts[name])].Amount.sum())

    def by(df: pd.DataFrame, key: str, name: str | None = None) -> pd.Series:
        d = df if name is None else df[df.Account_key.isin(accounts[name])]
        return d.groupby(key).Amount.sum()

    out: dict = {"year": year, "comparison": label}
    for name in ["Revenue", "Gross Profit", "EBITDA", "Net Income"]:
        a, c = line(actual, name), line(comp, name)
        out[name] = {"actual": round(a, 2), "comparison": round(c, 2), "variance": round(a - c, 2),
                     "pct": round((a - c) / abs(c), 4) if c else None}
    out["ebitda_margin"] = round(out["EBITDA"]["actual"] / out["Revenue"]["actual"], 4)
    out["ebitda_margin_comp"] = round(out["EBITDA"]["comparison"] / out["Revenue"]["comparison"], 4)
    out["gross_margin"] = round(out["Gross Profit"]["actual"] / out["Revenue"]["actual"], 4)
    out["gross_margin_comp"] = round(out["Gross Profit"]["comparison"] / out["Revenue"]["comparison"], 4)

    for name in ["Revenue", "EBITDA"]:
        a, c = by(actual, "Month", name), by(comp, "Month", name)
        m = pd.DataFrame({"actual": a, "comparison": c}).reindex(range(1, 11)).fillna(0.0)
        out[f"monthly_{name.lower()}"] = [
            {"month": int(k), "actual": round(r.actual, 2), "comparison": round(r.comparison, 2),
             "variance": round(r.actual - r.comparison, 2)} for k, r in m.iterrows()]

    a, c = by(actual, "Business Unit", "EBITDA"), by(comp, "Business Unit", "EBITDA")
    bu = pd.DataFrame({"actual": a, "comparison": c}).fillna(0.0)
    bu["variance"] = bu.actual - bu.comparison
    bu["pct"] = bu.variance / bu.comparison.abs()
    bu = bu.sort_values("variance", ascending=False)
    out["business_units"] = [{"name": k, "actual": round(r.actual, 2), "comparison": round(r.comparison, 2),
                              "variance": round(r.variance, 2), "pct": round(r.pct, 4)}
                             for k, r in bu.iterrows()]
    out["bu_ahead"] = int((bu.variance > 0).sum())

    a, c = by(actual, "SubAccount"), by(comp, "SubAccount")
    acc = pd.DataFrame({"actual": a, "comparison": c}).fillna(0.0)
    acc = acc[(acc.actual != 0) | (acc.comparison != 0)]
    acc["effect"] = acc.actual - acc.comparison
    acc["pct"] = acc.effect / acc.comparison.abs().where(acc.comparison != 0)
    acc = acc.sort_values("effect", ascending=False)

    def rows(df: pd.DataFrame) -> list[dict]:
        return [{"name": k, "actual": round(abs(r.actual), 2), "comparison": round(abs(r.comparison), 2),
                 "effect": round(r.effect, 2), "pct": None if pd.isna(r.pct) else round(r.pct, 4)}
                for k, r in df.iterrows()]

    out["accounts_in_play"] = len(acc)
    out["accounts_favourable"] = int((acc.effect > 0).sum())
    out["accounts_top"] = rows(acc.head(TOP_N))
    out["accounts_bottom"] = rows(acc.tail(TOP_N).iloc[::-1])
    out["accounts_all"] = [{"name": k, "effect": round(r.effect, 2)} for k, r in acc.iterrows()]
    out["max_abs_account_effect"] = round(float(acc.effect.abs().max()), 2)
    out["max_abs_bu_variance"] = round(float(bu.variance.abs().max()), 2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
