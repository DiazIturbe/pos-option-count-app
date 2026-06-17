import os
from pathlib import Path

import gdown
import streamlit as st

from report_generator import generate_report


st.set_page_config(
    page_title="POS Option Count Report Generator",
    page_icon="📦",
    layout="wide"
)

DEFAULT_JESTA_PATH = "data/default_jesta_mapping.csv"
GOOGLE_DRIVE_FILE_ID = "1xtsJW8H_Q-kRL8Sqb5raUFG2m9ByYU14"


st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1250px;
}

.hero-card {
    background: linear-gradient(135deg, #111827 0%, #374151 100%);
    padding: 2rem;
    border-radius: 22px;
    margin-bottom: 1.5rem;
    color: white;
}

.hero-card h1 {
    color: white;
    margin-bottom: 0.35rem;
    font-size: 2.4rem;
    font-weight: 800;
}

.hero-card p {
    color: #E5E7EB;
    font-size: 1.05rem;
    margin-bottom: 0;
}

[data-testid="stFileUploader"] {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 14px;
    padding: 0.75rem;
}

.stButton > button {
    width: 100%;
    border-radius: 12px;
    height: 3.1rem;
    font-weight: 800;
    border: 0;
}
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


st.markdown("""
<div class="hero-card">
    <h1>POS Option Count Report Generator</h1>
    <p>Upload the weekly POS Option Count and floor scan file to validate floor execution, identify missing styles, and download the report.</p>
</div>
""", unsafe_allow_html=True)

with st.expander("How to use this app", expanded=True):
    st.markdown("""
    **Normal workflow**

    1. Upload the **POS Option Count** file.
    2. Upload the **Floor Scan File**. The scan file does **not** need a header; the app automatically treats the first column as scanned barcodes.
    3. The app automatically uses the default Jesta Mapping file.
    4. Click **Generate Report** and download the Excel file.

    **Only upload a different Jesta Mapping file if Head Office has provided a new barcode mapping file.**
    """)

meta_col1, meta_col2 = st.columns(2)

with meta_col1:
    store_name = st.text_input("Store name", value="Richmond")

with meta_col2:
    report_week = st.text_input("Report week / date", value="Week XX")

st.markdown("### Required uploads")

upload_col1, upload_col2 = st.columns(2)

with upload_col1:
    st.markdown("#### 1. POS Option Count File")
    pos_file = st.file_uploader(
        "Upload POS Option Count file",
        type=["xlsx"],
        key="pos_file"
    )

with upload_col2:
    st.markdown("#### 2. Floor Scan File")
    scan_file = st.file_uploader(
        "Upload Floor Scan File",
        type=["xlsx"],
        key="scan_file"
    )

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

    if not pos_file or not scan_file:
        st.error("Please upload the POS Option Count file and the Floor Scan file.")

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

            st.subheader("Executive Summary")
            st.dataframe(result["summary"], use_container_width=True)

            try:
                summary_lookup = dict(zip(result["summary"]["Metric"], result["summary"]["Value"]))
                metric_cols = st.columns(4)
                metric_cols[0].metric("POS Expected", summary_lookup.get("POS Expected Options", "—"))
                metric_cols[1].metric("Scanned", summary_lookup.get("Unique Scanned Options", "—"))
                metric_cols[2].metric("Missing", summary_lookup.get("Expected but Missing", "—"))
                metric_cols[3].metric("Completion", summary_lookup.get("Completion Rate", "—"))
            except Exception:
                pass

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
