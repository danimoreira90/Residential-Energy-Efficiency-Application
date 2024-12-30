import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt


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

def plot_consumo_sam_plt(data):
    # Verifique se as colunas necessárias estão presentes
    if not {'Sistema', 'Classe', 'Consumo'}.issubset(data.columns):
        print("As colunas necessárias não estão presentes no DataFrame.")
        # Mostrar as colunas atuais para debug
        print("Colunas disponíveis:", data.columns)
        return

    # Agrupar os dados
    grouped_data = data.groupby(['Sistema', 'Classe'])[
        'Consumo'].sum().unstack()
    st.write("## Consumo por Setor Industrial e Região")

    # Criar o gráfico de área
    fig, ax = plt.subplots(figsize=(12, 6))
    grouped_data.plot(kind='area', alpha=0.7, ax=ax)
    ax.set_title("Consumo por Setor Industrial e Região", fontsize=16)
    ax.set_xlabel("Setor Industrial", fontsize=14)
    ax.set_ylabel("Consumo", fontsize=14)
    ax.legend(title="Região", fontsize=10)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()

    # Exibir o gráfico no Streamlit
    st.pyplot(fig)


def plot_consumo_sam_uf_plt(data):
    st.write("## Consumo e Número de Consumidores por UF")

    # Agrupar os dados
    grouped_data = data.groupby('UF')['Consumo'].sum()

    # Criar o gráfico de linha
    fig, ax = plt.subplots(figsize=(12, 6))
    grouped_data.plot(kind='line', marker='o', ax=ax)

    # Configurar o gráfico
    ax.set_title("Consumo e Número de Consumidores por UF", fontsize=16)
    ax.set_xlabel("UF", fontsize=14)
    ax.set_ylabel("Consumo", fontsize=14)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()

    # Mostrar o gráfico no Streamlit
    st.pyplot(fig)


def plot_setor_industrial_plt(data):
    st.write("## Consumo por Setor Industrial e Região")

    # Agrupar os dados
    grouped_data = data.groupby(['SetorIndustrial', 'Regiao'])[
        'Consumo'].sum().unstack()

    # Criar o gráfico de área
    fig, ax = plt.subplots(figsize=(12, 6))
    grouped_data.plot(kind='area', alpha=0.7, ax=ax)

    # Configurar o gráfico
    ax.set_title("Consumo por Setor Industrial e Região", fontsize=16)
    ax.set_xlabel("Setor Industrial", fontsize=14)
    ax.set_ylabel("Consumo", fontsize=14)
    ax.legend(title="Região", fontsize=10)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()

    # Mostrar o gráfico no Streamlit
    st.pyplot(fig)


def plot_consumo_ben_rg_plt(data):
    st.write("## Consumo por Região e Classe (1970-1989)")

    # Agrupar os dados
    grouped_data = data.groupby(['Regiao', 'Classe'])[
        'Consumo'].sum().unstack()

    # Criar o gráfico de linha
    fig, ax = plt.subplots(figsize=(12, 6))
    grouped_data.plot(kind='line', marker='o', ax=ax)

    # Configurar o gráfico
    ax.set_title("Consumo por Região e Classe (1970-1989)", fontsize=16)
    ax.set_xlabel("Região", fontsize=14)
    ax.set_ylabel("Consumo", fontsize=14)
    ax.legend(title="Classe", fontsize=10)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()

    # Mostrar o gráfico no Streamlit
    st.pyplot(fig)


def plot_consumo_eletrobras_plt(data):
    st.write("## Consumo Eletrobras por Região e Classe (1990-2003)")

    # Agrupar os dados
    grouped_data = data.groupby(['Regiao', 'Classe'])[
        'Consumo'].sum().unstack()

    # Criar o gráfico de linha
    fig, ax = plt.subplots(figsize=(12, 6))
    grouped_data.plot(kind='line', marker='o', ax=ax)

    # Configurar o gráfico
    ax.set_title(
        "Consumo Eletrobras por Região e Classe (1990-2003)", fontsize=16)
    ax.set_xlabel("Região", fontsize=14)
    ax.set_ylabel("Consumo", fontsize=14)
    ax.legend(title="Classe", fontsize=10)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()

    # Mostrar o gráfico no Streamlit
    st.pyplot(fig)


# plot_consumo_sam_plt(consumo_sam)
# plot_consumo_sam_uf_plt(consumo_sam_uf)
# plot_setor_industrial_plt(setor_industrial)
# plot_consumo_ben_rg_plt(consumo_ben_rg)
# plot_consumo_eletrobras_plt(consumo_eletrobras)



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
        plot_consumo_sam_plt(consumo_sam)
    elif option == 'CONSUMO E NUMCONS SAM UF':
        plot_consumo_sam_uf_plt(consumo_sam_uf)
    elif option == 'SETOR INDUSTRIAL POR RG':
        plot_setor_industrial_plt(setor_industrial)
    elif option == 'CONSUMO_BEN_RG_1970-1989':
        plot_consumo_ben_rg_plt(consumo_ben_rg)
    elif option == 'CONSUMO_ELETROBRAS_1990-2003':
        plot_consumo_eletrobras_plt(consumo_eletrobras)

