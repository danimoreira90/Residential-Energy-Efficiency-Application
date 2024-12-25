import pandas as pd
import streamlit as st


@st.cache_data
def load_excel_sheets(filename):
    xl = pd.ExcelFile(filename)
    dfs = {}
    for sheet_name in xl.sheet_names:
        dfs[sheet_name] = xl.parse(sheet_name)
    return dfs
