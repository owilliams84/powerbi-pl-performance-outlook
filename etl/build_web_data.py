"""Emit the compact JSON the milestonebi.com page reads.

**Aggregate only, on purpose.** The source ledger is Kaggle's "Data files (c) Original Authors",
which grants no redistribution licence, so no GL line and no account-level figure leaves this
script. What it writes is the statement as published: the 21 reporting lines the report already
shows on screen and in this repository's README, revenue by month, and EBITDA variance by
business unit. That is a summary of a 27,909-line ledger, not the ledger.

Every figure is computed with the same definitions as the DAX measures - the same TREATAS line
-> account mapping, the same display-sign flip, the same YTD window at the October close - so the
page and the report agree to the thousand.

    python etl/build_web_data.py [-o <path>]

Writes web/pl-performance-outlook.json by default.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

CURRENT_FY = 2020
PRIOR_FY = 2019
CLOSE_MONTH = 10          # actuals complete through October
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def read(name: str) -> list[dict]:
    with open(DATA / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=str(ROOT / "web" / "pl-performance-outlook.json"))
    args = ap.parse_args()

    if not DATA.exists():
        raise SystemExit(f"missing {DATA} - run etl/build_star_schema.py first (see README).")

    lines = read("dim_pl_line.csv")
    bridge = read("bridge_pl_account.csv")
    units = read("dim_business_unit.csv")
    fact = read("fact_pl.csv")

    # line -> the accounts that roll into it. A subtotal maps to every account beneath it, which
    # is exactly what TREATAS pushes onto Account in the model.
    accounts_for: dict[int, set[int]] = defaultdict(set)
    for b in bridge:
        accounts_for[int(b["PL Sort"])].add(int(b["Account_key"]))

    unit_of = {int(u["Territory_key"]): u["Business Unit"] for u in units}
    region_of = {int(u["Territory_key"]): u["Region"] for u in units}

    # (scenario, year, month, account) -> amount, and the same split by territory.
    by_acct: dict[tuple, float] = defaultdict(float)
    by_acct_unit: dict[tuple, float] = defaultdict(float)
    for r in fact:
        year, month = int(r["Date"][:4]), int(r["Date"][5:7])
        acct, terr = int(r["Account_key"]), int(r["Territory_key"])
        amt = float(r["Amount"])
        by_acct[(r["Scenario"], year, month, acct)] += amt
        by_acct_unit[(r["Scenario"], year, month, acct, terr)] += amt

    def total(scenario: str, year: int, months: range, accts: set[int], terr: int | None = None) -> float:
        out = 0.0
        for m in months:
            for a in accts:
                if terr is None:
                    out += by_acct.get((scenario, year, m, a), 0.0)
                else:
                    out += by_acct_unit.get((scenario, year, m, a, terr), 0.0)
        return out

    full, ytd = range(1, 13), range(1, CLOSE_MONTH + 1)
    rows = []
    for ln in lines:
        srt = int(ln["PL Sort"])
        accts = accounts_for.get(srt, set())
        sign = int(ln["Display Sign"])
        is_margin = ln["Row Type"] == "Margin"

        def k(scenario: str, year: int, months: range) -> float:
            return total(scenario, year, months, accts) * sign / 1000.0

        bud_fy, fc_fy = k("Budget", CURRENT_FY, full), k("Forecast", CURRENT_FY, full)
        ac_ytd, bud_ytd = k("Actual", CURRENT_FY, ytd), k("Budget", CURRENT_FY, ytd)
        py_ytd = k("Actual", PRIOR_FY, ytd)

        if is_margin:
            # A margin row carries its parent subtotal's accounts, so the ratio's numerator is
            # this line and the denominator is Revenue in the same scenario and window.
            rev = accounts_for[10]

            def ratio(scenario: str, year: int, months: range) -> float | None:
                den = total(scenario, year, months, rev) / 1000.0
                return None if not den else k(scenario, year, months) / den

            row = {"line": ln["PL Line"].strip(), "level": int(ln["Level"]), "type": "Margin",
                   "sign": 1,
                   "budFY": ratio("Budget", CURRENT_FY, full),
                   "fcFY": ratio("Forecast", CURRENT_FY, full),
                   "acYTD": ratio("Actual", CURRENT_FY, ytd),
                   "budYTD": ratio("Budget", CURRENT_FY, ytd),
                   "pyYTD": ratio("Actual", PRIOR_FY, ytd)}
            # Margin variances are percentage points, not a percentage change.
            row["varBUD"] = (None if row["fcFY"] is None or row["budFY"] is None
                             else round((row["fcFY"] - row["budFY"]) * 100, 1))
            row["varYTD"] = (None if row["acYTD"] is None or row["budYTD"] is None
                             else round((row["acYTD"] - row["budYTD"]) * 100, 1))
            for f in ("budFY", "fcFY", "acYTD", "budYTD", "pyYTD"):
                row[f] = None if row[f] is None else round(row[f], 4)
            rows.append(row)
            continue

        rows.append({
            "line": ln["PL Line"].strip(), "level": int(ln["Level"]), "type": ln["Row Type"],
            # -1 on cost lines. The page colours a variance with variance x sign > 0, which is
            # the same rule the report's Display Sign encodes: "spent less than planned" is good
            # on a cost line and bad on a revenue line, with no per-line exception list.
            "sign": sign,
            "budFY": round(bud_fy), "fcFY": round(fc_fy),
            "varBUD": round(fc_fy - bud_fy),
            "varBUDpct": None if not bud_fy else round(fc_fy / bud_fy - 1, 4),
            "acYTD": round(ac_ytd), "budYTD": round(bud_ytd),
            "varYTD": round(ac_ytd - bud_ytd),
            "varYTDpct": None if not bud_ytd else round(ac_ytd / bud_ytd - 1, 4),
            "pyYTD": round(py_ytd),
            "yoyPct": None if not py_ytd else round(ac_ytd / py_ytd - 1, 4),
            "fcToGo": round(fc_fy - ac_ytd),
            "budToGo": round(bud_fy - bud_ytd),
        })

    by_line = {r["line"]: r for r in rows}
    rev_accts, ebitda_accts = accounts_for[10], accounts_for[110]

    monthly = {
        "months": MONTHS,
        "budget": [round(total("Budget", CURRENT_FY, range(m, m + 1), rev_accts) / 1000) for m in range(1, 13)],
        "forecast": [round(total("Forecast", CURRENT_FY, range(m, m + 1), rev_accts) / 1000) for m in range(1, 13)],
        # Actual stops at the close, and is left short rather than zero-filled: a zero would draw
        # a line to the floor in November and read as a collapse.
        "actual": [round(total("Actual", CURRENT_FY, range(m, m + 1), rev_accts) / 1000)
                   for m in range(1, CLOSE_MONTH + 1)],
        "closeMonth": CLOSE_MONTH,
    }

    variance = []
    for terr, name in sorted(unit_of.items()):
        bud = total("Budget", CURRENT_FY, full, ebitda_accts, terr) / 1000.0
        fc = total("Forecast", CURRENT_FY, full, ebitda_accts, terr) / 1000.0
        variance.append({"unit": name, "region": region_of[terr],
                         "budFY": round(bud), "fcFY": round(fc), "varBUD": round(fc - bud)})
    variance.sort(key=lambda v: v["varBUD"])

    out = {
        "meta": {
            "source": "https://github.com/owilliams84/powerbi-pl-performance-outlook",
            "year": CURRENT_FY, "priorYear": PRIOR_FY,
            "closeMonth": MONTHS[CLOSE_MONTH - 1],
            "units": "$000",
            "glLines": 27909, "accounts": 26, "businessUnits": len(unit_of),
        },
        "headline": {
            "revenueFC": by_line["Revenue"]["fcFY"],
            "ebitdaFC": by_line["EBITDA"]["fcFY"],
            "ebitdaMarginFC": by_line["EBITDA %"]["fcFY"],
            "ebitdaVarBUD": by_line["EBITDA"]["varBUD"],
            "ebitdaVarBUDpct": by_line["EBITDA"]["varBUDpct"],
            "netIncomeFC": by_line["Net Income"]["fcFY"],
            "revenueVarBUDpct": by_line["Revenue"]["varBUDpct"],
            "opexVarBUDpct": by_line["Operating Expenses"]["varBUDpct"],
        },
        "statement": rows,
        "monthly": monthly,
        "variance": variance,
    }

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8", newline="\n")
    h = out["headline"]
    print(f"wrote {dest} ({dest.stat().st_size / 1024:.0f} KB)")
    print(f"  revenue {h['revenueFC']:,} | EBITDA {h['ebitdaFC']:,} "
          f"({h['ebitdaMarginFC']:.1%}) | vs budget {h['ebitdaVarBUD']:,} "
          f"({h['ebitdaVarBUDpct']:.1%}) | net income {h['netIncomeFC']:,}")
    print(f"  {len(rows)} statement lines, {len(variance)} business units")

    # The statement must foot, exactly as the ETL asserts and the report shows.
    checks = [
        ("Gross Profit", ["Revenue", "Cost of Sales"], [1, -1]),
        ("EBITDA", ["Gross Profit", "Operating Expenses"], [1, -1]),
        ("EBIT", ["EBITDA", "Depreciation & Amortisation"], [1, -1]),
        ("Net Income", ["Earnings Before Taxes", "Taxes"], [1, -1]),
    ]
    for target, parts, signs in checks:
        got = by_line[target]["fcFY"]
        want = sum(s * by_line[p]["fcFY"] for p, s in zip(parts, signs))
        if abs(got - want) > 1:
            raise SystemExit(f"ERROR: {target} {got} != {' '.join(parts)} = {want}")
    print("  statement foots in the full-year view")


if __name__ == "__main__":
    main()
