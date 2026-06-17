import os
import streamlit as st
from report_generator import generate_report

st.set_page_config(
    page_title="POS Option Count Report Generator",
    layout="wide"
)

DEFAULT_JESTA_PATH = "data/default_jesta_mapping.csv"

st.title("POS Option Count Report Generator")

with st.expander("How to use this app", expanded=True):
    st.markdown("""
    Upload the required files to generate the POS Option Count report.

    **Normal workflow:**
    1. Upload the **POS Option Count** file.
    2. Upload the **Floor Scan File**.
    3. The app will use the default Jesta Mapping file already saved in the app.

    **Only upload a Jesta Mapping file if Head Office has provided a new barcode mapping file.**
    """)

store_name = st.text_input("Store name", value="Richmond")

report_week = st.text_input("Report week / date", value="Week XX")

st.markdown("### 1. POS Option Count File")
pos_file = st.file_uploader(
    "Upload POS Option Count file",
    type=["xlsx"],
    key="pos_file"
)

st.markdown("### 2. Jesta Mapping File")

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
    jesta_file = DEFAULT_JESTA_PATH
    if os.path.exists(DEFAULT_JESTA_PATH):
        st.info("Using default Jesta Mapping file saved in the app.")
    else:
        st.error(
            "Default Jesta Mapping file was not found. "
            "Please create a folder named 'data' and place the file inside it as "
            "'default_jesta_mapping.csv'."
        )

st.markdown("### 3. Floor Scan File")
scan_file = st.file_uploader(
    "Upload Floor Scan File",
    type=["xlsx"],
    key="scan_file"
)

if st.button("Generate Report"):

    if not pos_file or not scan_file:
        st.error("Please upload the POS Option Count file and the Floor Scan file.")
    elif use_custom_jesta and not jesta_file:
        st.error("Please upload the replacement Jesta Mapping file.")
    elif not use_custom_jesta and not os.path.exists(DEFAULT_JESTA_PATH):
        st.error(
            "The default Jesta Mapping file is missing. "
            "Add it to data/default_jesta_mapping.csv or upload a replacement file."
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
