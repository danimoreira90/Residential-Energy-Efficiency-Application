import pandas as pd
import streamlit as st

@st.cache
def load_excel_data(sheet_name):
    file_path = r"D:\Pastas\Infnet\Infnet - 2024.2\Projeto de bloco\app_energia\Dados_abertos_Consumo_Mensal.xlsx"
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    # Converter 'Consumo' para float após remover vírgulas
    df['Consumo'] = df['Consumo'].replace(',', '', regex=True).astype(float)
    return df

# Carregar dados de cada planilha
consumo_sam = load_excel_data('CONSUMO E NUMCONS SAM')
consumo_sam_uf = load_excel_data('CONSUMO E NUMCONS SAM UF')
setor_industrial = load_excel_data('SETOR INDUSTRIAL POR RG')
consumo_ben_rg = load_excel_data('CONSUMO_BEN_RG_1970-1989')
consumo_eletrobras = load_excel_data('CONSUMO_ELETROBRAS_1990-2003')

# def plot_consumo_sam(data):
#     st.write("## Consumo e Número de Consumidores por Sistema e Classe")
#     st.bar_chart(data.groupby(['Sistema', 'Classe'])['Consumo'].sum())

def plot_consumo_sam(data):
    # Verifique se as colunas necessárias estão presentes
    if not {'Sistema', 'Classe', 'Consumo'}.issubset(data.columns):
        st.error("As colunas necessárias não estão presentes no DataFrame.")
        st.write(data.columns)  # Mostrar as colunas atuais para debug
        return  

    # Se estiver tudo certo, prossiga com a plotagem
    grouped_data = data.groupby(['Sistema', 'Classe'])['Consumo'].sum()
    st.bar_chart(grouped_data)

def plot_consumo_sam_uf(data):
    st.write("## Consumo e Número de Consumidores por UF")
    st.line_chart(data.groupby('UF')['Consumo'].sum())

def plot_setor_industrial(data):
    st.write("## Consumo por Setor Industrial e Região")
    st.area_chart(data.groupby(['SetorIndustrial', 'Regiao'])['Consumo'].sum())

def plot_consumo_ben_rg(data):
    st.write("## Consumo por Região e Classe (1970-1989)")
    st.line_chart(data.groupby(['Regiao', 'Classe'])['Consumo'].sum())

def plot_consumo_eletrobras(data):
    st.write("## Consumo Eletrobras por Região e Classe (1990-2003)")
    st.line_chart(data.groupby(['Regiao', 'Classe'])['Consumo'].sum())


def tarifas():
    st.title("Visualizações de Consumo de Energia")
    
    # Menu de seleção para escolher a visualização
    option = st.selectbox("Escolha a visualização:", [
        'CONSUMO E NUMCONS SAM', 
        'CONSUMO E NUMCONS SAM UF', 
        'SETOR INDUSTRIAL POR RG', 
        'CONSUMO_BEN_RG_1970-1989', 
        'CONSUMO_ELETROBRAS_1990-2003'
    ],
    key='unique_selectbox_key'
    )
    
    data = load_excel_data(option)

    if option == 'CONSUMO E NUMCONS SAM':
        plot_consumo_sam(data)
    elif option == 'CONSUMO E NUMCONS SAM UF':
        plot_consumo_sam_uf(data)
    elif option == 'SETOR INDUSTRIAL POR RG':
        plot_setor_industrial(data)
    elif option == 'CONSUMO_BEN_RG_1970-1989':
        plot_consumo_ben_rg(data)
    elif option == 'CONSUMO_ELETROBRAS_1990-2003':
        plot_consumo_eletrobras(data)

