import streamlit as st


# Importações dos módulos para cada página
from data_processing import (
    load_cleaned_data, clean_data, plot_correlation_matrix, plot_efficiency_distribution,
    plot_region_efficiency, plot_monthly_evolution, describe_data
)


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