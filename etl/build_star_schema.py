"""
Build a P&L star schema from the Kaggle 'General Ledger (Financial data set)' workbook.

Source : https://www.kaggle.com/datasets/irfansharif/generalledger  ("Data file for students.xlsx")
         27,909 real double-entry GL lines, 2018-01-01 .. 2020-12-31, 54-account chart of
         accounts, 7 territories.

ACTUAL  is taken verbatim from the GL - nothing is invented.
BUDGET  and FORECAST do not exist in the source (no public dataset carries plan data at
        account x entity x month grain). They are generated here deterministically from the
        actuals so the report has something honest to compare against. The rules are:

          Budget FY(n)  = FY(n-1) actual annual per account x territory
                          * a per-account-group planned growth rate
                          * a stable per-territory planning skew (mean 1.0)
                          spread over months on a *smoothed* FY(n-1) seasonality curve.
                          -> smooth, set once before the year, never revised.

          Forecast FY(n), close month = OCT:
                          Jan..Oct = actual (locked)
                          Nov..Dec = budget month * clamp(actual YTD / budget YTD, 0.7, 1.4)
                                     * a small re-forecast bias
                          -> "actuals through Oct + FC", exactly the snippet's semantics.
                          For a closed year, forecast == actual for all 12 months.

Everything is seeded, so re-running reproduces the same numbers.
"""

import csv
import hashlib
import os
from collections import defaultdict
from datetime import date, timedelta

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data")
SRC = os.path.join(OUT, "source", "Data file for students.xlsx")

CURRENT_FY = 2020          # the year the report lands on
PRIOR_FY = 2019
CLOSE_MONTH = 10           # actuals complete through October

# ---------------------------------------------------------------- planning assumptions
# Planned growth applied to the prior year's actual to set the budget.
BUDGET_GROWTH = {
    2019: {210: 1.42, 220: 1.20, 230: 1.40, 240: 1.35, 250: 1.25,
           260: 1.60, 270: 1.55, 280: 1.45, 290: 1.50, 300: 1.45, 310: 1.48,
           320: 1.50, 330: 1.52, 340: 1.50, 350: 1.45, 360: 1.40,
           370: 1.30, 380: 1.30, 390: 1.30, 400: 1.30,
           410: 1.20, 420: 1.10, 430: 1.10, 431: 1.20, 440: 1.25, 450: 1.40},
    2020: {210: 1.34, 220: 1.10, 230: 1.38, 240: 1.30, 250: 1.20,
           260: 1.55, 270: 1.50, 280: 1.42, 290: 1.45, 300: 1.40, 310: 1.44,
           320: 1.46, 330: 1.48, 340: 1.46, 350: 1.42, 360: 1.35,
           370: 1.28, 380: 1.28, 390: 1.28, 400: 1.28,
           410: 1.15, 420: 1.10, 430: 1.10, 431: 1.15, 440: 1.15, 450: 1.30},
}

# Reporting line each account rolls into, plus how the line is presented.
# display_sign = -1 flips naturally-negative cost accounts so costs print positive,
# the way the reference report shows them.
PL_STRUCTURE = [
    # sort, line,                 level, row_type,  display_sign, accounts
    (10,  "Revenue",              1, "Subtotal", 1,  [210, 220]),
    (20,  "External Revenue",     2, "Detail",   1,  [210]),
    (30,  "Sales Returns",        2, "Detail",   -1, [220]),
    (40,  "Cost of Sales",        1, "Detail",   -1, [230]),
    (50,  "Gross Profit",         1, "Subtotal", 1,  [210, 220, 230]),
    (60,  "Gross Margin %",       2, "Margin",   1,  []),
    (70,  "Operating Expenses",   1, "Subtotal", -1, [240, 250, 260, 270, 280,
                                                      290, 300, 310, 320, 330, 340, 350, 360]),
    (80,  "Indirect Labour",      2, "Detail",   -1, [240, 250]),
    (90,  "Marketing",            2, "Detail",   -1, [260, 270, 280]),
    (100, "General & Administration", 2, "Detail", -1, [290, 300, 310, 320, 330, 340, 350, 360]),
    (110, "EBITDA",               1, "Subtotal", 1,  [210, 220, 230, 240, 250, 260, 270, 280,
                                                      290, 300, 310, 320, 330, 340, 350, 360]),
    (120, "EBITDA %",             2, "Margin",   1,  []),
    (130, "Depreciation & Amortisation", 1, "Detail", -1, [370, 380, 390, 400]),
    (140, "EBIT",                 1, "Subtotal", 1,  [210, 220, 230, 240, 250, 260, 270, 280,
                                                      290, 300, 310, 320, 330, 340, 350, 360,
                                                      370, 380, 390, 400]),
    (150, "EBIT %",               2, "Margin",   1,  []),
    (160, "Net Financial Result", 1, "Detail",   1,  [410, 420, 430, 431, 440]),
    (170, "Earnings Before Taxes", 1, "Subtotal", 1, [210, 220, 230, 240, 250, 260, 270, 280,
                                                      290, 300, 310, 320, 330, 340, 350, 360,
                                                      370, 380, 390, 400, 410, 420, 430, 431, 440]),
    (180, "EBT %",                2, "Margin",   1,  []),
    (190, "Taxes",                1, "Detail",   -1, [450]),
    (200, "Net Income",           1, "Subtotal", 1,  [210, 220, 230, 240, 250, 260, 270, 280,
                                                      290, 300, 310, 320, 330, 340, 350, 360,
                                                      370, 380, 390, 400, 410, 420, 430, 431,
                                                      440, 450]),
    (210, "Net Income %",         2, "Margin",   1,  []),
]

MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def assert_structure_is_additive():
    """Every subtotal must be exactly the union of the lines that build up to it.

    Catches the classic P&L authoring bug where a subtotal silently drops an account
    and the statement stops footing.
    """
    acc = {line: set(accounts) for _, line, _, _, _, accounts in PL_STRUCTURE}
    ladder = [
        ("Gross Profit", ["Revenue", "Cost of Sales"]),
        ("Revenue", ["External Revenue", "Sales Returns"]),
        ("Operating Expenses", ["Indirect Labour", "Marketing", "General & Administration"]),
        ("EBITDA", ["Gross Profit", "Operating Expenses"]),
        ("EBIT", ["EBITDA", "Depreciation & Amortisation"]),
        ("Earnings Before Taxes", ["EBIT", "Net Financial Result"]),
        ("Net Income", ["Earnings Before Taxes", "Taxes"]),
    ]
    for total, parts in ladder:
        union = set().union(*(acc[p] for p in parts))
        if union != acc[total]:
            raise AssertionError(
                f"'{total}' does not foot: missing {sorted(acc[total] ^ union)} "
                f"(vs {' + '.join(parts)})")

    # No account may be double-counted inside a subtotal's own components.
    for total, parts in ladder:
        seen = set()
        for p in parts:
            if seen & acc[p]:
                raise AssertionError(f"'{total}': account {sorted(seen & acc[p])} counted twice")
            seen |= acc[p]

    # The six building-block lines must together account for every P&L account exactly once.
    blocks = ["Revenue", "Cost of Sales", "Operating Expenses",
              "Depreciation & Amortisation", "Net Financial Result", "Taxes"]
    seen = set()
    for b in blocks:
        if seen & acc[b]:
            raise AssertionError(f"'{b}' overlaps an earlier building block: {sorted(seen & acc[b])}")
        seen |= acc[b]
    if seen != acc["Net Income"]:
        raise AssertionError(
            f"Building blocks do not cover Net Income: {sorted(seen ^ acc['Net Income'])}")
    print("Structure check: all subtotals foot, no double counting.")


def jitter(lo, hi, *parts):
    """Deterministic pseudo-random factor in [lo, hi) keyed on the given parts."""
    h = hashlib.md5("|".join(str(p) for p in parts).encode()).digest()
    frac = int.from_bytes(h[:6], "big") / float(1 << 48)
    return lo + frac * (hi - lo)


def load_source():
    wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)

    coa = {}
    for r in wb["Chart of Accounts"].iter_rows(min_row=2, values_only=True):
        if r[0] is None:
            continue
        coa[r[0]] = {"account_key": r[0], "report": r[1], "class": r[2],
                     "subclass": r[3], "subclass2": r[4], "account": r[5], "subaccount": r[6]}

    terr = {}
    for r in wb["Territory"].iter_rows(min_row=2, values_only=True):
        if r[0] is None:
            continue
        terr[r[0]] = {"territory_key": r[0], "country": r[1], "region": r[2]}

    # actual[(year, month, account, territory)] = amount, P&L accounts only
    actual = defaultdict(float)
    for r in wb["GL"].iter_rows(min_row=2, values_only=True):
        if r[0] is None:
            continue
        acct = coa.get(r[3])
        if not acct or acct["report"] != "Profit and Loss":
            continue
        d = r[1]
        actual[(d.year, d.month, r[3], r[2])] += float(r[5] or 0)

    wb.close()
    return coa, terr, actual


def seasonality(actual, year, account, territory):
    """Smoothed monthly profile of a line from a given year; falls back to flat."""
    vals = [actual.get((year, m, account, territory), 0.0) for m in range(1, 13)]
    total = sum(vals)
    if total == 0:
        return [1 / 12] * 12
    # 50% of the real shape, 50% flat -> a plan curve, not a replay of last year's noise
    return [0.5 * (v / total) + 0.5 / 12 for v in vals]


def build_budget(actual, year):
    """Budget FY(year), built from FY(year-1) actuals."""
    growth = BUDGET_GROWTH[year]
    prior = year - 1
    budget = {}

    pairs = {(a, t) for (y, m, a, t) in actual if y == prior}
    for account, territory in pairs:
        prior_annual = sum(actual.get((prior, m, account, territory), 0.0) for m in range(1, 13))
        if prior_annual == 0:
            continue
        skew = jitter(0.90, 1.10, "terr-skew", year, account, territory)
        annual = prior_annual * growth.get(account, 1.25) * skew
        profile = seasonality(actual, prior, account, territory)
        for m in range(1, 13):
            budget[(year, m, account, territory)] = annual * profile[m - 1]
    return budget


def build_forecast(actual, budget, year, close_month):
    """Actuals to the close month, re-forecast beyond it."""
    forecast = {}
    keys = {(a, t) for (y, m, a, t) in actual if y == year} | \
           {(a, t) for (y, m, a, t) in budget if y == year}

    for account, territory in keys:
        act_ytd = sum(actual.get((year, m, account, territory), 0.0)
                      for m in range(1, close_month + 1))
        bud_ytd = sum(budget.get((year, m, account, territory), 0.0)
                      for m in range(1, close_month + 1))

        run_rate = act_ytd / bud_ytd if bud_ytd else 1.0
        run_rate = max(0.70, min(1.40, run_rate))
        bias = jitter(0.96, 1.06, "reforecast", year, account, territory)

        for m in range(1, 13):
            if m <= close_month:
                forecast[(year, m, account, territory)] = actual.get((year, m, account, territory), 0.0)
            else:
                forecast[(year, m, account, territory)] = \
                    budget.get((year, m, account, territory), 0.0) * run_rate * bias
    return forecast


def write_csv(name, header, rows):
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  {name:24} {len(rows):>7,} rows")
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    assert_structure_is_additive()
    coa, terr, actual = load_source()
    print(f"Loaded GL: {len(actual):,} account x territory x month cells")

    budgets, forecasts = {}, {}
    for year in (PRIOR_FY, CURRENT_FY):
        b = build_budget(actual, year)
        close = CLOSE_MONTH if year == CURRENT_FY else 12
        f = build_forecast(actual, b, year, close)
        budgets.update(b)
        forecasts.update(f)

    # ---------------------------------------------------------------- fact table
    rows = []
    for (y, m, a, t), v in sorted(actual.items()):
        rows.append([f"{y}-{m:02d}-01", t, a, "Actual", round(v, 2)])
    for (y, m, a, t), v in sorted(budgets.items()):
        rows.append([f"{y}-{m:02d}-01", t, a, "Budget", round(v, 2)])
    for (y, m, a, t), v in sorted(forecasts.items()):
        rows.append([f"{y}-{m:02d}-01", t, a, "Forecast", round(v, 2)])

    print("\nWriting star schema:")
    write_csv("fact_pl.csv", ["Date", "Territory_key", "Account_key", "Scenario", "Amount"], rows)

    # ---------------------------------------------------------------- dimensions
    write_csv("dim_account.csv",
              ["Account_key", "Class", "SubClass", "SubClass2", "Account", "SubAccount"],
              [[a["account_key"], a["class"], a["subclass"], a["subclass2"],
                a["account"], a["subaccount"]]
               for a in sorted(coa.values(), key=lambda x: x["account_key"])
               if a["report"] == "Profit and Loss"])

    write_csv("dim_business_unit.csv", ["Territory_key", "Business Unit", "Region"],
              [[t["territory_key"], t["country"], t["region"]]
               for t in sorted(terr.values(), key=lambda x: x["territory_key"])])

    write_csv("dim_scenario.csv", ["Scenario", "Scenario Sort"],
              [["Actual", 1], ["Budget", 2], ["Forecast", 3]])

    # P&L row structure + the bridge that maps each row to its constituent accounts
    margin_parent = {"Gross Margin %": "Gross Profit", "EBITDA %": "EBITDA",
                     "EBIT %": "EBIT", "EBT %": "Earnings Before Taxes",
                     "Net Income %": "Net Income"}
    by_line = {line: accounts for _, line, _, _, _, accounts in PL_STRUCTURE}

    indent = " " * 4

    struct, bridge = [], []
    for sort, line, level, row_type, sign, accounts in PL_STRUCTURE:
        if row_type == "Margin":
            accounts = by_line[margin_parent[line]]
        label = (indent + line) if level == 2 else line
        struct.append([sort, label, level, row_type, sign,
                       1 if row_type == "Subtotal" else 0])
        for a in accounts:
            bridge.append([sort, a])
    write_csv("dim_pl_line.csv",
              ["PL Sort", "PL Line", "Level", "Row Type", "Display Sign", "Is Subtotal"], struct)
    write_csv("bridge_pl_account.csv", ["PL Sort", "Account_key"], bridge)

    # date dimension over the full GL span
    dates = []
    d, end = date(2018, 1, 1), date(2020, 12, 31)
    while d <= end:
        dates.append([d.isoformat(), d.year, f"Q{(d.month - 1)//3 + 1}",
                      d.month, MONTH_ABBR[d.month], f"{d.year}-{d.month:02d}",
                      1 if d.month <= CLOSE_MONTH else 0])
        d += timedelta(days=32)
        d = date(d.year, d.month, 1)
    write_csv("dim_date.csv",
              ["Date", "Year", "Quarter", "Month No", "Month", "Year Month", "Is YTD"], dates)

    # ---------------------------------------------------------------- sanity check
    print(f"\nFY{CURRENT_FY} check (all business units, thousands):")
    print(f"  {'Line':<28}{'Budget':>12}{'Forecast':>12}{'Act YTD':>12}{'FC to Go':>12}")
    for sort, line, level, row_type, sign, accounts in PL_STRUCTURE:
        if row_type == "Margin" or level != 1:
            continue
        acc = set(accounts)

        def s(src, months):
            return sign * sum(v for (y, m, a, t), v in src.items()
                              if y == CURRENT_FY and m in months and a in acc) / 1000

        allm, ytd, togo = range(1, 13), range(1, CLOSE_MONTH + 1), range(CLOSE_MONTH + 1, 13)
        print(f"  {line:<28}{s(budgets, allm):>12,.0f}{s(forecasts, allm):>12,.0f}"
              f"{s(actual, ytd):>12,.0f}{s(forecasts, togo):>12,.0f}")


if __name__ == "__main__":
    main()
