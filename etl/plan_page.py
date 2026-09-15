"""Page 02, Against Plan - the report half. Called from build_report.py.

Built from design/plan-mockup.html. Every helper comes from etl/milestone_pbir.py (the
milestone-report-design library); this file is layout only. Measures come from the
'Plan Metrics' table written by etl/plan_model.py.
"""

from __future__ import annotations

from milestone_pbir import (
    BODY, CANVAS_W, CARD, GOLD, INK, MUTED, NAVY, SLATE, Fields, action_button, axis,
    button_slicer, categorical_filter, colour, column, dynamic_chrome, dynamic_text, filter_panel,
    lit, masthead, obj, page, pivot_objects, sort_by, svg_image, visual,
)

PAGE_NAME = "pgAgainstPlan"
F = Fields("Plan Metrics")


def build() -> tuple[dict, list[dict], list[dict]]:
    v: list[dict] = masthead("Plan", "Performance against plan", "02 / AGAINST PLAN") + [
        dynamic_text("vStandPlan", 18, 112, 700, 56, 95, F.expr("Plan Standfirst")),

        button_slicer("vYearPlan", 740, 72, 150, 64, 400, "Date", "Year", 2020, 2, header="FISCAL YEAR",
                      filters=[categorical_filter("fYearPlan", "Date", "Year", [2019, 2020])]),
        button_slicer("vCompPlan", 906, 72, 340, 64, 410, "Plan Comparison", "Comparison", "Budget", 2,
                      header="COMPARE JAN-OCT WITH"),
        action_button("vFiltersPlan", 1262, 96, 154, 34, 420, "Filters", "bmPlanFiltersOpen"),
        dynamic_text("vChipPlan", 1250, 132, 178, 28, 430, F.expr("Plan Filter Summary"),
                     size=8.0, color=MUTED, align="center"),
    ]
    for i, card in enumerate(["Plan Card Revenue", "Plan Card EBITDA", "Plan Card Units", "Plan Card Accounts"]):
        v.append(svg_image(f"vCard{i + 1}Plan", 24 + i * 352, 176, 336, 140, 500 + i * 10, F.expr(card)))

    v.append(visual(
        "vLinePlan", "lineChart", 24, 332, 688, 264, 600,
        query={"queryState": {
            "Category": {"projections": [column("Date", "Month")]},
            "Y": {"projections": [F.m("Chart Actual", "Actual"), F.m("Chart Comparison", "Comparison")]}},
            "sortDefinition": sort_by(column("Date", "Month"), "Ascending")},
        objects={
            "categoryAxis": axis(), "valueAxis": axis(gridlines=True, labelDisplayUnits=lit(1000)),
            "legend": [{"properties": {"show": lit(True), "position": lit("Top"), "showTitle": lit(False),
                                       "fontSize": lit(8.5), "labelColor": colour(MUTED)}}],
            "labels": obj(show=lit(False)),
            "dataPoint": [{"properties": {"fill": colour(NAVY)}, "selector": {"metadata": F.ref("Chart Actual")}},
                          {"properties": {"fill": colour(SLATE)}, "selector": {"metadata": F.ref("Chart Comparison")}}],
            "lineStyles": [
                {"properties": {"strokeWidth": lit(2), "showMarker": lit(False), "lineStyle": lit("solid")}},
                {"properties": {"lineStyle": lit("dashed"), "strokeWidth": lit(2)},
                 "selector": {"metadata": F.ref("Chart Comparison")}},
            ],
        },
        container=dynamic_chrome(F.expr("Plan Title Line Chart"), F.expr("Plan Subtitle Line Chart")),
    ))
    v.append(button_slicer("vMetricPlan", 494, 338, 208, 40, 610, "Plan Chart Line", "Line", "EBITDA", 2))

    v.append(visual(
        "vVarPlan", "columnChart", 728, 332, 688, 264, 620,
        query={"queryState": {
            "Category": {"projections": [column("Date", "Month")]},
            "Y": {"projections": [F.m("Chart Variance", "Variance")]},
            "Tooltips": {"projections": [F.m("Chart Actual", "Actual"), F.m("Chart Comparison", "Comparison")]}},
            "sortDefinition": sort_by(column("Date", "Month"), "Ascending")},
        objects={
            "categoryAxis": axis(), "valueAxis": axis(gridlines=True, labelDisplayUnits=lit(1000)),
            "legend": obj(show=lit(False)),
            "labels": [{"properties": {"show": lit(True), "fontSize": lit(8.0), "color": colour(BODY),
                                       "labelDisplayUnits": lit(1000)}}],
            "dataPoint": [{"properties": {"fill": {"solid": {"color": F.expr("Chart Variance Colour")}}},
                           "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
        },
        container=dynamic_chrome(F.expr("Plan Title Variance Chart"), F.expr("Plan Subtitle Variance Chart")),
    ))

    unit_objects = pivot_objects()
    unit_objects["values"] = F.values_with_colour("EBITDA Variance Colour", "EBITDA Variance $000")
    v.append(visual(
        "vUnitsPlan", "pivotTable", 24, 612, 688, 264, 700,
        query={"queryState": {
            "Rows": {"projections": [column("Business Unit", "Business Unit")]},
            "Values": {"projections": [F.m("EBITDA Actual $000", "Actual $000"), F.m("EBITDA Comparison $000", "Comparison"),
                                       F.m("EBITDA Variance $000", "Variance"), F.m("Unit EBITDA Bar", " "),
                                       F.m("Unit Variance % Label", "%")]}},
            "sortDefinition": sort_by(F.m("EBITDA Variance $000"), "Descending")},
        objects=unit_objects,
        container=dynamic_chrome(F.expr("Plan Title Unit Table"), F.expr("Plan Subtitle Unit Table")),
    ))

    acc_objects = pivot_objects()
    acc_objects["values"] = F.values_with_colour("Account Effect Colour", "Account Effect $000")
    v.append(visual(
        "vAccountsPlan", "pivotTable", 728, 612, 688, 264, 710,
        query={"queryState": {
            "Rows": {"projections": [column("Account", "SubAccount", "Account")]},
            "Values": {"projections": [F.m("Account Effect Rank", "Rank"), F.m("Account Actual $000", "Actual $000"),
                                       F.m("Account Comparison $000", "Comparison"), F.m("Account Effect $000", "Effect on profit"),
                                       F.m("Account Effect Bar", " "), F.m("Account Effect % Label", "%")]}},
            "sortDefinition": sort_by(F.m("Account Effect Rank"), "Ascending")},
        objects=acc_objects,
        container=dynamic_chrome(F.expr("Plan Title Account Table"), F.expr("Plan Subtitle Account Table")),
        filters=[F.range_filter("fAccountsPlanTop", "Account Effect Rank", 1, 8)],
    ))
    v.append(button_slicer("vAccShowPlan", 1258, 618, 148, 40, 720, "Account Ranking", "Show", "Bottom", 2))

    panel, bookmarks = filter_panel("Plan", "bmPlanFilters", "Plan filters", PAGE_NAME, [
        ("vRegionPlan", "Business Unit", "Region", "REGION"),
        ("vUnitPlan", "Business Unit", "Business Unit", "BUSINESS UNIT"),
    ])
    v += panel

    return page(PAGE_NAME, "Against Plan"), v, bookmarks
