"""Page 02, Against Plan - the report half. Called from build_report.py.

Built from design/plan-mockup.html with the helpers of the milestone-report-design starter (the
Superstore revenue page): SVG measures in image visuals and table cells, button slicers on
disconnected tables, measure-bound titles, and a filter panel shown and hidden by two bookmarks.
Measures come from the 'Plan Metrics' table written by etl/plan_model.py.
"""

from __future__ import annotations

PAGE_NAME = "pgAgainstPlan"
ENTITY = "Plan Metrics"
CANVAS_W, CANVAS_H = 1440, 900

PAPER, CARD, RULE, INK, BODY, MUTED = "#F4F6FA", "#FFFFFF", "#E3E7EF", "#0A0917", "#4A5768", "#667284"
GOLD, NAVY, SLATE = "#C9A227", "#111F38", "#7C8598"
MARK_FILE = "MilestoneMark.svg"
VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json"

# --------------------------------------------------------------------------------------------
# Envelope helpers
# --------------------------------------------------------------------------------------------


def lit(value) -> dict:
    """'D' for a double, 'L' for an integer, quotes for text - the suffix is load-bearing."""
    if isinstance(value, bool):
        v = "true" if value else "false"
    elif isinstance(value, int):
        v = f"{value}L"
    elif isinstance(value, float):
        v = f"{value}D"
    else:
        v = f"'{value}'"
    return {"expr": {"Literal": {"Value": v}}}


def colour(hex_code: str) -> dict:
    return {"solid": {"color": lit(hex_code)}}


def obj(**props) -> list:
    return [{"properties": props}]


def mexpr(name: str) -> dict:
    return {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": ENTITY}}, "Property": name}}}


def m(name: str, display: str | None = None) -> dict:
    f = {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": ENTITY}}, "Property": name}},
         "queryRef": f"{ENTITY}.{name}", "nativeQueryRef": name}
    if display:
        f["displayName"] = display
    return f


def column(table: str, name: str, display: str | None = None) -> dict:
    f = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}},
         "queryRef": f"{table}.{name}", "nativeQueryRef": name, "active": True}
    if display:
        f["displayName"] = display
    return f


def sort_by(field: dict, direction: str = "Descending") -> dict:
    return {"sort": [{"field": field["field"], "direction": direction}], "isDefaultSort": True}


def in_filter(alias: str, table: str, col: str, values: list) -> dict:
    return {
        "Version": 2,
        "From": [{"Name": alias, "Entity": table, "Type": 0}],
        "Where": [{"Condition": {"In": {
            "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": col}}],
            "Values": [[lit(v)["expr"]] for v in values],
        }}}],
    }


# --------------------------------------------------------------------------------------------
# Chrome and visuals
# --------------------------------------------------------------------------------------------


def no_chrome() -> dict:
    return {
        "padding": obj(top=lit(0.0), bottom=lit(0.0), left=lit(0.0), right=lit(0.0)),
        "dropShadow": obj(show=lit(False)),
        "background": obj(show=lit(False)),
        "border": obj(show=lit(False)),
        "title": obj(show=lit(False)),
    }


def dynamic_chrome(title: str, subtitle: str | None = None) -> dict:
    out = {
        "padding": obj(top=lit(8.0), bottom=lit(8.0), left=lit(10.0), right=lit(10.0)),
        "dropShadow": obj(show=lit(False)),
        "background": obj(show=lit(True), color=colour(CARD), transparency=lit(0.0)),
        "border": obj(show=lit(True), color=colour(RULE), radius=lit(4)),
        "title": obj(show=lit(True), text=mexpr(title), fontSize=lit(10.5), bold=lit(True),
                     fontColor=colour(INK), heading=lit("Heading3")),
    }
    if subtitle:
        out["subTitle"] = obj(show=lit(True), text=mexpr(subtitle), fontSize=lit(8.5), fontColor=colour(MUTED))
    return out


def visual(name, vtype, x, y, w, h, z, query=None, objects=None, container=None, filters=None) -> dict:
    node = {"$schema": VISUAL_SCHEMA, "name": name,
            "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
            "visual": {"visualType": vtype}}
    if query is not None:
        node["visual"]["query"] = query
    if objects:
        node["visual"]["objects"] = objects
    node["visual"]["visualContainerObjects"] = container or no_chrome()
    if filters:
        node["filterConfig"] = {"filters": filters}
    return node


def textbox(name, x, y, w, h, z, paragraphs, background=None) -> dict:
    out = []
    for para in paragraphs:
        runs = para if isinstance(para, list) else [para]
        text_runs = []
        for run in runs:
            style = {"fontSize": f"{run.get('size', 11)}pt", "color": run.get("color", BODY)}
            if run.get("bold"):
                style["fontWeight"] = "bold"
            if run.get("family"):
                style["fontFamily"] = run["family"]
            if run.get("spacing"):
                style["letterSpacing"] = run["spacing"]
            text_runs.append({"value": run["text"], "textStyle": style})
        node = {"textRuns": text_runs}
        if runs[0].get("align"):
            node["horizontalTextAlignment"] = runs[0]["align"]
        out.append(node)
    container = no_chrome()
    if background:
        container["background"] = obj(show=lit(True), color=colour(background), transparency=lit(0.0))
        container["padding"] = obj(top=lit(4.0), bottom=lit(4.0), left=lit(10.0), right=lit(10.0))
    node = visual(name, "textbox", x, y, w, h, z, container=container)
    node["visual"]["objects"] = {"general": [{"properties": {"paragraphs": out}}]}
    return node


def mark(name, x, y, w, h, z) -> dict:
    node = visual(name, "image", x, y, w, h, z)
    node["visual"]["objects"] = {
        "general": obj(imageUrl={"expr": {"ResourcePackageItem": {
            "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": MARK_FILE}}}),
        "imageScaling": obj(imageScalingType=lit("Fit")),
    }
    return node


def dynamic_text(name, x, y, w, h, z, measure, size=10.0, color=BODY, align="left") -> dict:
    """A textbox cannot bind a measure: a transparent shape whose title is the measure. The fill
    must be transparent bare and on the default selector, or the theme paints under the text."""
    container = no_chrome()
    container["title"] = obj(show=lit(True), text=mexpr(measure), fontSize=lit(size), fontColor=colour(color),
                             bold=lit(False), titleWrap=lit(True), alignment=lit(align))
    clear = {"show": lit(True), "fillColor": colour(PAPER), "transparency": lit(100.0)}
    off = {"show": lit(False)}
    node = visual(name, "shape", x, y, w, h, z, container=container)
    node["visual"]["objects"] = {
        "shape": [{"properties": {"tileShape": lit("rectangle")}, "selector": {"id": "default"}}],
        "fill": [{"properties": clear}, {"properties": clear, "selector": {"id": "default"}}],
        "outline": [{"properties": off}, {"properties": off, "selector": {"id": "default"}}],
    }
    return node


def svg_image(name, x, y, w, h, z, measure) -> dict:
    node = visual(name, "image", x, y, w, h, z)
    node["visual"]["objects"] = {"image": [{"properties": {
        "sourceType": lit("imageData"), "sourceField": mexpr(measure), "fit": lit("Normal")}}]}
    return node


def button_slicer(name, x, y, w, h, z, table, col, default, columns, header=None, filters=None) -> dict:
    container = no_chrome()
    if header:
        container["title"] = obj(show=lit(True), text=lit(header), fontSize=lit(8.5), bold=lit(True),
                                 fontColor=colour(MUTED))
    return visual(
        name, "advancedSlicerVisual", x, y, w, h, z,
        query={"queryState": {"Values": {"projections": [column(table, col)]}}},
        objects={
            "general": [{"properties": {"filter": {"filter": in_filter("b", table, col, [default])}}}],
            "selection": [{"properties": {"strictSingleSelect": lit(True), "selectAllCheckboxEnabled": lit(False)}}],
            "layout": [{"properties": {"rowCount": lit(1), "columnCount": lit(columns), "cellPadding": lit(0)}}],
            "shapeCustomRectangle": [{"properties": {"tileShape": lit("rectangleRoundedByPixel"),
                                                     "rectangleRoundedCurve": lit(3)}, "selector": {"id": "default"}}],
            "fillCustom": [
                {"properties": {"show": lit(True), "fillColor": colour(CARD)}, "selector": {"id": "default"}},
                {"properties": {"show": lit(True), "fillColor": colour(INK)}, "selector": {"id": "selected"}},
                {"properties": {"show": lit(True), "fillColor": colour(PAPER)}, "selector": {"id": "hover"}},
            ],
            "outline": [
                {"properties": {"show": lit(True), "lineColor": colour(RULE), "weight": lit(1.0)}, "selector": {"id": "default"}},
                {"properties": {"show": lit(True), "lineColor": colour(INK), "weight": lit(1.0)}, "selector": {"id": "selected"}},
            ],
            "value": [
                {"properties": {"fontColor": colour(BODY), "fontSize": lit(9.0), "bold": lit(True),
                                "horizontalAlignment": lit("center")}, "selector": {"id": "default"}},
                {"properties": {"fontColor": colour(CARD)}, "selector": {"id": "selected"}},
            ],
            "label": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
            "icon": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
            "selectionIcon": [{"properties": {"show": lit(False)}, "selector": {"id": "default"}}],
        },
        container=container, filters=filters,
    )


def dropdown(name, x, y, w, h, z, table, col, header) -> dict:
    container = no_chrome()
    container["background"] = obj(show=lit(True), color=colour(CARD), transparency=lit(0.0))
    container["padding"] = obj(top=lit(8.0), bottom=lit(8.0), left=lit(10.0), right=lit(10.0))
    return visual(
        name, "slicer", x, y, w, h, z,
        query={"queryState": {"Values": {"projections": [column(table, col)]}}},
        objects={
            "general": [{"properties": {"orientation": lit(0)}}],
            "data": [{"properties": {"mode": lit("Dropdown")}}],
            "header": [{"properties": {"show": lit(True), "text": lit(header), "textSize": lit(8.5),
                                       "fontColor": colour(MUTED), "bold": lit(True)}}],
            "items": [{"properties": {"fontColor": colour(BODY), "textSize": lit(9.5), "background": colour(CARD)}}],
        },
        container=container,
    )


def action_button(name, x, y, w, h, z, text, bookmark, fill=CARD, text_colour=INK, outline=INK,
                  transparency=0.0) -> dict:
    """Styling objects need a bare entry and a 'default' id entry, or Desktop ignores them."""
    def dual(props):
        return [{"properties": props}, {"properties": props, "selector": {"id": "default"}}]
    objects = {
        "shape": [{"properties": {"tileShape": lit("rectangleRoundedByPixel"), "rectangleRoundedCurve": lit(4)}}],
        "fill": dual({"show": lit(True), "fillColor": colour(fill), "transparency": lit(transparency)}),
        "outline": dual({"show": lit(outline is not None),
                         **({"lineColor": colour(outline), "weight": lit(1.0)} if outline else {})}),
        "icon": dual({"show": lit(False)}),
        "text": dual({"show": lit(text is not None),
                      **({"text": lit(text), "fontColor": colour(text_colour), "fontSize": lit(10.0),
                          "bold": lit(True)} if text else {})}),
    }
    container = no_chrome()
    container["visualLink"] = obj(show=lit(True), type=lit("Bookmark"), bookmark=lit(bookmark))
    node = visual(name, "actionButton", x, y, w, h, z, container=container)
    node["visual"]["objects"] = objects
    node["howCreated"] = "InsertVisualButton"
    return node


def measure_range_filter(name, measure, low, high) -> dict:
    ref = {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": measure}}
    return {
        "name": name,
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": ENTITY}}, "Property": measure}},
        "type": "Advanced",
        "filter": {"Version": 2, "From": [{"Name": "m", "Entity": ENTITY, "Type": 0}],
                   "Where": [{"Condition": {"And": {
                       "Left": {"Comparison": {"ComparisonKind": 2, "Left": ref, "Right": lit(low)["expr"]}},
                       "Right": {"Comparison": {"ComparisonKind": 4, "Left": ref, "Right": lit(high)["expr"]}},
                   }}}]},
    }


def categorical_filter(name, table, col, values) -> dict:
    return {"name": name,
            "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}},
            "type": "Categorical", "filter": in_filter("t", table, col, values)}


def axis(gridlines=False, **extra) -> list:
    props = {"show": lit(True), "showAxisTitle": lit(False), "fontSize": lit(8.5),
             "labelColor": colour(MUTED), "gridlineShow": lit(gridlines)}
    if gridlines:
        props["gridlineColor"] = colour(RULE)
    props.update(extra)
    return [{"properties": props}]


def table_objects(image=True) -> dict:
    grid = {"gridVertical": lit(False), "gridHorizontal": lit(True), "gridHorizontalColor": colour(RULE),
            "rowPadding": lit(2)}
    if image:
        grid.update(imageHeight=lit(16.0), imageWidth=lit(120.0))
    return {
        "grid": [{"properties": grid}],
        "columnHeaders": [{"properties": {"fontSize": lit(9.0), "bold": lit(True), "fontColor": colour(INK),
                                          "backColor": colour(CARD), "alignment": lit("Right")}}],
        "rowHeaders": [{"properties": {"fontSize": lit(9.0), "fontColor": colour(BODY), "backColor": colour(CARD)}}],
        "subTotals": [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}],
    }


def values_objects(colour_measure: str, coloured: str) -> list:
    return [
        {"properties": {"fontSize": lit(9.0), "fontColorPrimary": colour(BODY),
                        "backColorPrimary": colour(CARD), "backColorSecondary": colour(CARD)}},
        {"properties": {"fontColor": {"solid": {"color": mexpr(colour_measure)}}},
         "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"{ENTITY}.{coloured}"}},
    ]


# --------------------------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------------------------


def build() -> tuple[dict, list[dict], list[dict]]:
    v: list[dict] = [
        textbox("vBandPlan", 0, 0, CANVAS_W, 60, 50, [[{"text": "", "size": 6, "color": INK}]], background=INK),
        mark("vMarkPlan", 24, 12, 44, 38, 60),
        textbox("vWordmarkPlan", 76, 15, 260, 32, 70, [[{"text": "Milestone ", "size": 15, "color": CARD, "bold": True},
                                                         {"text": "BI", "size": 15, "color": GOLD, "bold": True}]]),
        textbox("vRefPlan", 1016, 22, 400, 22, 80, [[{"text": "02 / AGAINST PLAN", "size": 8, "color": GOLD, "bold": True,
                                                      "family": "Consolas", "spacing": "2px", "align": "right"}]]),
        textbox("vTitlePlan", 24, 74, 700, 40, 90, [[{"text": "Performance against plan", "size": 22,
                                                      "color": INK, "bold": True}]]),
        dynamic_text("vStandPlan", 18, 112, 700, 56, 95, "Plan Standfirst"),

        button_slicer("vYearPlan", 740, 72, 150, 64, 400, "Date", "Year", 2020, 2, header="FISCAL YEAR",
                      filters=[categorical_filter("fYearPlan", "Date", "Year", [2019, 2020])]),
        button_slicer("vCompPlan", 906, 72, 340, 64, 410, "Plan Comparison", "Comparison", "Budget", 2,
                      header="COMPARE JAN-OCT WITH"),
        action_button("vFiltersPlan", 1262, 96, 154, 34, 420, "Filters", "bmPlanFiltersOpen"),
        dynamic_text("vChipPlan", 1250, 132, 178, 28, 430, "Plan Filter Summary", size=8.0, color=MUTED, align="center"),
    ]
    for i, measure in enumerate(["Plan Card Revenue", "Plan Card EBITDA", "Plan Card Units", "Plan Card Accounts"]):
        v.append(svg_image(f"vCard{i + 1}Plan", 24 + i * 352, 176, 336, 140, 500 + i * 10, measure))

    v.append(visual(
        "vLinePlan", "lineChart", 24, 332, 688, 264, 600,
        query={"queryState": {
            "Category": {"projections": [column("Date", "Month")]},
            "Y": {"projections": [m("Chart Actual", "Actual"), m("Chart Comparison", "Comparison")]}},
            "sortDefinition": sort_by(column("Date", "Month"), "Ascending")},
        objects={
            "categoryAxis": axis(), "valueAxis": axis(gridlines=True, labelDisplayUnits=lit(1000)),
            "legend": [{"properties": {"show": lit(True), "position": lit("Top"), "showTitle": lit(False),
                                       "fontSize": lit(8.5), "labelColor": colour(MUTED)}}],
            "labels": obj(show=lit(False)),
            "dataPoint": [{"properties": {"fill": colour(NAVY)}, "selector": {"metadata": f"{ENTITY}.Chart Actual"}},
                          {"properties": {"fill": colour(SLATE)}, "selector": {"metadata": f"{ENTITY}.Chart Comparison"}}],
            "lineStyles": [
                {"properties": {"strokeWidth": lit(2), "showMarker": lit(False), "lineStyle": lit("solid")}},
                {"properties": {"lineStyle": lit("dashed"), "strokeWidth": lit(2)},
                 "selector": {"metadata": f"{ENTITY}.Chart Comparison"}},
            ],
        },
        container=dynamic_chrome("Plan Title Line Chart", "Plan Subtitle Line Chart"),
    ))
    v.append(button_slicer("vMetricPlan", 494, 338, 208, 40, 610, "Plan Chart Line", "Line", "EBITDA", 2))

    v.append(visual(
        "vVarPlan", "columnChart", 728, 332, 688, 264, 620,
        query={"queryState": {
            "Category": {"projections": [column("Date", "Month")]},
            "Y": {"projections": [m("Chart Variance", "Variance")]},
            "Tooltips": {"projections": [m("Chart Actual", "Actual"), m("Chart Comparison", "Comparison")]}},
            "sortDefinition": sort_by(column("Date", "Month"), "Ascending")},
        objects={
            "categoryAxis": axis(), "valueAxis": axis(gridlines=True, labelDisplayUnits=lit(1000)),
            "legend": obj(show=lit(False)),
            "labels": [{"properties": {"show": lit(True), "fontSize": lit(8.0), "color": colour(BODY),
                                       "labelDisplayUnits": lit(1000)}}],
            "dataPoint": [{"properties": {"fill": {"solid": {"color": mexpr("Chart Variance Colour")}}},
                           "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
        },
        container=dynamic_chrome("Plan Title Variance Chart", "Plan Subtitle Variance Chart"),
    ))

    unit_objects = table_objects()
    unit_objects["values"] = values_objects("EBITDA Variance Colour", "EBITDA Variance $000")
    v.append(visual(
        "vUnitsPlan", "pivotTable", 24, 612, 688, 264, 700,
        query={"queryState": {
            "Rows": {"projections": [column("Business Unit", "Business Unit")]},
            "Values": {"projections": [m("EBITDA Actual $000", "Actual $000"), m("EBITDA Comparison $000", "Comparison"),
                                       m("EBITDA Variance $000", "Variance"), m("Unit EBITDA Bar", " "),
                                       m("Unit Variance % Label", "%")]}},
            "sortDefinition": sort_by(m("EBITDA Variance $000"), "Descending")},
        objects=unit_objects,
        container=dynamic_chrome("Plan Title Unit Table", "Plan Subtitle Unit Table"),
    ))

    acc_objects = table_objects()
    acc_objects["values"] = values_objects("Account Effect Colour", "Account Effect $000")
    v.append(visual(
        "vAccountsPlan", "pivotTable", 728, 612, 688, 264, 710,
        query={"queryState": {
            "Rows": {"projections": [column("Account", "SubAccount", "Account")]},
            "Values": {"projections": [m("Account Effect Rank", "Rank"), m("Account Actual $000", "Actual $000"),
                                       m("Account Comparison $000", "Comparison"), m("Account Effect $000", "Effect on profit"),
                                       m("Account Effect Bar", " "), m("Account Effect % Label", "%")]}},
            "sortDefinition": sort_by(m("Account Effect Rank"), "Ascending")},
        objects=acc_objects,
        container=dynamic_chrome("Plan Title Account Table", "Plan Subtitle Account Table"),
        filters=[measure_range_filter("fAccountsPlanTop", "Account Effect Rank", 1, 8)],
    ))
    v.append(button_slicer("vAccShowPlan", 1258, 618, 148, 40, 720, "Account Ranking", "Show", "Bottom", 2))

    panel = [
        action_button("vScrimPlan", 0, 0, CANVAS_W, CANVAS_H, 2000, None, "bmPlanFiltersClosed",
                      fill=INK, outline=None, transparency=65.0),
        textbox("vPanelPlan", 1076, 118, 340, 272, 2010, [[{"text": "", "size": 6}]], background=CARD),
        textbox("vPanelHeadPlan", 1092, 128, 300, 52, 2020, [
            [{"text": "Filters", "size": 14, "color": INK, "bold": True}],
            [{"text": "Apply to every number on this page, cards included.", "size": 8.5, "color": MUTED}],
        ]),
        dropdown("vRegionPlan", 1092, 184, 308, 80, 2030, "Business Unit", "Region", "REGION"),
        dropdown("vUnitPlan", 1092, 268, 308, 80, 2040, "Business Unit", "Business Unit", "BUSINESS UNIT"),
        action_button("vDonePlan", 1092, 344, 308, 34, 2060, "Done", "bmPlanFiltersClosed", fill=INK, text_colour=CARD),
    ]
    panel[1]["visual"]["visualContainerObjects"]["border"] = obj(show=lit(True), color=colour(RULE), radius=lit(6))
    for p in panel:
        p["isHidden"] = True
    v += panel

    page = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
        "name": PAGE_NAME, "displayName": "Against Plan", "displayOption": "FitToPage",
        "height": CANVAS_H, "width": CANVAS_W,
        "objects": {"background": obj(color=colour(PAPER), transparency=lit(0.0)),
                    "displayArea": obj(verticalAlignment=lit("Top"))},
    }
    return page, v, bookmarks(panel)


def bookmarks(panel: list[dict]) -> list[dict]:
    """Open and closed states for the filter panel, touching only its visuals and no data."""
    names = [p["name"] for p in panel]

    def one(suffix: str, hidden: bool) -> dict:
        containers = {}
        for p in panel:
            single = {"visualType": p["visual"]["visualType"], "objects": {}}
            if hidden:
                single["display"] = {"mode": "hidden"}
            containers[p["name"]] = {"singleVisual": single}
        return {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/bookmark/2.1.0/schema.json",
            "displayName": f"Plan filters {suffix.lower()}",
            "name": f"bmPlanFilters{suffix}",
            "options": {"targetVisualNames": names, "applyOnlyToTargetVisuals": True,
                        "suppressData": True, "suppressActiveSection": True},
            "explorationState": {"version": "1.3", "activeSection": PAGE_NAME,
                                 "sections": {PAGE_NAME: {"visualContainers": containers}}},
        }

    return [one("Open", False), one("Closed", True)]
