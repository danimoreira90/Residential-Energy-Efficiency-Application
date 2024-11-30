import streamlit as st
import matplotlib.pyplot as plt
from wordcloud import WordCloud

# Importações dos módulos para cada página
from data_processing import (
    load_cleaned_data, clean_data, plot_correlation_matrix, plot_efficiency_distribution,
    plot_region_efficiency, plot_monthly_evolution, describe_data
)
from load_excel_data import load_excel_sheets

# Configuração da página
st.set_page_config(page_title="Eficiência Energética Residencial", layout="wide")

def home():
    st.title("🌍 Eficiência Energética Residencial - Projeto ODS7")
    
    # Introdução ao projeto
    st.markdown("""
    ## Visão Geral
    Em um mundo onde a sustentabilidade se torna cada vez mais crucial, o **Projeto ODS7** se destaca 
    como uma iniciativa inovadora voltada para a **melhoria da eficiência energética em residências**. 
    Este projeto não só almeja a redução do consumo energético, mas também busca integrar soluções 
    energéticas limpas e sustentáveis que contribuam para um futuro mais verde.
    """, unsafe_allow_html=True)

    # Objetivos do projeto
    st.markdown("""
    ## Objetivos
    1. **Redução de Consumo:** Diminuir o consumo energético em residências monitoradas em pelo menos 10% ao ano.
    2. **Conscientização:** Elevar a conscientização dos usuários sobre o impacto ambiental e econômico de seu consumo energético.
    3. **Ferramentas Interativas:** Desenvolver e disponibilizar ferramentas interativas para monitoramento e análise do consumo energético.
    """, unsafe_allow_html=True)

    # Importância da eficiência energética
    st.markdown("""
    ## Por Que a Eficiência Energética?
    A eficiência energética é fundamental não apenas para reduzir custos, mas também para combater as mudanças climáticas. 
    Melhorar a eficiência energética das residências pode significativamente diminuir a quantidade de energia necessária 
    para aquecimento, resfriamento e outras necessidades domésticas, contribuindo assim para um planeta mais sustentável.
    """, unsafe_allow_html=True)

    # Visualização de nuvem de palavras
    st.subheader("Foco em Palavras-Chave de Energia")
    plot_word_cloud()  # Supõe-se que a função plot_word_cloud() cria e exibe uma nuvem de palavras.

    st.info("Explore as outras seções para visualizações interativas e mais informações sobre eficiência energética.")

@st.cache_data  # Cache para a nuvem de palavras
def plot_word_cloud():
    text = "energia renovável sustentabilidade eficiência energética solar eólica hidrelétrica biomassa conservação energia gestão energia redução emissões energia limpa fotovoltaica turbinas eólicas painéis solares energia térmica células combustível geotérmica energia do oceano reciclagem energia inovação energética"
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text)
    plt.figure(figsize=(8, 4))
    fig, ax = plt.subplots(figsize=(8, 4))  # Cria um objeto de figura e um de eixo
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")  # Remove os eixos
    st.pyplot(fig)  # Exibe a figura


def data_analysis():
    st.title("Análise de Dados")
    df = load_cleaned_data()
    df = clean_data(df)
    if st.button("Exibir Matriz de Correlação"):
        plot_correlation_matrix(df, st)
    if st.button("Distribuição da Eficiência por Região"):
        plot_efficiency_distribution(df, st)
    if st.button("Eficiência por Região"):
        plot_region_efficiency(df, st)
    if st.button("Evolução da Energia e Lucro por Mês"):
        plot_monthly_evolution(df, st)

def upload_download():
    st.title("Upload e Download de Dados")
    st.subheader("Download de Dados Processados")

    df = load_cleaned_data()  # Carregar dados processados
    df = clean_data(df)  # Limpar dados

    # Converter DataFrame para CSV para download
    @st.cache_data
    def convert_df_to_csv(df):
        return df.to_csv(index=False).encode('utf-8')
    
    csv = convert_df_to_csv(df)  # Obter a versão CSV dos dados

    st.download_button(
        label="Baixar Dados Limpos",
        data=csv,
        file_name="dados_limpos.csv",
        mime="text/csv",
        help="Clique aqui para baixar os dados limpos em formato CSV."
    )

    st.info("Clique no botão acima para baixar os dados limpos processados em formato CSV.")

    

def settings():
    st.title("Configurações")
    st.write("Ajustes e configurações da aplicação.")

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
