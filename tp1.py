import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
from data_processing import (
    load_cleaned_data, clean_data, plot_correlation_matrix, plot_efficiency_distribution,
    plot_region_efficiency, plot_monthly_evolution, describe_data
)
from load_excel_data import load_excel_sheets

st.set_page_config(layout="wide")


# Título do projeto
st.title("🌍 Eficiência Energética Residencial - Projeto ODS7")

# Descrição do problema de negócio
st.header("Problema de Negócio")
st.write("""
O consumo de energia em residências muitas vezes é ineficiente, resultando em altos custos para os consumidores e impacto ambiental significativo. Este projeto visa desenvolver uma aplicação que permita o monitoramento e a análise do consumo energético em tempo real, com o objetivo de reduzir o desperdício de energia e promover a eficiência energética em residências.
""")

# Objetivos do Projeto
st.header("Objetivos do Projeto")
st.write("""
1. Reduzir o consumo energético em residências monitoradas em pelo menos 10% no período de um ano.
2. Aumentar a conscientização dos usuários sobre o impacto de seu consumo energético.
3. Oferecer uma ferramenta interativa e acessível que permita o monitoramento e a análise do consumo energético em tempo real.
""")

# Links úteis
st.header("Links Úteis")
st.markdown("""
- [ODS7 - Energia Limpa e Acessível](https://www.un.org/sustainabledevelopment/energy/)
- [NREL - National Renewable Energy Laboratory](https://www.nrel.gov/)
- [Documentação Streamlit](https://docs.streamlit.io/)
""")

st.header("Amostra de Dados Processados")

df = load_cleaned_data()
df = clean_data(df)
st.dataframe(df.head())

# Exibir visualizações
if st.button("Exibir Matriz de Correlação"):
    plot_correlation_matrix(df, st)

if st.button("Distribuição da Eficiência por Região"):
    plot_efficiency_distribution(df, st)

if st.button("Eficiência por Região"):
    plot_region_efficiency(df, st)

if st.button("Evolução da Energia e Lucro por Mês"):
    plot_monthly_evolution(df, st)

st.info("Aplicação desenvolvida para análise de eficiência energética em residências.")

# Caminho para o arquivo Excel
filepath = "D:\Pastas\Infnet\Infnet - 2024.2\Projeto de bloco\TP1\Dados_abertos_Consumo_Mensal.xlsx"

# Carrega todos os dados
data_sheets = load_excel_sheets(filepath)

# Adiciona um título ao app
st.title('Visualização de Dados de Consumo Energético - EPE - Empresa de Pesquisa Energética')

if 'sheet_name' not in st.session_state:
    st.session_state.sheet_name = list(data_sheets.keys())[0]

# Cria uma seleção para as subplanilhas
sheet_name = st.selectbox('Escolha uma subplanilha para visualizar', list(data_sheets.keys()))

# Exibe os dados da subplanilha escolhida
st.write(f"Exibindo dados de: {sheet_name}")
st.dataframe(data_sheets[sheet_name])


