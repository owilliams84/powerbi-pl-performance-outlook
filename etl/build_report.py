"""
Generate the PBIR report definition for 'PL Performance and Outlook'.

Written as a generator rather than by hand so the 20-odd visual JSON files stay consistent -
one place to change a colour, a font size or the grid, and every visual follows.

Run:  python etl/build_report.py
Then: powerbi-report-author validate "PL Performance and Outlook.Report"
"""

import json
import os
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORT = os.path.join(ROOT, "PL Performance and Outlook.Report")
DEFN = os.path.join(REPORT, "definition")

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
V_VISUAL = f"{SCHEMA}/visualContainer/2.5.0/schema.json"
V_PAGE = f"{SCHEMA}/page/2.0.0/schema.json"
V_REPORT = f"{SCHEMA}/report/3.3.0/schema.json"
V_PAGES = f"{SCHEMA}/pagesMetadata/1.0.0/schema.json"
V_VERSION = f"{SCHEMA}/versionMetadata/1.0.0/schema.json"

THEME_FILE = "MilestoneTheme.json"
MARK_FILE = "MilestoneMark.svg"

# ---------------------------------------------------------------- palette
# milestonebi.com's own tokens, so this reads as the same studio's work as the other three
# reports: near-black indigo for text and the brand band, gold for the accent, and the site's
# greys for everything that should recede.
PAPER = "#F4F6FA"      # page ground
SURFACE = "#FFFFFF"    # visual backgrounds
RULE = "#E3E7EF"       # hairlines and borders
INK = "#0A0917"        # headline text, and the brand band
BODY = "#4A5768"       # body text
MUTED = "#667284"      # secondary text, axis labels
NAVY = "#111F38"       # the logo's navy
GOLD = "#C9A227"       # the accent, on both grounds
ACTUAL = "#111F38"     # actual series
BUDGET = "#BCC1D2"     # budget series - deliberately recessive
FORECAST = "#C9A227"   # forecast series
GOOD = "#1E7A4C"
BAD = "#B3261E"

CANVAS_W, CANVAS_H = 1440, 900

# ---------------------------------------------------------------- expression helpers


def lit(value):
    return {"expr": {"Literal": {"Value": value}}}


def num(value):
    return lit(f"{value}D")


def integer(value):
    return lit(f"{value}L")


def boolean(value):
    return lit("true" if value else "false")


def text(value):
    return lit(f"'{value}'")


def fill(hex_colour):
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{hex_colour}'"}}}}}


def fill_from_measure(entity, prop):
    """Field-driven colour: a measure returning a hex string drives the colour slot."""
    return {"solid": {"color": {"expr": {"Measure": {
        "Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}}}}


def obj(**properties):
    return [{"properties": properties}]


def measure_field(entity, prop, display=None):
    p = {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": prop,
    }
    if display:
        p["displayName"] = display
    return p


def column_field(entity, prop, display=None, active=False):
    p = {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": prop,
    }
    if display:
        p["displayName"] = display
    if active:
        p["active"] = True
    return p


def sort_by_column(entity, prop, direction="Ascending"):
    return {"sort": [{"field": {"Column": {
        "Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "direction": direction}], "isDefaultSort": True}


def sort_by_measure(entity, prop, direction="Descending"):
    return {"sort": [{"field": {"Measure": {
        "Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "direction": direction}], "isDefaultSort": True}


# ---------------------------------------------------------------- shared chrome

def container(title=None, background=True):
    """Standard card chrome. padding is always declared - omitting it collapses the
    theme's padding cascade to zero and the contents sit flush against the border."""
    vco = {
        "padding": obj(top=num(8), bottom=num(8), left=num(10), right=num(10)),
        "dropShadow": obj(show=boolean(False)),
    }
    if background:
        vco["background"] = obj(show=boolean(True), color=fill(SURFACE), transparency=num(0))
        vco["border"] = obj(show=boolean(True), color=fill(RULE), radius=integer(4))
    if title:
        vco["title"] = obj(
            show=boolean(True), text=text(title), fontSize=num(10.5), bold=boolean(True),
            fontColor=fill(INK), heading=text("Heading3"))
    else:
        vco["title"] = obj(show=boolean(False))
    return vco


def visual(name, x, y, w, h, z, body):
    return {
        "$schema": V_VISUAL,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": body,
    }


# ---------------------------------------------------------------- visuals

def textbox(name, x, y, w, h, z, runs, align="left", background=None):
    # background and border are declared explicitly in both branches: the theme applies a white
    # card and a hairline to every visual, textboxes included, so leaving them out puts a white
    # box behind the title - and white text on the brand band disappears into it.
    vco = {
        "padding": obj(top=num(0), bottom=num(0), left=num(0), right=num(0)),
        "title": obj(show=boolean(False)),
        "border": obj(show=boolean(False)),
        "dropShadow": obj(show=boolean(False)),
        "background": obj(show=boolean(False)),
    }
    if background:
        vco["background"] = obj(show=boolean(True), color=fill(background), transparency=num(0))
    return visual(name, x, y, w, h, z, {
        "visualType": "textbox",
        "objects": {"general": obj(paragraphs=[{"textRuns": runs, "horizontalTextAlignment": align}])},
        "visualContainerObjects": vco,
    })


def image(name, x, y, w, h, z, resource):
    """A registered image. The file has to be listed in report.json's resourcePackages with
    type Image, and the binding is a ResourcePackageItem expression, not a literal path."""
    return visual(name, x, y, w, h, z, {
        "visualType": "image",
        "objects": {
            "general": obj(imageUrl={"expr": {"ResourcePackageItem": {
                "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": resource}}}),
            "imageScaling": obj(imageScalingType=text("Fit")),
        },
        "visualContainerObjects": {
            "padding": obj(top=num(0), bottom=num(0), left=num(0), right=num(0)),
            "background": obj(show=boolean(False)),
            "border": obj(show=boolean(False)),
            "dropShadow": obj(show=boolean(False)),
            "title": obj(show=boolean(False)),
        },
    })


def slicer(name, x, y, w, h, z, entity, prop, header, mode="Dropdown",
           orientation=0, preselect=None, alias="s", numeric=False):
    general = {"orientation": integer(orientation)}
    if preselect:
        general["filter"] = {"filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"In": {
                # Inside a Where condition the reference must be the From alias (Source),
                # not the Entity - using Entity here makes the filter silently do nothing.
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": alias}},
                                            "Property": prop}}],
                # int64 columns need a type-suffixed literal; strings need single quotes
                "Values": [[{"Literal": {"Value": (f"{v}L" if numeric else f"'{v}'")}}]
                           for v in preselect],
            }}}],
        }}

    vco = container()
    vco["title"] = obj(show=boolean(False))
    return visual(name, x, y, w, h, z, {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [column_field(entity, prop, active=True)]}}},
        "objects": {
            "general": obj(**general),
            "data": obj(mode=text(mode)),
            "header": obj(show=boolean(True), text=text(header), textSize=num(8.5),
                          fontColor=fill(MUTED), bold=boolean(True)),
            "items": obj(fontColor=fill(BODY), textSize=num(9.5), background=fill(SURFACE)),
        },
        "visualContainerObjects": vco,
    })


def kpi_card(name, x, y, w, h, z, entries):
    """One multi-value card rather than a row of single-value cards - cardVisual takes
    several projections natively and keeps the tiles aligned to one grid."""
    return visual(name, x, y, w, h, z, {
        "visualType": "cardVisual",
        "query": {"queryState": {"Data": {"projections": [
            measure_field("Metrics", prop, display) for prop, display in entries]}}},
        # value/label/accentBar all carry a _selectorHint of "default": without the id
        # selector these validate cleanly and then render unchanged.
        "objects": {
            "general": obj(),
            "value": [{"properties": {
                "fontSize": num(17), "bold": boolean(True), "fontColor": fill(INK),
                "fontFamily": text("Segoe UI"), "horizontalAlignment": text("Left"),
                "labelDisplayUnits": text("1")},
                "selector": {"id": "default"}}],
            "label": [{"properties": {
                "show": boolean(True), "fontSize": num(8.5), "fontColor": fill(MUTED),
                "bold": boolean(False), "position": text("belowValue"),
                "horizontalAlignment": text("Left")},
                "selector": {"id": "default"}}],
            "accentBar": [{"properties": {
                "show": boolean(True), "color": fill(ACTUAL), "width": integer(3)},
                "selector": {"id": "default"}}],
        },
        "visualContainerObjects": container(),
    })


def statement_matrix(name, x, y, w, h, z):
    """The statement itself.

    Rows come from the disconnected P&L Line table and the column headings from the
    disconnected Report View table, with a single measure resolving each cell. One matrix
    answers three different questions, and the headings change with the question.
    """
    return visual(name, x, y, w, h, z, {
        "visualType": "pivotTable",
        "query": {
            "queryState": {
                "Rows": {"projections": [
                    column_field("P&L Line", "PL Line", display="Statement", active=True)]},
                "Columns": {"projections": [column_field("Report View", "Column", active=True)]},
                "Values": {"projections": [measure_field("Metrics", "Cell")]},
            },
            # PL Line is sorted by PL Sort in the model, so an ascending sort on the label
            # lands the statement in statement order rather than alphabetical order.
            "sortDefinition": sort_by_column("P&L Line", "PL Line"),
        },
        "objects": {
            "columnHeaders": obj(
                fontSize=num(9), bold=boolean(True), fontColor=fill(MUTED),
                backColor=fill(SURFACE), alignment=text("Right"),
                autoSizeColumnWidth=boolean(True), columnAdjustment=text("growToFit")),
            "rowHeaders": obj(
                fontSize=num(9.5), fontColor=fill(INK),
                backColor=fill(SURFACE), showExpandCollapseButtons=boolean(False),
                stepped=boolean(False), alignment=text("Left"), wordWrap=boolean(False)),
            "values": [
                {"properties": {
                    "fontSize": num(9.5),
                    "fontColor": fill(BODY),
                    "backColorPrimary": fill(SURFACE),
                    "backColorSecondary": fill(SURFACE),
                }},
                # Favourability colouring. The wildcard selector targets every value column,
                # which is what a field-parameter column set needs - the columns are not
                # known statically, so no single metadata queryRef could name them.
                {"properties": {"fontColor": fill_from_measure("Metrics", "_Cell Colour")},
                 "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                              "metadata": "Metrics.Cell"}},
            ],
            "grid": obj(
                gridVertical=boolean(False), gridHorizontal=boolean(True),
                gridHorizontalColor=fill(RULE), rowPadding=integer(3),
                outlineColor=fill(RULE), outlineWeight=integer(1)),
            "subTotals": obj(rowSubtotals=boolean(False), columnSubtotals=boolean(False)),
        },
        # stylePreset is a container object. Left on the default preset it would repaint the
        # rows and quietly override every colour set above.
        "visualContainerObjects": dict(container(), stylePreset=obj(name=text("None"))),
    })


def monthly_chart(name, x, y, w, h, z):
    """Revenue by month, actual against budget, with the forecast carrying the open months."""
    v = visual(name, x, y, w, h, z, {
        "visualType": "lineChart",
        "query": {
            "queryState": {
                "Category": {"projections": [column_field("Date", "Month", active=True)]},
                "Y": {"projections": [
                    measure_field("Metrics", "Budget (month)", "Budget"),
                    measure_field("Metrics", "Forecast (month)", "Forecast"),
                    measure_field("Metrics", "Actual (month)", "Actual"),
                ]},
            },
            "sortDefinition": sort_by_column("Date", "Month"),
        },
        "objects": {
            "categoryAxis": obj(show=boolean(True), showAxisTitle=boolean(False), fontSize=num(8.5),
                                labelColor=fill(MUTED), gridlineShow=boolean(False)),
            "valueAxis": obj(show=boolean(True), showAxisTitle=boolean(False), fontSize=num(8.5),
                             labelColor=fill(MUTED), gridlineShow=boolean(True),
                             gridlineColor=fill(RULE)),
            "legend": obj(show=boolean(True), position=text("Top"), showTitle=boolean(False),
                          fontSize=num(8.5), labelColor=fill(MUTED)),
            "labels": obj(show=boolean(False)),
            "lineStyles": [
                {"properties": {"strokeWidth": integer(2), "lineStyle": text("solid"),
                                "showMarker": boolean(False)}},
                {"properties": {"lineStyle": text("dashed"), "strokeWidth": integer(2)},
                 "selector": {"metadata": "Metrics.Forecast (month)"}},
                {"properties": {"strokeWidth": integer(3)},
                 "selector": {"metadata": "Metrics.Actual (month)"}},
            ],
            "dataPoint": [
                {"properties": {"fill": fill(ACTUAL)},
                 "selector": {"metadata": "Metrics.Actual (month)"}},
                {"properties": {"fill": fill(BUDGET)},
                 "selector": {"metadata": "Metrics.Budget (month)"}},
                {"properties": {"fill": fill(FORECAST)},
                 "selector": {"metadata": "Metrics.Forecast (month)"}},
            ],
        },
        "visualContainerObjects": container("Revenue by month — actual vs budget vs forecast"),
    })
    # filterConfig is a sibling of "visual" at the root of visual.json, not a property inside
    # it. Pins the chart to the Revenue line so it does not follow the matrix row selection.
    v["filterConfig"] = {"filters": [{
        "name": "fRevenueLine",
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": "P&L Line"}},
                             "Property": "PL Line"}},
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "p", "Entity": "P&L Line", "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "p"}},
                                            "Property": "PL Line"}}],
                "Values": [[{"Literal": {"Value": "'Revenue'"}}]],
            }}}],
        },
    }]}
    return v


def variance_chart(name, x, y, w, h, z):
    """Where the EBITDA miss actually sits, by business unit."""
    return visual(name, x, y, w, h, z, {
        "visualType": "barChart",
        "query": {
            "queryState": {
                "Category": {"projections": [column_field("Business Unit", "Business Unit", active=True)]},
                "Y": {"projections": [measure_field("Metrics", "KPI EBITDA Var BUD", "EBITDA vs budget")]},
                "Tooltips": {"projections": [
                    measure_field("Metrics", "KPI EBITDA FC", "EBITDA forecast"),
                ]},
            },
            "sortDefinition": sort_by_measure("Metrics", "KPI EBITDA Var BUD", "Ascending"),
        },
        "objects": {
            "categoryAxis": obj(show=boolean(True), showAxisTitle=boolean(False), fontSize=num(8.5),
                                labelColor=fill(BODY), gridlineShow=boolean(False)),
            "valueAxis": obj(show=boolean(True), showAxisTitle=boolean(False), fontSize=num(8.5),
                             labelColor=fill(MUTED), gridlineShow=boolean(True),
                             gridlineColor=fill(RULE)),
            "legend": obj(show=boolean(False)),
            "labels": obj(show=boolean(True), fontSize=num(8.5), color=fill(BODY),
                          labelPosition=text("OutsideEnd")),
            "dataPoint": obj(defaultColor=fill(FORECAST)),
        },
        "visualContainerObjects": container("EBITDA variance to budget by business unit ($000)"),
    })


# ---------------------------------------------------------------- page assembly

def build_page():
    visuals = []
    z = 1000

    def nxt():
        nonlocal z
        z += 1000
        return z

    # Brand band. A textbox with a navy background rather than a shape - one fewer visual type
    # to get right - with the registered mark and the wordmark sitting on top of it.
    visuals.append(textbox("vBand0000000001", 0, 0, CANVAS_W, 60, nxt(), [{
        "value": " ", "textStyle": {"fontSize": "6px", "color": INK},
    }], background=INK))
    visuals.append(image("vMark0000000001", 24, 12, 44, 38, nxt(), MARK_FILE))
    visuals.append(textbox("vWordmark000001", 76, 15, 260, 32, nxt(), [
        {"value": "Milestone ", "textStyle": {"fontFamily": "Segoe UI", "fontSize": "15px",
                                              "fontWeight": "bold", "color": SURFACE}},
        {"value": "BI", "textStyle": {"fontFamily": "Segoe UI", "fontSize": "15px",
                                      "fontWeight": "bold", "color": GOLD}},
    ]))
    visuals.append(textbox("vRef0000000001", 1016, 22, 400, 22, nxt(), [{
        "value": "01 / P&L STATEMENT",
        "textStyle": {"fontFamily": "Consolas", "fontSize": "8px", "fontWeight": "bold",
                      "color": GOLD, "letterSpacing": "2px"},
    }], align="right"))

    visuals.append(textbox("vTitle0000000001", 24, 68, 700, 36, nxt(), [{
        "value": "Profit & Loss — Performance & Outlook",
        "textStyle": {"fontFamily": "Segoe UI", "fontSize": "22px", "fontWeight": "600",
                      "color": INK},
    }]))

    visuals.append(textbox("vBasis00000000001", 24, 104, 760, 24, nxt(), [{
        "value": "FY2020  |  actuals through October + forecast  |  all business units  |  $000",
        "textStyle": {"fontFamily": "Segoe UI", "fontSize": "10px", "color": MUTED},
    }]))

    # Dropdown slicers need at least 76px or the validator errors: header 28 + selector 32 +
    # padding.
    visuals.append(slicer("vYear000000000001", 786, 66, 200, 80, nxt(),
                          "Date", "Year", "FISCAL YEAR", mode="Dropdown",
                          preselect=[2020], alias="d", numeric=True))
    visuals.append(slicer("vRegion0000000001", 996, 66, 200, 80, nxt(),
                          "Business Unit", "Region", "REGION", mode="Dropdown", alias="r"))
    visuals.append(slicer("vBusUnit000000001", 1206, 66, 210, 80, nxt(),
                          "Business Unit", "Business Unit", "BUSINESS UNIT",
                          mode="Dropdown", alias="b"))

    # The three-view switcher. Tiles rather than a dropdown, so all three questions are
    # visible at once and switching between them is a single click.
    visuals.append(slicer("vView000000000001", 24, 152, 560, 96, nxt(),
                          "Report View", "View", "VIEW", mode="Basic", orientation=1,
                          preselect=["Full-Year Landing"], alias="v"))

    # 96px, not less: the card puts its label below the value, and at 84 the labels clip.
    visuals.append(kpi_card("vKpiStrip00000001", 596, 152, 820, 96, nxt(), [
        ("KPI Revenue FC", "Revenue"),
        ("KPI EBITDA FC", "EBITDA"),
        ("KPI EBITDA Margin FC", "EBITDA %"),
        ("KPI EBITDA Var BUD", "vs budget"),
        ("KPI Net Income FC", "Net income"),
    ]))

    visuals.append(statement_matrix("vStatement0000001", 24, 260, 884, 624, nxt()))
    visuals.append(monthly_chart("vMonthly000000001", 924, 260, 492, 300, nxt()))
    visuals.append(variance_chart("vVariance00000001", 924, 572, 492, 312, nxt()))

    page = {
        "$schema": V_PAGE,
        "name": "pgPLStatement",
        "displayName": "P&L Statement",
        "displayOption": "FitToPage",
        "height": CANVAS_H,
        "width": CANVAS_W,
        "objects": {
            "background": obj(color=fill(PAPER), transparency=num(0)),
            "displayArea": obj(verticalAlignment=text("Top")),
        },
    }
    return page, visuals


# ---------------------------------------------------------------- theme

def build_theme():
    return {
        "name": THEME_FILE,          # must match the file name exactly, extension included
        "dataColors": [ACTUAL, BUDGET, FORECAST, GOOD, BAD, "#4A6E8A", "#A8894F", MUTED],
        "background": PAPER,
        "foreground": BODY,
        "tableAccent": ACTUAL,
        "good": GOOD,
        "neutral": MUTED,
        "bad": BAD,
        "textClasses": {
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": 14, "color": INK},
            "header": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": INK},
            "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": BODY},
            "callout": {"fontFace": "Segoe UI", "fontSize": 20, "color": INK},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"show": True, "color": {"solid": {"color": SURFACE}}}],
                    "border": [{"show": True, "color": {"solid": {"color": RULE}}, "radius": 4}],
                    "padding": [{"top": 8, "bottom": 8, "left": 10, "right": 10}],
                    "dropShadow": [{"show": False}],
                }
            }
        },
    }


# ---------------------------------------------------------------- write

def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    # Wipe the pages tree first. Renamed visuals otherwise linger as stale empty boxes.
    # OneDrive intermittently holds a handle on the folders, so retry, then fall back to
    # clearing the files and leaving the empty directories behind - which is harmless.
    pages_dir = os.path.join(DEFN, "pages")
    for attempt in range(3):
        if not os.path.isdir(pages_dir):
            break
        try:
            shutil.rmtree(pages_dir)
        except PermissionError:
            if attempt == 2:
                shutil.rmtree(pages_dir, ignore_errors=True)
            else:
                time.sleep(0.6)

    write_json(os.path.join(REPORT, ".platform"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/"
                   "platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "PL Performance and Outlook"},
        "config": {"version": "2.0", "logicalId": "c48d1f07-9b25-4e6a-8d13-5f2a70c9e4b6"},
    })

    write_json(os.path.join(REPORT, "definition.pbir"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/"
                   "definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../PL Performance and Outlook.SemanticModel"}},
    })

    write_json(os.path.join(DEFN, "version.json"), {"$schema": V_VERSION, "version": "2.0.0"})

    # The versions Desktop itself writes back on save. Leaving the older set here meant every
    # save produced a diff against the generator, and the generator then undid it on the next run.
    versions = {"visual": "2.12.0", "report": "3.4.0", "page": "2.3.1"}
    write_json(os.path.join(DEFN, "report.json"), {
        "$schema": V_REPORT,
        "themeCollection": {
            "baseTheme": {"name": "CY25SU12", "reportVersionAtImport": versions,
                          "type": "SharedResources"},
            "customTheme": {"name": THEME_FILE, "reportVersionAtImport": versions,
                            "type": "RegisteredResources"},
        },
        "objects": {
            "section": obj(verticalAlignment=text("Top")),
            "outspacePane": obj(expanded=boolean(False)),
        },
        # Two packages, not one. The SharedResources entry naming the base theme was missing,
        # and Desktop silently added it back on the first save - so the generated report.json and
        # the saved one disagreed until this matched.
        "resourcePackages": [
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": MARK_FILE, "path": MARK_FILE, "type": "Image"},
                       {"name": THEME_FILE, "path": THEME_FILE, "type": "CustomTheme"}]},
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY25SU12", "path": "BaseThemes/CY25SU12.json",
                        "type": "BaseTheme"}]},
        ],
        "settings": {"useStylableVisualContainerHeader": True},
    })

    resources = os.path.join(REPORT, "StaticResources", "RegisteredResources")
    write_json(os.path.join(resources, THEME_FILE), build_theme())
    shutil.copyfile(os.path.join(HERE, "assets", "milestone-mark.svg"),
                    os.path.join(resources, MARK_FILE))
    # The report used to ship a theme under its own name; Desktop caches themes by file name, so
    # the old one is removed rather than left to shadow the new palette.
    stale = os.path.join(resources, "PLPerformanceTheme.json")
    if os.path.exists(stale):
        os.remove(stale)

    page, visuals = build_page()
    write_json(os.path.join(DEFN, "pages", "pages.json"), {
        "$schema": V_PAGES,
        "pageOrder": [page["name"]],
        "activePageName": page["name"],
    })
    write_json(os.path.join(DEFN, "pages", page["name"], "page.json"), page)
    for v in visuals:
        write_json(os.path.join(DEFN, "pages", page["name"], "visuals", v["name"], "visual.json"), v)

    print(f"Wrote 1 page, {len(visuals)} visuals to {REPORT}")


if __name__ == "__main__":
    main()
