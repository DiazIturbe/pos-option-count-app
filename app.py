import os
import base64
from pathlib import Path
from io import BytesIO
from datetime import date

import gdown
import pandas as pd
import streamlit as st

from report_generator import generate_report


st.set_page_config(
    page_title="Floor Inventory Validation Platform",
    page_icon="▌▌✓",
    layout="wide"
)

DEFAULT_JESTA_PATH = "data/default_jesta_mapping.csv"
GOOGLE_DRIVE_FILE_ID = "1xtsJW8H_Q-kRL8Sqb5raUFG2m9ByYU14"
HERO_IMAGE_PATH = "assets/hero_image.jpg"


def get_hero_background_css():
    if os.path.exists(HERO_IMAGE_PATH):
        with open(HERO_IMAGE_PATH, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        return f"""
        background:
            linear-gradient(135deg, rgba(17,24,39,0.88), rgba(37,99,235,0.58)),
            url("data:image/jpg;base64,{encoded}");
        background-size: cover;
        background-position: center;
        """
    return """
    background: linear-gradient(135deg, #111827 0%, #2563EB 100%);
    """


hero_background = get_hero_background_css()


st.markdown(f"""
<style>
.block-container {{
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1250px;
}}

.hero-card {{
    {hero_background}
    padding: 2.4rem;
    border-radius: 24px;
    margin-bottom: 1.5rem;
    color: white;
    box-shadow: 0 12px 30px rgba(17, 24, 39, 0.24);
}}

.brand-label {{
    font-size: 0.9rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #DBEAFE;
    font-weight: 800;
    margin-bottom: 0.7rem;
}}

.barcode-icon {{
    display: inline-block;
    font-size: 1.4rem;
    font-weight: 900;
    letter-spacing: 0.12rem;
    margin-bottom: 0.7rem;
    color: white;
}}

.hero-card h1 {{
    color: white;
    margin-bottom: 0.35rem;
    font-size: 2.55rem;
    font-weight: 900;
}}

.hero-card p {{
    color: #E5E7EB;
    font-size: 1.08rem;
    margin-bottom: 0;
    max-width: 760px;
}}

.creator-pill {{
    display: inline-block;
    margin-top: 1.1rem;
    padding: 0.42rem 0.85rem;
    border: 1px solid rgba(229, 231, 235, 0.65);
    border-radius: 999px;
    color: #F9FAFB;
    font-size: 0.92rem;
    background: rgba(17, 24, 39, 0.28);
}}

.version-line {{
    margin-top: 0.75rem;
    color: #D1D5DB;
    font-size: 0.85rem;
}}

.preview-card {{
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 18px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}}

[data-testid="stFileUploader"] {{
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 14px;
    padding: 0.75rem;
}}

.stButton > button {{
    width: 100%;
    border-radius: 12px;
    height: 3.2rem;
    font-weight: 900;
    border: 0;
    background: linear-gradient(135deg, #111827 0%, #2563EB 100%);
    color: white;
    font-size: 1.05rem;
    box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
}}

.stButton > button:hover {{
    background: linear-gradient(135deg, #1F2937 0%, #1D4ED8 100%);
    color: white;
}}
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def download_jesta_mapping_from_drive():
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    output_path = data_dir / "default_jesta_mapping.csv"
    url = f"https://drive.google.com/uc?id={GOOGLE_DRIVE_FILE_ID}"

    gdown.download(
        url=url,
        output=str(output_path),
        quiet=False
    )

    if not output_path.exists():
        raise RuntimeError("Jesta Mapping file was not downloaded.")

    if output_path.stat().st_size < 1000:
        raise RuntimeError(
            "Downloaded file is too small. Google Drive may have returned an error page."
        )

    return str(output_path)


def get_default_jesta_file():
    if os.path.exists(DEFAULT_JESTA_PATH):
        return DEFAULT_JESTA_PATH

    return download_jesta_mapping_from_drive()


def build_scan_excel_from_text(barcode_text):
    raw_lines = [
        line.strip()
        for line in barcode_text.splitlines()
        if line.strip()
    ]

    valid_barcodes = []
    invalid_lines = []

    for line in raw_lines:
        cleaned = line.strip().replace(" ", "")

        if cleaned.isdigit() and len(cleaned) in [8, 12, 13, 14]:
            valid_barcodes.append(cleaned)
        else:
            invalid_lines.append(line)

    scan_df = pd.DataFrame(valid_barcodes, columns=["scanned_barcode"])

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        scan_df.to_excel(writer, index=False, header=False)

    output.seek(0)

    return output, valid_barcodes, invalid_lines


st.markdown("""
<div class="hero-card">
    <div class="brand-label">DDI Data Solutions</div>
    <div class="barcode-icon">▌▌▌▌▌ ✓</div>
    <h1>Floor Inventory Validation Platform</h1>
    <p>POS Option Count automation for retail store execution. Validate scanned floor inventory, identify missing styles, and generate actionable operational reports.</p>
    <div class="creator-pill">Created by Diego Díaz Iturbe · Retail Analytics • Automation • Operations</div>
    <div class="version-line">v1.2.0 · Last updated June 2026</div>
</div>
""", unsafe_allow_html=True)


tab_generate, tab_preview, tab_about = st.tabs([
    "Generate Report",
    "Preview Example",
    "About"
])


with tab_generate:
    with st.expander("How to use this app", expanded=False):
        st.markdown("""
        **Workflow**

        1. Upload the **POS Option Count** file.
        2. Choose how to provide the floor scan:
           - Upload an Excel scan file, or
           - Paste the barcode list from Notes.
        3. The app automatically uses the default Jesta Mapping file.
        4. Click **Generate Report** and download the Excel report.

        **Phone workflow**

        Scan into Apple Notes, copy the full list, then paste it into the app.
        """)

    meta_col1, meta_col2 = st.columns(2)

    with meta_col1:
        store_name = st.text_input(
            "Store name",
            value="",
            placeholder="Enter store name"
        )

    with meta_col2:
        report_date = st.date_input(
            "Report date",
            value=date.today()
        )

    report_week = report_date.strftime("%Y-%m-%d")

    st.markdown("### Required uploads")

    st.markdown("#### 1. POS Option Count File")
    pos_file = st.file_uploader(
        "Upload POS Option Count file",
        type=["xlsx"],
        key="pos_file"
    )

    st.markdown("#### 2. Floor Scan Input")

    scan_input_method = st.radio(
        "Choose scan input method",
        ["Paste barcode list from Notes", "Upload Excel scan file"],
        horizontal=True
    )

    scan_file = None
    pasted_valid_barcodes = []
    pasted_invalid_lines = []

    if scan_input_method == "Upload Excel scan file":
        scan_file = st.file_uploader(
            "Upload Floor Scan File",
            type=["xlsx"],
            key="scan_file"
        )

    else:
        barcode_text = st.text_area(
            "Paste barcode list here",
            height=300,
            placeholder="Scan or paste barcodes here, one per line..."
        )

        if barcode_text.strip():
            scan_file, pasted_valid_barcodes, pasted_invalid_lines = build_scan_excel_from_text(barcode_text)

            metric_cols = st.columns(3)
            metric_cols[0].metric("Valid Scans", len(pasted_valid_barcodes))
            metric_cols[1].metric("Unique Scans", len(set(pasted_valid_barcodes)))
            metric_cols[2].metric("Duplicates", len(pasted_valid_barcodes) - len(set(pasted_valid_barcodes)))

            if pasted_invalid_lines:
                st.warning(
                    f"{len(pasted_invalid_lines)} line(s) were ignored because they were not valid barcode numbers."
                )

                with st.expander("Show ignored lines"):
                    st.write(pasted_invalid_lines)

    st.markdown("### Jesta Mapping")

    use_custom_jesta = st.checkbox(
        "Upload a different Jesta Mapping file",
        value=False
    )

    if use_custom_jesta:
        jesta_file = st.file_uploader(
            "Upload replacement Jesta Mapping File",
            type=["csv"],
            key="jesta_file"
        )
    else:
        try:
            with st.spinner("Loading default Jesta Mapping file..."):
                jesta_file = get_default_jesta_file()

            st.info("Using default Jesta Mapping file.")

        except Exception as e:
            jesta_file = None
            st.error(
                "Default Jesta Mapping file could not be loaded. "
                "Please upload a replacement Jesta Mapping file."
            )
            st.exception(e)

    st.markdown("---")

    if st.button("Generate Report"):

        if not store_name.strip():
            st.error("Please enter the store name.")

        elif not pos_file:
            st.error("Please upload the POS Option Count file.")

        elif not scan_file:
            st.error("Please provide the Floor Scan input using Excel upload or pasted barcode list.")

        elif use_custom_jesta and not jesta_file:
            st.error("Please upload the replacement Jesta Mapping file.")

        elif not use_custom_jesta and not jesta_file:
            st.error(
                "The default Jesta Mapping file is missing or could not be downloaded. "
                "Upload a replacement file or check the Google Drive sharing settings."
            )

        else:
            try:
                with st.spinner("Generating report..."):
                    result = generate_report(
                        pos_file=pos_file,
                        jesta_file=jesta_file,
                        scan_file=scan_file
                    )

                st.success("Report generated successfully.")

                if "warnings" in result and result["warnings"]:
                    st.warning("Some warnings were detected:")
                    for warning in result["warnings"]:
                        st.write(f"- {warning}")

                try:
                    summary_lookup = dict(zip(result["summary"]["Metric"], result["summary"]["Value"]))
                    metric_cols = st.columns(4)
                    metric_cols[0].metric("POS Expected", summary_lookup.get("POS Expected Options", "—"))
                    metric_cols[1].metric("Scanned", summary_lookup.get("Unique Scanned Options", "—"))
                    metric_cols[2].metric("Missing", summary_lookup.get("Expected but Missing", "—"))
                    metric_cols[3].metric("Completion", summary_lookup.get("Completion Rate", "—"))
                except Exception:
                    pass

                st.subheader("Executive Summary")
                st.dataframe(result["summary"], use_container_width=True)

                if "priority_missing" in result:
                    st.subheader("Priority Missing Products")
                    st.caption(
                        "Products expected on the floor but not scanned, sorted by highest stock on hand."
                    )
                    st.dataframe(result["priority_missing"], use_container_width=True)

                if "missing_by_dept" in result:
                    st.subheader("Missing by Department")
                    st.dataframe(result["missing_by_dept"], use_container_width=True)

                if "missing_by_brand" in result:
                    st.subheader("Missing by Brand")
                    st.dataframe(result["missing_by_brand"], use_container_width=True)

                if "unexpected_by_brand" in result:
                    st.subheader("Unexpected by Brand")
                    st.dataframe(result["unexpected_by_brand"], use_container_width=True)
                elif "unexpected_by_dept" in result:
                    st.subheader("Unexpected by Department")
                    st.dataframe(result["unexpected_by_dept"], use_container_width=True)

                st.subheader("Full POS vs Floor Report")
                st.dataframe(result["final_report"], use_container_width=True)

                clean_store = store_name.replace(" ", "_")
                clean_week = report_week.replace(" ", "_")

                st.download_button(
                    label="Download Excel Report",
                    data=result["excel_file"],
                    file_name=f"POS_Option_Count_Report_{clean_store}_{clean_week}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error("The report could not be generated.")
                st.exception(e)


with tab_preview:
    st.markdown("## Preview Example")
    st.markdown(
        "This section shows what the dashboard and report output look like using sample data. "
        "No company files are required to view this preview."
    )

    sample_cols = st.columns(4)
    sample_cols[0].metric("POS Expected", "542")
    sample_cols[1].metric("Scanned", "511")
    sample_cols[2].metric("Missing", "31")
    sample_cols[3].metric("Completion", "94.3%")

    st.markdown("### Sample Priority Missing Products")

    sample_priority = pd.DataFrame({
        "product_code": ["STYLE-001", "STYLE-002", "STYLE-003", "STYLE-004", "STYLE-005"],
        "brand": ["Nike", "Adidas", "New Balance", "Puma", "Asics"],
        "description": [
            "High-demand footwear style",
            "Core lifestyle footwear option",
            "Seasonal running style",
            "Apparel feature style",
            "Performance footwear option"
        ],
        "department": [
            "Mens Footwear",
            "Womens Footwear",
            "Mens Footwear",
            "Apparel",
            "Womens Footwear"
        ],
        "qty_oh": [18, 14, 11, 9, 7],
        "priority_reason": [
            "Missing from floor with stock on hand",
            "Missing from floor with stock on hand",
            "Missing from floor with stock on hand",
            "Missing from floor with stock on hand",
            "Missing from floor with stock on hand"
        ]
    })

    st.dataframe(sample_priority, use_container_width=True)

    st.markdown("### Sample Missing by Department")

    sample_missing_dept = pd.DataFrame({
        "department": ["Mens Footwear", "Womens Footwear", "Apparel", "Accessories"],
        "missing_count": [14, 9, 5, 3]
    })

    st.bar_chart(sample_missing_dept.set_index("department"))

    st.markdown("### What the Excel report includes")

    st.markdown("""
    The downloaded report includes multiple sheets:

    - **Executive Summary** — key totals and completion rate.
    - **Priority Missing** — missing products ranked by stock on hand.
    - **Missing by Department** — operational summary by area.
    - **Missing by Brand** — brand-level execution opportunities.
    - **Unexpected by Brand** — items scanned on the floor but not expected in POS.
    - **POS vs Floor** — full item-level report.
    """)


with tab_about:
    st.markdown("## About this project")

    st.markdown("""
    **Floor Inventory Validation Platform** is a workflow automation project created under **DDI Data Solutions**.

    It was designed to reduce manual work in retail floor execution audits by automating the comparison between:

    - Weekly POS Option Count files
    - Floor scan barcode lists
    - Product/barcode mapping data

    The system generates a structured report identifying:

    - Products expected and found on the floor
    - Products expected but missing
    - Unexpected scanned products
    - Priority missing styles based on stock on hand
    """)

    st.markdown("---")

    st.markdown("""
    ### Project Story

    **Business problem:**  
    Store teams often need to manually compare POS Option Count files against floor scans to identify missing products and execution gaps.

    **Solution:**  
    This platform automates barcode matching, floor validation, exception detection, and report generation.

    **Operational value:**  
    The workflow reduces manual reconciliation time, standardizes execution audits, and creates actionable reports for store teams.

    ### Created by Diego Díaz Iturbe

    **Retail Analytics • Automation • Operations**
    """)
