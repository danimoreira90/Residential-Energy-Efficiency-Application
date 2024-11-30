import streamlit as st
import pandas as pd
import numpy as np

@st.cache_data  
def tarifas():
    st.title("Visualização das Tarifas Homologadas")
    data = load_data()  # Função que precisa ser definida para carregar os dados

    # Dropdown para seleção de distribuidora
    distribuidora = st.selectbox("Escolha a Distribuidora", np.sort(data['SigAgente'].unique()))
    filtered_data = data[data['SigAgente'] == distribuidora]

    # Gráfico de barras para TUSD e TE
    st.bar_chart(filtered_data[['VlrTusd', 'VlrTe']])

    # Tabela detalhada
    st.write(filtered_data)

def load_data():
    # Carregar e retornar o DataFrame
    return pd.read_csv(r"D:\Pastas\Infnet\Infnet - 2024.2\Projeto de bloco\Dados\tarifas-homologadas-distribuidoras-energia-eletrica (1).csv",    sep=';',  # Verifique se o delimitador está correto
    encoding='latin1',  # Ou outro encoding apropriado
    header=0)  # Se a primeira linha contém os cabeçalhos das colunas)
    print(df.columns) 

