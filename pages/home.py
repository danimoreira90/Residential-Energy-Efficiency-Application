import streamlit as st
from wordcloud import WordCloud
import matplotlib.pyplot as plt

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