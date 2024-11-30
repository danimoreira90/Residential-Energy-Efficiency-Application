import streamlit as st
# Importa as funções das páginas da pasta pages
from pages.home import home
from pages.data_analysis import data_analysis
from pages.upload_download import upload_download
from pages.settings import settings

# Configuração da página
st.set_page_config(page_title="Eficiência Energética Residencial", layout="wide")

# Dicionário que mapeia nomes para funções
pages = {
    "Home": home,
    "Análise de Dados": data_analysis,
    "Upload/Download de Dados": upload_download,
    "Configurações": settings
}

# Menu lateral para seleção de página
st.sidebar.title("Navegação")
choice = st.sidebar.radio("Escolha uma página", list(pages.keys()))

# Chamada da função que renderiza a página escolhida
pages[choice]()