import streamlit as st
import pandas as pd

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

# Exibir amostras dos dados
st.header("Amostra de Dados")
st.write("Abaixo está uma amostra dos dados que serão utilizados ao longo do projeto.")

# Carregar e exibir os dados (substitua o caminho com o local correto dos seus datasets)
df = pd.read_csv('MidCase_2030_efficiency1_dissipation0.5_value.csv')

# Exibir as primeiras 5 linhas do DataFrame
st.dataframe(df.head())

# Nota final
st.info("Esta é uma versão demo da aplicação. Os próximos passos incluirão a integração completa dos dados e a implementação de funcionalidades avançadas.")
