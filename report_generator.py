import pandas as pd
from io import BytesIO


def clean_text(series):
    return series.astype(str).str.strip()


def validate_columns(df, required_cols, file_name):
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"{file_name} is missing required columns: {missing}")


def generate_report(pos_file, jesta_file, scan_file):
    warnings = []

    # -------------------------
    # Load scan file
    # -------------------------
    # The scan file does not need a header.
    # The app always treats the first column as the scanned barcode column.
    scan_list = pd.read_excel(
        scan_file,
        sheet_name=0,
        dtype=str,
        header=None
    )

    if scan_list.empty:
        raise ValueError("The scan file is empty.")

    scan_list = scan_list.iloc[:, [0]].copy()
    scan_list.columns = ["bar_code_id"]

    scan_list["bar_code_id"] = clean_text(scan_list["bar_code_id"])

    # Drop common accidental header values if a user still uploads a file with a header.
    header_values = {
        "bar_code_id",
        "barcode",
        "bar code",
        "bar_code",
        "scanned barcode",
        "scan",
        "nan"
    }

    scan_list = scan_list[
        scan_list["bar_code_id"].notna()
        & (scan_list["bar_code_id"] != "")
        & (~scan_list["bar_code_id"].str.lower().isin(header_values))
    ].copy()

    total_scans = len(scan_list)
    duplicate_scans = total_scans - scan_list["bar_code_id"].nunique()

    if duplicate_scans > 0:
        warnings.append(f"{duplicate_scans} duplicate barcode scans were detected.")

    if scan_list.empty:
        raise ValueError("No valid barcodes were found in the scan file.")

    # -------------------------
    # Load Jesta mapping
    # -------------------------
    jesta_map = pd.read_csv(jesta_file, low_memory=False, dtype=str)
    jesta_map.columns = jesta_map.columns.astype(str).str.strip()

    validate_columns(
        jesta_map,
        ["BAR_CODE_ID", "VENDOR_STYLE_CODE"],
        "Jesta Mapping File"
    )

    jesta_map = jesta_map.rename(columns={
        "BAR_CODE_ID": "bar_code_id",
        "VENDOR_STYLE_CODE": "product_code",
        "BRAND": "brand",
        "DESCRIPTION": "description",
    })

    jesta_map["bar_code_id"] = clean_text(jesta_map["bar_code_id"])
    jesta_map["product_code"] = clean_text(jesta_map["product_code"])

    jesta_map = jesta_map[
        jesta_map["bar_code_id"].notna()
        & (jesta_map["bar_code_id"] != "")
        & (jesta_map["bar_code_id"].str.lower() != "nan")
        & jesta_map["product_code"].notna()
        & (jesta_map["product_code"] != "")
        & (jesta_map["product_code"].str.lower() != "nan")
    ].copy()

    jesta_map = jesta_map.drop_duplicates(subset=["bar_code_id"]).copy()

    # -------------------------
    # Match scan to product codes
    # -------------------------
    scan_with_products = scan_list.merge(
        jesta_map,
        on="bar_code_id",
        how="left"
    )

    unmatched_scans = scan_with_products["product_code"].isna().sum()

    if unmatched_scans > 0:
        warnings.append(
            f"{unmatched_scans} scanned barcodes were not found in the Jesta mapping file."
        )

    scanned_all = scan_with_products[
        scan_with_products["product_code"].notna()
    ].copy()

    scanned_all["product_code"] = clean_text(scanned_all["product_code"])
    scanned_unique = scanned_all.drop_duplicates(subset=["product_code"]).copy()

    # -------------------------
    # Load POS Option Count
    # -------------------------
    try:
        pos = pd.read_excel(
            pos_file,
            sheet_name="Master",
            header=2,
            dtype=str
        )
    except Exception:
        raise ValueError(
            "Could not read the POS Option Count file. "
            "Please confirm it has a sheet named 'Master' and that headers start on row 3."
        )

    pos.columns = pos.columns.astype(str).str.strip()

    validate_columns(
        pos,
        ["VENDOR_STYLE_NO"],
        "POS Option Count File"
    )

    pos = pos.rename(columns={
        "BRAND": "brand",
        "DESCRIPTION": "description",
        "VENDOR_STYLE_NO": "product_code",
        "DEPARTMENT": "department",
        "SIZES_IN_STOCK": "sizes_in_stock",
        "QTY_ON_HAND": "qty_oh",
    })

    pos["product_code"] = clean_text(pos["product_code"])

    if "qty_oh" in pos.columns:
        pos["qty_oh"] = pd.to_numeric(pos["qty_oh"], errors="coerce").fillna(0)
    else:
        pos["qty_oh"] = 0
        warnings.append("POS file did not include QTY_ON_HAND. Priority ranking will be limited.")

    for col in ["brand", "description", "department", "sizes_in_stock"]:
        if col not in pos.columns:
            pos[col] = pd.NA

    pos = pos[
        pos["product_code"].notna()
        & (pos["product_code"] != "")
        & (pos["product_code"].str.lower() != "nan")
    ].copy()

    if pos.empty:
        raise ValueError("No valid product codes were found in the POS file.")

    # -------------------------
    # Compare POS vs floor scan
    # -------------------------
    on_floor_expected = scanned_unique.merge(
        pos,
        on="product_code",
        how="inner",
        suffixes=("_scan", "_pos")
    )

    on_floor_unexpected = scanned_unique[
        ~scanned_unique["product_code"].isin(pos["product_code"])
    ].copy()

    missing_from_floor = pos[
        ~pos["product_code"].isin(scanned_unique["product_code"])
    ].copy()

    pos_n = pos["product_code"].nunique()
    scanned_n = scanned_unique["product_code"].nunique()
    found_n = on_floor_expected["product_code"].nunique()
    unexpected_n = on_floor_unexpected["product_code"].nunique()
    missing_n = missing_from_floor["product_code"].nunique()

    completion_rate = round((found_n / pos_n) * 100, 1) if pos_n else 0

    summary = pd.DataFrame({
        "Metric": [
            "POS Expected Options",
            "Unique Scanned Options",
            "On Floor & Expected",
            "On Floor but Unexpected",
            "Expected but Missing",
            "Completion Rate"
        ],
        "Value": [
            pos_n,
            scanned_n,
            found_n,
            unexpected_n,
            missing_n,
            f"{completion_rate}%"
        ]
    })

    # -------------------------
    # Priority missing products
    # -------------------------
    priority_missing = (
        missing_from_floor
        .sort_values("qty_oh", ascending=False)
        .loc[:, ["product_code", "brand", "description", "department", "sizes_in_stock", "qty_oh"]]
        .head(50)
        .copy()
    )

    priority_missing["priority_reason"] = "Missing from floor with stock on hand"

    # -------------------------
    # Group summaries
    # -------------------------
    missing_by_dept = (
        missing_from_floor
        .assign(department=lambda df: df["department"].fillna("UNKNOWN"))
        .groupby("department")["product_code"]
        .nunique()
        .reset_index(name="missing_count")
        .sort_values("missing_count", ascending=False)
    )

    missing_by_brand = (
        missing_from_floor
        .assign(brand=lambda df: df["brand"].fillna("UNKNOWN"))
        .groupby("brand")
        .agg(
            missing_count=("product_code", "nunique"),
            stock_on_hand=("qty_oh", "sum")
        )
        .reset_index()
        .sort_values(["missing_count", "stock_on_hand"], ascending=False)
    )

    if "brand" not in on_floor_unexpected.columns:
        on_floor_unexpected["brand"] = "UNKNOWN"

    unexpected_by_brand = (
        on_floor_unexpected
        .assign(brand=lambda df: df["brand"].fillna("UNKNOWN"))
        .groupby("brand")["product_code"]
        .nunique()
        .reset_index(name="unexpected_count")
        .sort_values("unexpected_count", ascending=False)
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
    # Final report
    # -------------------------
    r_expected = on_floor_expected.copy()
    r_expected["status"] = "ON_FLOOR_EXPECTED"

    if "brand_pos" in r_expected.columns:
        r_expected["brand"] = r_expected["brand_pos"]
    elif "brand_scan" in r_expected.columns:
        r_expected["brand"] = r_expected["brand_scan"]

    if "description_pos" in r_expected.columns:
        r_expected["description"] = r_expected["description_pos"]
    elif "description_scan" in r_expected.columns:
        r_expected["description"] = r_expected["description_scan"]

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
    # Excel export
    # -------------------------
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        summary.to_excel(writer, sheet_name="Executive_Summary", index=False)
        priority_missing.to_excel(writer, sheet_name="Priority_Missing", index=False)
        missing_by_dept.to_excel(writer, sheet_name="Missing_by_Department", index=False)
        missing_by_brand.to_excel(writer, sheet_name="Missing_by_Brand", index=False)
        unexpected_by_brand.to_excel(writer, sheet_name="Unexpected_by_Brand", index=False)
        unexpected_by_dept.to_excel(writer, sheet_name="Unexpected_by_Department", index=False)
        final_report.to_excel(writer, sheet_name="POS_vs_Floor", index=False)

        workbook = writer.book

        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#E6E6E6",
            "border": 1,
            "align": "center"
        })

        action_fmt = workbook.add_format({
            "bg_color": "#F4CCCC",
            "font_color": "#990000"
        })

        review_fmt = workbook.add_format({
            "bg_color": "#FFF2CC",
            "font_color": "#7F6000"
        })

        ok_fmt = workbook.add_format({
            "bg_color": "#C6EFCE",
            "font_color": "#006100"
        })

        sheet_frames = {
            "Executive_Summary": summary,
            "Priority_Missing": priority_missing,
            "Missing_by_Department": missing_by_dept,
            "Missing_by_Brand": missing_by_brand,
            "Unexpected_by_Brand": unexpected_by_brand,
            "Unexpected_by_Department": unexpected_by_dept,
            "POS_vs_Floor": final_report
        }

        for sheet_name, df in sheet_frames.items():
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes(1, 0)

            for col_num, col_name in enumerate(df.columns):
                worksheet.write(0, col_num, col_name, header_fmt)
                worksheet.set_column(col_num, col_num, 22)

            if len(df) > 0:
                worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

        worksheet = writer.sheets["POS_vs_Floor"]
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
        "priority_missing": priority_missing,
        "missing_by_dept": missing_by_dept,
        "missing_by_brand": missing_by_brand,
        "unexpected_by_brand": unexpected_by_brand,
        "unexpected_by_dept": unexpected_by_dept,
        "final_report": final_report,
        "excel_file": output,
        "warnings": warnings
    }
