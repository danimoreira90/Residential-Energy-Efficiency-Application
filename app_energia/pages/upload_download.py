import streamlit as st
from data_processing import (
    load_cleaned_data, clean_data)

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