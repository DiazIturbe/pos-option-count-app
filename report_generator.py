import pandas as pd
from io import BytesIO


def generate_report(pos_file, jesta_file, scan_file):
    # -------------------------
    # Load scan file
    # -------------------------
    scan_list = pd.read_excel(scan_file, sheet_name=0, dtype=str)
    scan_list.columns = scan_list.columns.astype(str).str.strip()

    if "bar_code_id" not in scan_list.columns:
        scan_list = scan_list.rename(columns={scan_list.columns[0]: "bar_code_id"})

    scan_list["bar_code_id"] = scan_list["bar_code_id"].astype(str).str.strip()
    scan_list = scan_list[
        scan_list["bar_code_id"].notna() &
        (scan_list["bar_code_id"] != "")
    ].copy()

    # -------------------------
    # Load Jesta mapping
    # -------------------------
    jesta_map = pd.read_csv(jesta_file, low_memory=False)

    jesta_map = jesta_map.rename(columns={
        "BAR_CODE_ID": "bar_code_id",
        "VENDOR_STYLE_CODE": "product_code",
        "BRAND": "brand",
        "DESCRIPTION": "description",
    })

    jesta_map["bar_code_id"] = jesta_map["bar_code_id"].astype(str).str.strip()
    jesta_map["product_code"] = jesta_map["product_code"].astype(str).str.strip()

    # -------------------------
    # Match scan to product codes
    # -------------------------
    scan_with_products = scan_list.merge(
        jesta_map,
        on="bar_code_id",
        how="left"
    )

    scanned_all = scan_with_products[
        scan_with_products["product_code"].notna()
    ].copy()

    scanned_all["product_code"] = scanned_all["product_code"].astype(str).str.strip()

    scanned_unique = scanned_all.drop_duplicates(subset=["product_code"]).copy()

    # -------------------------
    # Load POS Option Count
    # -------------------------
    pos = pd.read_excel(
        pos_file,
        sheet_name="Master",
        header=2
    )

    pos.columns = pos.columns.astype(str).str.strip()

    pos = pos.rename(columns={
        "BRAND": "brand",
        "DESCRIPTION": "description",
        "VENDOR_STYLE_NO": "product_code",
        "DEPARTMENT": "department",
        "SIZES_IN_STOCK": "sizes_in_stock",
        "QTY_ON_HAND": "qty_oh",
    })

    pos["product_code"] = pos["product_code"].astype(str).str.strip()

    # -------------------------
    # Compare POS vs floor scan
    # -------------------------
    on_floor_expected = scanned_unique.merge(
        pos,
        on="product_code",
        how="inner"
    )

    on_floor_unexpected = scanned_unique[
        ~scanned_unique["product_code"].isin(pos["product_code"])
    ].copy()

    missing_from_floor = pos[
        ~pos["product_code"].isin(scanned_unique["product_code"])
    ].copy()

    pos_n = pos["product_code"].nunique()

    summary = pd.DataFrame({
        "Metric": [
            "POS Expected Options",
            "Scanned Options",
            "On Floor & Expected",
            "On Floor but Unexpected",
            "Expected but Missing"
        ],
        "Count": [
            pos_n,
            scanned_unique["product_code"].nunique(),
            on_floor_expected["product_code"].nunique(),
            on_floor_unexpected["product_code"].nunique(),
            missing_from_floor["product_code"].nunique()
        ]
    })

    summary["% of POS"] = (summary["Count"] / pos_n * 100).round(1)

    # -------------------------
    # Department summaries
    # -------------------------
    missing_by_dept = (
        missing_from_floor
        .assign(department=lambda df: df["department"].fillna("UNKNOWN"))
        .groupby("department")["product_code"]
        .nunique()
        .reset_index(name="missing_count")
        .sort_values("missing_count", ascending=False)
    )

    unexpected_by_dept = (
        on_floor_unexpected
        .assign(department="UNKNOWN (not in POS)")
        .groupby("department")["product_code"]
        .nunique()
        .reset_index(name="unexpected_count")
        .sort_values("unexpected_count", ascending=False)
    )

    # -------------------------
    # Build final report
    # -------------------------
    r_expected = on_floor_expected.copy()
    r_expected["status"] = "ON_FLOOR_EXPECTED"

    if "brand_y" in r_expected.columns or "brand_x" in r_expected.columns:
        r_expected["brand"] = (
            r_expected.get("brand_y", pd.Series(index=r_expected.index))
            .combine_first(r_expected.get("brand_x", pd.Series(index=r_expected.index)))
        )

    if "description_y" in r_expected.columns or "description_x" in r_expected.columns:
        r_expected["description"] = (
            r_expected.get("description_y", pd.Series(index=r_expected.index))
            .combine_first(r_expected.get("description_x", pd.Series(index=r_expected.index)))
        )

    r_unexpected = on_floor_unexpected.copy()
    r_unexpected["status"] = "ON_FLOOR_UNEXPECTED"
    r_unexpected["department"] = "UNKNOWN (not in POS)"
    r_unexpected["sizes_in_stock"] = pd.NA
    r_unexpected["qty_oh"] = pd.NA

    r_missing = missing_from_floor.copy()
    r_missing["status"] = "MISSING_FROM_FLOOR"

    keep_cols = [
        "product_code",
        "brand",
        "description",
        "department",
        "sizes_in_stock",
        "qty_oh",
        "status"
    ]

    for df in [r_expected, r_unexpected, r_missing]:
        for col in keep_cols:
            if col not in df.columns:
                df[col] = pd.NA

    final_report = pd.concat([
        r_expected[keep_cols],
        r_unexpected[keep_cols],
        r_missing[keep_cols],
    ], ignore_index=True)

    final_report["priority"] = final_report["status"].map({
        "ON_FLOOR_EXPECTED": "OK",
        "ON_FLOOR_UNEXPECTED": "Review",
        "MISSING_FROM_FLOOR": "Action Required"
    })

    final_report["action"] = final_report["status"].map({
        "ON_FLOOR_EXPECTED": "None",
        "ON_FLOOR_UNEXPECTED": "Validate placement / update POS",
        "MISSING_FROM_FLOOR": "Replenish or correct assortment execution"
    })

    # -------------------------
    # Create Excel file in memory
    # -------------------------
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        final_report.to_excel(writer, sheet_name="POS_vs_Floor", index=False)
        missing_by_dept.to_excel(writer, sheet_name="Missing_by_Department", index=False)
        unexpected_by_dept.to_excel(writer, sheet_name="Unexpected_by_Department", index=False)
        summary.to_excel(writer, sheet_name="Executive_Summary", index=False)

        workbook = writer.book
        worksheet = writer.sheets["POS_vs_Floor"]

        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#E6E6E6",
            "border": 1,
            "align": "center"
        })

        ok_fmt = workbook.add_format({"bg_color": "#C6EFCE", "font_color": "#006100"})
        review_fmt = workbook.add_format({"bg_color": "#FFF2CC", "font_color": "#7F6000"})
        action_fmt = workbook.add_format({"bg_color": "#F4CCCC", "font_color": "#990000"})

        for col_num, col_name in enumerate(final_report.columns):
            worksheet.write(0, col_num, col_name, header_fmt)
            worksheet.set_column(col_num, col_num, 20)

        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, len(final_report), len(final_report.columns) - 1)

        status_col = final_report.columns.get_loc("status")

        worksheet.conditional_format(1, status_col, len(final_report), status_col, {
            "type": "text",
            "criteria": "containing",
            "value": "ON_FLOOR_EXPECTED",
            "format": ok_fmt
        })

        worksheet.conditional_format(1, status_col, len(final_report), status_col, {
            "type": "text",
            "criteria": "containing",
            "value": "ON_FLOOR_UNEXPECTED",
            "format": review_fmt
        })

        worksheet.conditional_format(1, status_col, len(final_report), status_col, {
            "type": "text",
            "criteria": "containing",
            "value": "MISSING_FROM_FLOOR",
            "format": action_fmt
        })

    output.seek(0)

    return {
        "summary": summary,
        "final_report": final_report,
        "missing_by_dept": missing_by_dept,
        "unexpected_by_dept": unexpected_by_dept,
        "excel_file": output
    }