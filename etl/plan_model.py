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

import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "PL Performance and Outlook.SemanticModel" / "definition" / "tables"
MODEL = ROOT / "PL Performance and Outlook.SemanticModel" / "definition" / "model.tmdl"
NS = uuid.UUID("2f1d5c7a-8e4b-4a3d-9c6e-7b8a1d2e3f40")

GOOD, BAD, INK, BODY, MUTED, RULE, GOLD, NAVY = (
    "#1E7A4C", "#B3261E", "#0A0917", "#4A5768", "#667284", "#E3E7EF", "#C9A227", "#111F38")
TOP_N = 8
ENTITY = "Plan Metrics"


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "plan:" + ":".join(parts)))


def q(name: str) -> str:
    return name if name.replace("_", "").isalnum() else f"'{name}'"


# --------------------------------------------------------------------------------------------
# SVG helpers (from the milestone-report-design starter, money in $000)
# --------------------------------------------------------------------------------------------


def svg_uri(body: str = "Svg") -> str:
    """'%' before '#': unencoded, "3.6%" is read as an escape and '#' ends the URI."""
    return f'"data:image/svg+xml;utf8," & SUBSTITUTE(SUBSTITUTE({body}, "%", "%25"), "#", "%23")'


def money(expr: str, signed: bool = False) -> str:
    body = f'FORMAT(ABS({expr}) / 1000, "#,0") & "k"'
    if signed:
        return f'IF({expr} < 0, "&#8722;$", "+$") & {body}'
    return f'IF({expr} < 0, "&#8722;$", "$") & {body}'


def pct(expr: str) -> str:
    return (f'IF(ISBLANK({expr}), "new", IF({expr} < 0, "&#8722;", "+") & FORMAT(ABS({expr}), "0.0%"))')


def pp(a: str, b: str) -> str:
    return f'IF({a} - {b} < 0, "&#8722;", "+") & FORMAT(ABS({a} - {b}) * 100, "0.0") & "pp"'


def tone(expr: str) -> str:
    return f'IF({expr} >= 0, "{GOOD}", "{BAD}")'


def ring(cx: int, cy: int, r: int, share: str, colour: str, over: str | None = None) -> str:
    def arc(s: str, col: str) -> str:
        return (
            f'IF({s} > 0, "<path d=\'M{cx},{cy - r} A{r},{r} 0 " & IF({s} > 0.5, "1", "0") & " 1 " & '
            f'FORMAT({cx} + {r} * COS(2 * PI() * MIN({s}, 0.9999) - PI() / 2), "0.00") & "," & '
            f'FORMAT({cy} + {r} * SIN(2 * PI() * MIN({s}, 0.9999) - PI() / 2), "0.00") & '
            f'"\' stroke=\'{col}\' stroke-width=\'7\' fill=\'none\'/>")'
        )
    out = f'"<circle cx=\'{cx}\' cy=\'{cy}\' r=\'{r}\' stroke=\'{RULE}\' stroke-width=\'7\' fill=\'none\'/>" & {arc(share, colour)}'
    if over:
        out += f" & {arc(over, GOLD)}"
    return out


def card(label: str, value: str, note: str, row1: tuple, row2: tuple, graphic: str) -> str:
    def row(y: int, r: tuple) -> str:
        return (f'"<text x=\'16\' y=\'{y}\' font-size=\'11.5\' fill=\'{BODY}\'>" & {r[0]} & "</text>'
                f'<text x=\'320\' y=\'{y}\' font-size=\'11.5\' font-weight=\'600\' text-anchor=\'end\' fill=\'" & {r[2]} & "\'>" & {r[1]} & "</text>"')
    return "\n".join([
        f'"<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'336\' height=\'140\' viewBox=\'0 0 336 140\' font-family=\'Segoe UI, sans-serif\'>"',
        f'& "<rect x=\'0.5\' y=\'0.5\' width=\'335\' height=\'139\' rx=\'4\' fill=\'#FFFFFF\' stroke=\'{RULE}\'/><rect width=\'3\' height=\'140\' fill=\'{GOLD}\'/>"',
        f'& "<text x=\'16\' y=\'24\' font-size=\'11\' font-weight=\'700\' fill=\'{MUTED}\' letter-spacing=\'0.4\'>" & {label} & "</text>"',
        f'& "<text x=\'16\' y=\'58\' font-size=\'28\' font-weight=\'700\' fill=\'{INK}\'>" & {value} & "</text>"',
        f'& "<text x=\'16\' y=\'76\' font-size=\'11.5\' fill=\'{MUTED}\'>" & {note} & "</text>"',
        f'& "<line x1=\'16\' y1=\'88\' x2=\'320\' y2=\'88\' stroke=\'{RULE}\'/>"',
        f"& {row(107, row1)}",
        f"& {row(127, row2)}",
        f"& {graphic}",
        '& "</svg>"',
    ])


def no_comparison_card(label: str) -> str:
    return (f'"<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'336\' height=\'140\' viewBox=\'0 0 336 140\' font-family=\'Segoe UI, sans-serif\'>'
            f'<rect x=\'0.5\' y=\'0.5\' width=\'335\' height=\'139\' rx=\'4\' fill=\'#FFFFFF\' stroke=\'{RULE}\'/>'
            f'<text x=\'16\' y=\'24\' font-size=\'11\' font-weight=\'700\' fill=\'{MUTED}\'>{label}</text>'
            f'<text x=\'16\' y=\'64\' font-size=\'13\' fill=\'{BODY}\'>Nothing to compare with for this year.</text></svg>"')


def indent(text: str, n: int = 1) -> str:
    return "\n".join(("    " * n + line) if line else line for line in text.split("\n"))


def line_filter(line: str) -> str:
    """Restrict to the accounts one P&L line rolls up, keeping any account already in context."""
    return (f"KEEPFILTERS(TREATAS(CALCULATETABLE(VALUES('PL Bridge'[Account_key]), "
            f"REMOVEFILTERS('P&L Line'), 'P&L Line'[PL Line] = \"{line}\"), Account[Account_key]))")


BU_POOL = ("FILTER(ALLSELECTED('Business Unit'[Business Unit]), "
           "NOT ISBLANK([EBITDA Actual]) || NOT ISBLANK([EBITDA Comparison]))")
ACCOUNT_POOL = ("FILTER(ALL(Account[SubAccount]), "
                "NOT ISBLANK([_Plan Actual]) || NOT ISBLANK([_Plan Comparison]))")


def M(name, dax, fmt=None, doc=None, category=None, hidden=False):
    return dict(name=name, dax=dax.strip("\n"), fmt=fmt, doc=doc, category=category, hidden=hidden)


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
        M("Unit EBITDA Bar", f"""
VAR Change = [EBITDA Variance]
VAR Scale = MAXX({BU_POOL}, ABS([EBITDA Variance]))
VAR W = DIVIDE(ABS(Change), Scale) * 56
VAR X = IF(Change >= 0, 60, 60 - W)
VAR Svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='120' height='16' viewBox='0 0 120 16'>"
        & "<line x1='60' y1='0' x2='60' y2='16' stroke='{MUTED}'/>"
        & "<rect x='" & FORMAT(X, "0.0") & "' y='3' width='" & FORMAT(W, "0.0") & "' height='10' fill='" & {tone("Change")} & "'/>"
        & "</svg>"
RETURN
    IF(NOT ISBLANK(Change) && HASONEVALUE('Business Unit'[Business Unit]), {svg_uri()})""", None,
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
        M("Account Effect Rank", f"""
VAR Direction = SELECTEDVALUE('Account Ranking'[Show], "Bottom")
VAR Pool = {ACCOUNT_POOL}
VAR Me = [Account Effect]
RETURN
    IF(
        HASONEVALUE(Account[SubAccount]) && [Plan Comparison Available]
            && (NOT ISBLANK([_Plan Actual]) || NOT ISBLANK([_Plan Comparison])),
        IF(
            Direction = "Top",
            COUNTROWS(FILTER(Pool, [Account Effect] > Me)) + 1,
            COUNTROWS(FILTER(Pool, [Account Effect] < Me)) + 1
        )
    )""", "0",
          f"Position by effect on profit, from the top or the bottom as 'Account Ranking' says. The table\n"
          f"keeps ranks 1 to {TOP_N} with a visual-level filter. ALL pool: that filter narrows ALLSELECTED."),
        M("Account Effect Bar", f"""
VAR Change = [Account Effect]
VAR Scale = MAXX({ACCOUNT_POOL}, ABS([Account Effect]))
VAR W = DIVIDE(ABS(Change), Scale) * 56
VAR X = IF(Change >= 0, 60, 60 - W)
VAR Svg =
    "<svg xmlns='http://www.w3.org/2000/svg' width='120' height='16' viewBox='0 0 120 16'>"
        & "<line x1='60' y1='0' x2='60' y2='16' stroke='{MUTED}'/>"
        & "<rect x='" & FORMAT(X, "0.0") & "' y='3' width='" & FORMAT(W, "0.0") & "' height='10' fill='" & {tone("Change")} & "'/>"
        & "</svg>"
RETURN
    IF(NOT ISBLANK([Account Effect Rank]), {svg_uri()})""", None,
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


def doc(text: str | None, pad: str) -> list[str]:
    return [f"{pad}/// {p}".rstrip() for p in text.split("\n")] if text else []


def write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_measure_table() -> int:
    lines = doc("Measures behind page 02, Against Plan. Generated by etl/plan_model.py - edit that, not this.", "")
    lines += [f"table {q(ENTITY)}", f"\tlineageTag: {tag('table', ENTITY)}"]
    specs = measures()
    for s in specs:
        lines.append("")
        lines += doc(s["doc"], "\t")
        body = s["dax"].split("\n")
        if len(body) == 1:
            lines.append(f"\tmeasure {q(s['name'])} = {body[0]}")
        else:
            lines.append(f"\tmeasure {q(s['name'])} =")
            lines += [("\t\t\t" + b) if b.strip() else "\t\t\t" for b in body]
        if s["fmt"]:
            lines.append(f"\t\tformatString: {s['fmt']}")
        if s["hidden"]:
            lines.append("\t\tisHidden")
        if s["category"]:
            lines.append(f"\t\tdataCategory: {s['category']}")
        lines.append(f"\t\tlineageTag: {tag('measure', s['name'])}")
    lines += [
        "",
        "\tcolumn Placeholder",
        "\t\tdataType: string",
        "\t\tisHidden",
        f"\t\tlineageTag: {tag('column', ENTITY, 'Placeholder')}",
        "\t\tsummarizeBy: none",
        "\t\tsourceColumn: [Placeholder]",
        "",
        f"\tpartition {q(ENTITY)} = calculated",
        "\t\tmode: import",
        "\t\tsource = ROW(\"Placeholder\", \"\")",
    ]
    write(TABLES / f"{ENTITY}.tmdl", lines)
    return len(specs)


def write_disconnected(name: str, doc_text: str, columns: list, rows: list) -> None:
    lines = doc(doc_text, "") + [f"table {q(name)}", f"\tlineageTag: {tag('table', name)}"]
    for col, dtype, sort_by in columns:
        lines += ["", f"\tcolumn {q(col)}", f"\t\tdataType: {dtype}"]
        if dtype == "int64":
            lines += ["\t\tisHidden", "\t\tformatString: 0"]
        lines += [f"\t\tlineageTag: {tag('column', name, col)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {col}"]
        if sort_by:
            lines.append(f"\t\tsortByColumn: {q(sort_by)}")
    fields = ", ".join((c if c.isidentifier() else f'#"{c}"') + (" = Int64.Type" if t == "int64" else " = text")
                       for c, t, _ in columns)
    data = ", ".join("{" + ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in r) + "}" for r in rows)
    lines += [
        "",
        f"\tpartition {q(name)} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f"\t\t\t\t    Source = #table(type table [{fields}], {{{data}}})",
        "\t\t\t\tin",
        "\t\t\t\t    Source",
        "",
        "\tannotation PBI_ResultType = Table",
    ]
    write(TABLES / f"{name}.tmdl", lines)


def add_refs() -> None:
    text = MODEL.read_text(encoding="utf-8")
    missing = [n for n in [ENTITY, *DISCONNECTED] if f"ref table {q(n)}" not in text]
    if not missing:
        return
    marker = "ref table 'Report View'"
    new = "\n".join(f"ref table {q(n)}" for n in missing)
    text = text.replace(marker, marker + "\n" + new, 1)
    MODEL.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    n = write_measure_table()
    for name, (doc_text, columns, rows) in DISCONNECTED.items():
        write_disconnected(name, doc_text, columns, rows)
    add_refs()
    print(f"{ENTITY}: {n} measures; toggle tables: {', '.join(DISCONNECTED)}")


if __name__ == "__main__":
    main()
