import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests

@st.cache_data  
def load_all_data():
    file_path = 'D:\\Pastas\\Infnet\\Infnet - 2024.2\\Projeto de bloco\\TP1\\Dados_abertos_Consumo_Mensal.xlsx'
    sheets = {
        'CONSUMO E NUMCONS SAM': None,
        'CONSUMO E NUMCONS SAM UF': None,
        'SETOR INDUSTRIAL POR RG': None,
        'CONSUMO_BEN_RG_1970-1989': None,
        'CONSUMO_ELETROBRAS_1990-2003': None,
        'ANALISE CONS NUMCONS SAM': None,
        'ANALISE CONS NUMCONS SAM UF': None,
        'ANALISE SETOR IND POR RG': None
    }
    
    for sheet_name in sheets.keys():
        sheets[sheet_name] = pd.read_excel(file_path, sheet_name=sheet_name)
    
    return sheets


import streamlit as st
import pandas as pd

def load_all_data():
    file_path = 'D:\\Pastas\\Infnet\\Infnet - 2024.2\\Projeto de bloco\\TP1\\Dados_abertos_Consumo_Mensal.xlsx'
    sheets = {
        'CONSUMO E NUMCONS SAM': None,
        'CONSUMO E NUMCONS SAM UF': None,
        'SETOR INDUSTRIAL POR RG': None,
        'CONSUMO_BEN_RG_1970-1989': None,
        'CONSUMO_ELETROBRAS_1990-2003': None,
        'ANALISE CONS NUMCONS SAM': None,
        'ANALISE CONS NUMCONS SAM UF': None,
        'ANALISE SETOR IND POR RG': None
    }
    
    for sheet_name in sheets.keys():
        sheets[sheet_name] = pd.read_excel(file_path, sheet_name=sheet_name)
    
    return sheets

def consumo_data_page():
    st.title('Visualização de Dados de Consumo de Energia via API')
    data_sheets = load_all_data()


    response = requests.get("http://localhost:8000/sheets")
    sheets = response.json()['sheets']

    sheet_options = list(data_sheets.keys())
    selected_sheet = st.selectbox('Escolha a planilha para visualizar:', sheet_options)

    data_response = requests.get(f"http://localhost:8000/data/{selected_sheet}")
    data = data_response.json()['data']

    data = data_sheets[selected_sheet]
    st.write(f"Visualizando dados de: {selected_sheet}")
    st.dataframe(data)

def fetch_data_from_api(sheet_name):
    response = requests.get(f"http://localhost:8000/data/{sheet_name}")
    if response.status_code == 200:
        data = response.json()['data']
        return pd.DataFrame(data)
    else:
        st.error("Falha ao buscar dados da API.")
        return pd.DataFrame()

def consumo_dados():
    st.title('Dados de Consumo Energético')

    sheets_response = requests.get("http://localhost:8000/sheets")
    if sheets_response.status_code == 200:
        sheets = sheets_response.json()['sheets']
        selected_sheet = st.selectbox('Selecione a planilha:', sheets)
        
        if st.button('Carregar Dados'):
            data_df = fetch_data_from_api(selected_sheet)
            if not data_df.empty:
                st.dataframe(data_df)
            else:
                st.write("Nenhum dado disponível para mostrar.")
    else:
        st.error("Falha ao obter a lista de planilhas da API.")