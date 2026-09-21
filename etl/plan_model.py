"""Generate the model half of page 02, Against Plan: a measure table and three toggle tables.

The rest of this model is hand-written TMDL. These four tables are generated instead, because
most of what they hold is SVG assembled in DAX, and a generator owns the escaping, the lineage
tags and TMDL's no-blank-lines rule in one place.

    python etl/plan_model.py

Writes tables/Plan Metrics.tmdl, Plan Comparison.tmdl, Plan Chart Line.tmdl and
Account Ranking.tmdl, and adds their `ref table` lines to model.tmdl if missing.

Conventions the measures rely on:

* Actuals, budget and prior year are all January to the October close ('Date'[Is YTD] = 1), so
  the three are always the same months.
* Amounts stay signed as posted - income positive, costs negative - so actual minus comparison is
  the effect on profit for any line or account, favourable when positive. No sign table needed.
* Business Unit is on the filter panel, so every business-unit pool uses ALLSELECTED. Account is
  never on a slicer and sits in a Top/Bottom table with a measure filter, so its pool uses ALL.
  (Using ALL on a slicer's own column is the bug found on the Superstore revenue page.)
"""

from __future__ import annotations

from pathlib import Path

from milestone_pbir import (
    BAD, GOOD, INK, NAVY, RULE, add_table_refs, card, disconnected_table_tmdl, diverging_bar,
    empty_card, indent, measure, measure_table_tmdl, money as _money, pct, pp, rank_measure,
    ring, ring_label, svg_uri, tagger, tone, write_lines,
)

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "PL Performance and Outlook.SemanticModel" / "definition" / "tables"
MODEL = ROOT / "PL Performance and Outlook.SemanticModel" / "definition" / "model.tmdl"
tag = tagger("2f1d5c7a-8e4b-4a3d-9c6e-7b8a1d2e3f40", "plan")

TOP_N = 8
ENTITY = "Plan Metrics"


def money(expr: str, signed: bool = False) -> str:
    """Card amounts on this page are in $k."""
    return _money(expr, signed, thousands=True)


def no_comparison_card(label: str) -> str:
    return empty_card(label, "Nothing to compare with for this year.")


def line_filter(line: str) -> str:
    """Restrict to the accounts one P&L line rolls up, keeping any account already in context."""
    return (f"KEEPFILTERS(TREATAS(CALCULATETABLE(VALUES('PL Bridge'[Account_key]), "
            f"REMOVEFILTERS('P&L Line'), 'P&L Line'[PL Line] = \"{line}\"), Account[Account_key]))")


BU_POOL = ("FILTER(ALLSELECTED('Business Unit'[Business Unit]), "
           "NOT ISBLANK([EBITDA Actual]) || NOT ISBLANK([EBITDA Comparison]))")
ACCOUNT_POOL = ("FILTER(ALL(Account[SubAccount]), "
                "NOT ISBLANK([_Plan Actual]) || NOT ISBLANK([_Plan Comparison]))")


def M(name, dax, fmt=None, doc=None, category=None, hidden=False):
    return measure(name, dax, fmt, doc, category, hidden)


def measures() -> list[dict]:
    out = [
        M("Plan Year", "MAX('Date'[Year])", "0", "The year on screen; the page forces a single year."),
        M("Plan Choice", "SELECTEDVALUE('Plan Comparison'[Comparison], \"Budget\")", None),
        M("Plan Comparison Label",
          "IF([Plan Choice] = \"Budget\", \"budget\", FORMAT([Plan Year] - 1, \"0\"))", None,
          "How the comparison reads inside a sentence: 'budget', or the prior year's number."),
        M("Plan Comparison Available", """
VAR Y = [Plan Year]
RETURN
    IF(
        [Plan Choice] = "Budget",
        NOT ISEMPTY(
            CALCULATETABLE(
                Financials,
                REMOVEFILTERS(Scenario), Scenario[Scenario] = "Budget",
                REMOVEFILTERS('Date'), 'Date'[Year] = Y,
                REMOVEFILTERS('Business Unit'), REMOVEFILTERS(Account)
            )
        ),
        Y - 1 >= CALCULATE(MIN('Date'[Year]), REMOVEFILTERS('Date'))
    )""", None,
          "False for 2018: there is no budget before 2019 and no year before 2018."),
        M("_Plan Actual", """
CALCULATE(SUM(Financials[Amount]), REMOVEFILTERS(Scenario), Scenario[Scenario] = "Actual", 'Date'[Is YTD] = 1)""",
          "#,0", "Actuals, January to the October close, signed as posted.", hidden=True),
        M("_Plan Comparison", """
VAR Y = [Plan Year]
RETURN
    IF(
        [Plan Comparison Available],
        IF(
            [Plan Choice] = "Budget",
            CALCULATE(SUM(Financials[Amount]), REMOVEFILTERS(Scenario), Scenario[Scenario] = "Budget", 'Date'[Is YTD] = 1),
            CALCULATE(SUM(Financials[Amount]), REMOVEFILTERS(Scenario), Scenario[Scenario] = "Actual", 'Date'[Is YTD] = 1, 'Date'[Year] = Y - 1)
        )
    )""", "#,0",
          "The same months, from the budget or from the prior year's actuals. The prior year replaces\n"
          "only the Year filter, so a month on a chart axis still applies.", hidden=True),
    ]

    for line in ["Revenue", "Gross Profit", "EBITDA", "Net Income"]:
        out += [
            M(f"{line} Actual", f"CALCULATE([_Plan Actual], {line_filter(line)})", "#,0"),
            M(f"{line} Comparison", f"CALCULATE([_Plan Comparison], {line_filter(line)})", "#,0"),
            M(f"{line} Variance", f"IF([Plan Comparison Available], [{line} Actual] - [{line} Comparison])", "#,0",
              "Actual less comparison. Positive is favourable: the line is signed as posted."),
            M(f"{line} Variance %", f"DIVIDE([{line} Variance], ABS([{line} Comparison]))", "0.0%"),
        ]
    out += [
        M("EBITDA Margin Actual", "DIVIDE([EBITDA Actual], [Revenue Actual])", "0.0%"),
        M("EBITDA Margin Comparison", "DIVIDE([EBITDA Comparison], [Revenue Comparison])", "0.0%"),
        M("Gross Margin Actual", "DIVIDE([Gross Profit Actual], [Revenue Actual])", "0.0%"),
        M("Gross Margin Comparison", "DIVIDE([Gross Profit Comparison], [Revenue Comparison])", "0.0%"),

        M("Plan Chart Metric", "SELECTEDVALUE('Plan Chart Line'[Line], \"EBITDA\")", None),
        M("Chart Actual", "IF([Plan Chart Metric] = \"Revenue\", [Revenue Actual], [EBITDA Actual])", "#,0"),
        M("Chart Comparison", "IF([Plan Chart Metric] = \"Revenue\", [Revenue Comparison], [EBITDA Comparison])", "#,0"),
        M("Chart Variance", "IF([Plan Chart Metric] = \"Revenue\", [Revenue Variance], [EBITDA Variance])", "#,0"),
        M("Chart Variance Colour", f"IF([Chart Variance] >= 0, \"{GOOD}\", \"{BAD}\")", None),
        M("EBITDA Variance Colour", f"IF([EBITDA Variance] >= 0, \"{GOOD}\", \"{BAD}\")", None),

        M("Units In Play", f"IF([Plan Comparison Available], COUNTROWS({BU_POOL}))", "0",
          "ALLSELECTED: Business Unit is on the filter panel, and ALL would ignore it."),
        M("Units Ahead", f"IF([Plan Comparison Available], COUNTROWS(FILTER({BU_POOL}, [EBITDA Variance] > 0)))", "0"),
        M("Unit EBITDA Bar", diverging_bar(
            "[EBITDA Variance]", f"MAXX({BU_POOL}, ABS([EBITDA Variance]))",
            "NOT ISBLANK(Change) && HASONEVALUE('Business Unit'[Business Unit])"), None,
          "Diverging bar for a unit's EBITDA variance, scaled to the largest among the units selected.",
          category="ImageUrl"),
        M("Unit Variance % Label", """
VAR P = [EBITDA Variance %]
RETURN IF(NOT ISBLANK([EBITDA Variance]), FORMAT(P, "+0.0%;-0.0%;0.0%"))""", None),

        M("Account Actual", "ABS([_Plan Actual])", "#,0",
          "Unsigned for display: an account is either income or cost, and the effect column carries the sign."),
        M("Account Comparison", "ABS([_Plan Comparison])", "#,0"),
        M("Account Effect", "IF([Plan Comparison Available], [_Plan Actual] - [_Plan Comparison])", "#,0",
          "Effect on profit: positive when income beat the comparison or a cost came in under it."),
        M("Accounts In Play", f"IF([Plan Comparison Available], COUNTROWS({ACCOUNT_POOL}))", "0",
          "Accounts with any posting in either period."),
        M("Accounts Favourable", f"IF([Plan Comparison Available], COUNTROWS(FILTER({ACCOUNT_POOL}, [Account Effect] > 0)))", "0"),
        M("Account Effect Rank", rank_measure(
            "'Account Ranking'[Show]", "Bottom", ACCOUNT_POOL, "[Account Effect]",
            "HASONEVALUE(Account[SubAccount]) && [Plan Comparison Available]\n"
            "            && (NOT ISBLANK([_Plan Actual]) || NOT ISBLANK([_Plan Comparison]))"), "0",
          f"Position by effect on profit, from the top or the bottom as 'Account Ranking' says. The table\n"
          f"keeps ranks 1 to {TOP_N} with a visual-level filter. ALL pool: that filter narrows ALLSELECTED."),
        M("Account Effect Bar", diverging_bar(
            "[Account Effect]", f"MAXX({ACCOUNT_POOL}, ABS([Account Effect]))",
            "NOT ISBLANK([Account Effect Rank])"), None,
          "Diverging bar for an account's effect on profit, one scale for Top and Bottom.", category="ImageUrl"),
        M("Account Effect % Label", """
VAR C = [_Plan Comparison]
VAR P = DIVIDE([Account Effect], ABS(C))
RETURN
    IF(
        NOT ISBLANK([Account Effect Rank]),
        IF(ISBLANK(C) || C = 0, "new", FORMAT(P, "+0.0%;-0.0%;0.0%"))
    )""", None),
        M("Account Effect Colour", f"IF([Account Effect] >= 0, \"{GOOD}\", \"{BAD}\")", None),
    ]

    # $000 for the tables, like page 01. Separate measures rather than a scaling format string, so
    # the charts' K display units never apply on top of an already-divided number.
    for name in ["EBITDA Actual", "EBITDA Comparison", "EBITDA Variance",
                 "Account Actual", "Account Comparison", "Account Effect"]:
        out.append(M(f"{name} $000", f"ROUND(DIVIDE([{name}], 1000), 0)", "#,0;-#,0;0"))

    # ---- words that rewrite themselves ---------------------------------------------------------
    out += [
        M("Plan Standfirst", """
VAR Y = [Plan Year]
VAR C = [Plan Comparison Label]
VAR RP = [Revenue Variance %]
VAR EP = [EBITDA Variance %]
VAR MarginMove = [EBITDA Margin Actual] - [EBITDA Margin Comparison]
RETURN
    IF(
        NOT [Plan Comparison Available],
        Y & " has nothing to compare with: there is no budget before 2019 and no year before 2018.",
        "January to October " & Y & ": revenue " & IF(RP >= 0, "ahead of ", "behind ") & C & " by "
            & FORMAT(ABS(RP), "0.0%") & ", EBITDA " & IF(EP >= 0, "ahead", "behind") & " by " & FORMAT(ABS(EP), "0.0%") & ". "
            & IF(
                ABS(MarginMove) < 0.01,
                "The EBITDA margin held at " & FORMAT([EBITDA Margin Actual], "0.0%") & ": costs moved with sales.",
                "The EBITDA margin " & IF(MarginMove < 0, "fell", "rose") & " from " & FORMAT([EBITDA Margin Comparison], "0.0%")
                    & " to " & FORMAT([EBITDA Margin Actual], "0.0%") & IF(MarginMove < 0, ": costs took a larger share of revenue.", ": costs took a smaller share of revenue.")
            )
    )""", None,
          "Judged on the margin, not on the two growth rates: revenue +37.7% against EBITDA +4.0% first\n"
          "read as 'costs moved in step with sales' while the margin fell 7.6 points."),
        M("Plan Title Line Chart",
          "[Plan Chart Metric] & \" by month, actual against \" & [Plan Comparison Label]", None),
        M("Plan Subtitle Line Chart", """
VAR Ahead = COUNTROWS(FILTER(VALUES('Date'[Month No]), [Chart Variance] > 0))
VAR Months = COUNTROWS(FILTER(VALUES('Date'[Month No]), NOT ISBLANK([Chart Actual])))
RETURN
    IF([Plan Comparison Available], "Ahead of " & [Plan Comparison Label] & " in " & Ahead & " of " & Months & " months")""", None),
        M("Plan Title Variance Chart", "\"Which months moved \" & [Plan Chart Metric]", None),
        M("Plan Subtitle Variance Chart", """
VAR ByMonth = FILTER(ADDCOLUMNS(VALUES('Date'[Month No]), "@V", [Chart Variance]), NOT ISBLANK([@V]))
VAR Worst = TOPN(1, ByMonth, ABS([@V]), DESC)
VAR V = MAXX(Worst, [@V])
VAR MonthName = FORMAT(DATE(2000, MAXX(Worst, 'Date'[Month No]), 1), "mmm")
RETURN
    IF(
        [Plan Comparison Available],
        [Plan Chart Metric] & " less " & [Plan Comparison Label] & ", by month: " & MonthName & " moved most ("
            & IF(V < 0, "-$", "+$") & FORMAT(ABS(V) / 1000, "#,0") & "k)"
    )""", None),
        M("Plan Title Unit Table", "\"EBITDA by business unit, against \" & [Plan Comparison Label]", None),
        M("Plan Subtitle Unit Table", f"""
VAR Worst = TOPN(1, ADDCOLUMNS({BU_POOL}, "@V", [EBITDA Variance]), [@V], ASC)
RETURN
    IF(
        [Plan Comparison Available],
        [Units Ahead] & " of " & [Units In Play] & " ahead; " & MAXX(Worst, 'Business Unit'[Business Unit])
            & IF(MAXX(Worst, [@V]) < 0, " is furthest behind", " is least ahead")
    )""", None),
        M("Plan Title Account Table", f"""
IF(
    SELECTEDVALUE('Account Ranking'[Show], "Bottom") = "Top",
    "The {TOP_N} accounts that helped profit most against " & [Plan Comparison Label],
    "The {TOP_N} accounts that cost profit most against " & [Plan Comparison Label]
)""", None),
        M("Plan Subtitle Account Table",
          "\"Effect on profit: income above or costs below \" & [Plan Comparison Label] & \" counts as positive\"", None),
        M("Plan Filter Summary", """
VAR Names =
    FILTER(
        {
            ("region", ISFILTERED('Business Unit'[Region]), 1),
            ("business unit", ISFILTERED('Business Unit'[Business Unit]), 2)
        },
        [Value2]
    )
RETURN
    IF(COUNTROWS(Names) = 0, "No filters applied", "Filtered by " & CONCATENATEX(Names, [Value1], ", ", [Value3], ASC))""", None),
    ]

    # ---- the four cards ----------------------------------------------------------------------
    out.append(M("Plan Card Revenue", f"""
VAR Y = [Plan Year]
VAR C = [Plan Comparison Label]
VAR A = [Revenue Actual]
VAR B = [Revenue Comparison]
VAR P = [Revenue Variance %]
VAR GM = [Gross Margin Actual]
VAR GMC = [Gross Margin Comparison]
VAR NI = [Net Income Actual]
VAR NIP = [Net Income Variance %]
VAR NIV = [Net Income Variance]
VAR Ratio = DIVIDE(A, B)
VAR Svg =
{indent(card(
    '"REVENUE, JAN-OCT " & Y',
    money("A"),
    f'{pct("P")} & " on " & C & " (" & {money("B")} & ")"',
    ('"Gross margin " & FORMAT(GM, "0.0%")', pp("GM", "GMC"), tone("GM - GMC")),
    ('"Net income " & ' + money("NI"), pct("NIP"), tone("NIV")),
    ring(286, 42, 26, "MIN(Ratio, 1)", NAVY, "Ratio - 1")
    + f' & "<text x=\'286\' y=\'47\' font-size=\'13\' font-weight=\'700\' text-anchor=\'middle\' fill=\'{INK}\'>" & FORMAT(Ratio, "0%") & "</text>"',
    icon="coin",
))}
VAR NoComparison = {no_comparison_card("REVENUE")}
RETURN
    {svg_uri("IF([Plan Comparison Available], Svg, NoComparison)")}""", None,
        "Revenue card: actual, the change on the comparison, and a ring of actual as a share of it.",
        category="ImageUrl"))

    out.append(M("Plan Card EBITDA", f"""
VAR Y = [Plan Year]
VAR C = [Plan Comparison Label]
VAR A = [EBITDA Actual]
VAR B = [EBITDA Comparison]
VAR P = [EBITDA Variance %]
VAR V = [EBITDA Variance]
VAR EM = [EBITDA Margin Actual]
VAR EMC = [EBITDA Margin Comparison]
VAR Ratio = DIVIDE(A, B)
VAR Svg =
{indent(card(
    '"EBITDA, JAN-OCT " & Y',
    money("A"),
    f'{pct("P")} & " on " & C & " (" & {money("B")} & ")"',
    ('"EBITDA margin " & FORMAT(EM, "0.0%")', pp("EM", "EMC"), tone("EM - EMC")),
    ('IF(V < 0, "Gap to close", "Headroom")', money("V", True), tone("V")),
    ring(286, 42, 26, "MAX(MIN(Ratio, 1), 0)", NAVY, "Ratio - 1")
    + f' & "<text x=\'286\' y=\'47\' font-size=\'13\' font-weight=\'700\' text-anchor=\'middle\' fill=\'{INK}\'>" & FORMAT(Ratio, "0%") & "</text>"',
    icon="bag",
))}
VAR NoComparison = {no_comparison_card("EBITDA")}
RETURN
    {svg_uri("IF([Plan Comparison Available], Svg, NoComparison)")}""", None,
        "EBITDA card: actual, the change, the margin move in points, and the gap or headroom.",
        category="ImageUrl"))

    out.append(M("Plan Card Units", f"""
VAR C = [Plan Comparison Label]
VAR Units = ADDCOLUMNS({BU_POOL}, "@V", [EBITDA Variance])
VAR N = COUNTROWS(Units)
VAR BestRow = TOPN(1, Units, [@V], DESC, 'Business Unit'[Business Unit], ASC)
VAR WorstRow = TOPN(1, Units, [@V], ASC, 'Business Unit'[Business Unit], ASC)
VAR BestValue = MAXX(BestRow, [@V])
VAR WorstValue = MAXX(WorstRow, [@V])
VAR Tiles =
    CONCATENATEX(
        Units,
        VAR UnitName = 'Business Unit'[Business Unit]
        VAR I = COUNTROWS(FILTER(Units, 'Business Unit'[Business Unit] < UnitName))
        VAR X = 196 + I * 18
        RETURN
            "<rect x='" & X & "' y='26' width='15' height='34' rx='2' fill='" & {tone("[@V]")} & "'/>"
                & "<text x='" & X + 7.5 & "' y='48' font-size='9' font-weight='700' text-anchor='middle' fill='#FFFFFF'>"
                & LEFT(UnitName, 1) & "</text>",
        ""
    )
VAR Svg =
{indent(card(
    '"UNITS AHEAD ON EBITDA"',
    'FORMAT([Units Ahead], "0")',
    '"of " & N & IF(N = 1, " business unit", " business units")',
    ('"Best &#183; " & MAXX(BestRow, \'Business Unit\'[Business Unit])', money("BestValue", True), tone("BestValue")),
    ('"Weakest &#183; " & MAXX(WorstRow, \'Business Unit\'[Business Unit])', money("WorstValue", True), tone("WorstValue")),
    "Tiles",
    icon="bars",
))}
VAR NoComparison = {no_comparison_card("UNITS AHEAD ON EBITDA")}
RETURN
    {svg_uri("IF([Plan Comparison Available], Svg, NoComparison)")}""", None,
        "One tile per business unit in the selection, alphabetical, green ahead and red behind.",
        category="ImageUrl"))

    out.append(M("Plan Card Accounts", f"""
VAR C = [Plan Comparison Label]
VAR Accounts = ADDCOLUMNS({ACCOUNT_POOL}, "@V", [Account Effect])
VAR Scale = MAXX(Accounts, ABS([@V]))
VAR BestRow = TOPN(1, Accounts, [@V], DESC, Account[SubAccount], ASC)
VAR WorstRow = TOPN(1, Accounts, [@V], ASC, Account[SubAccount], ASC)
VAR BestValue = MAXX(BestRow, [@V])
VAR WorstValue = MAXX(WorstRow, [@V])
VAR Bars =
    "<line x1='176' y1='46' x2='320' y2='46' stroke='{RULE}'/>"
        & CONCATENATEX(
            Accounts,
            VAR Change = [@V]
            VAR I = COUNTROWS(FILTER(Accounts, [@V] > Change))
            VAR H = MAX(1.5, 20 * DIVIDE(ABS(Change), Scale))
            RETURN
                "<rect x='" & FORMAT(176 + I * 6.8, "0.0") & "' y='" & FORMAT(IF(Change >= 0, 46 - H, 46), "0.0")
                    & "' width='5' height='" & FORMAT(H, "0.0") & "' fill='" & {tone("Change")} & "'/>",
            ""
        )
VAR Svg =
{indent(card(
    '"ACCOUNTS BETTER THAN " & UPPER(C)',
    'FORMAT([Accounts Favourable], "0")',
    '"of " & [Accounts In Play] & " accounts with postings"',
    ('"Best &#183; " & LEFT(MAXX(BestRow, Account[SubAccount]), 26)', money("BestValue", True), tone("BestValue")),
    ('"Worst &#183; " & LEFT(MAXX(WorstRow, Account[SubAccount]), 26)', money("WorstValue", True), tone("WorstValue")),
    "Bars",
    icon="clipboard-check",
))}
VAR NoComparison = {no_comparison_card("ACCOUNTS")}
RETURN
    {svg_uri("IF([Plan Comparison Available], Svg, NoComparison)")}""", None,
        "Every account with postings as a bar, sorted from most to least helpful to profit.",
        category="ImageUrl"))

    return out


DISCONNECTED = {
    "Plan Comparison": (
        "Button slicer values for what page 02 compares actuals with. No relationships.",
        [("Comparison", "string", "Comparison Order"), ("Comparison Order", "int64", None)],
        [("Budget", 1), ("Prior year", 2)],
    ),
    "Plan Chart Line": (
        "Revenue or EBITDA, for page 02's monthly charts.",
        [("Line", "string", "Line Order"), ("Line Order", "int64", None)],
        [("Revenue", 1), ("EBITDA", 2)],
    ),
    "Account Ranking": (
        "Top or Bottom for page 02's account table. Its own table: two toggles on one column\n"
        "cross-filter each other.",
        [("Show", "string", "Show Order"), ("Show Order", "int64", None)],
        [("Top", 1), ("Bottom", 2)],
    ),
}


# --------------------------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------------------------


def write_measure_table() -> int:
    specs = measures()
    write_lines(TABLES / f"{ENTITY}.tmdl", measure_table_tmdl(
        ENTITY, specs, tag, "Measures behind page 02, Against Plan. Generated by etl/plan_model.py - edit that, not this."))
    return len(specs)


def main() -> None:
    n = write_measure_table()
    for name, (doc_text, columns, rows) in DISCONNECTED.items():
        write_lines(TABLES / f"{name}.tmdl", disconnected_table_tmdl(name, doc_text, columns, rows, tag))
    add_table_refs(MODEL, [ENTITY, *DISCONNECTED], after="ref table 'Report View'")
    print(f"{ENTITY}: {n} measures; toggle tables: {', '.join(DISCONNECTED)}")


if __name__ == "__main__":
    main()
