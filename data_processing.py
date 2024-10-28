import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import streamlit as st

# Carregar o dataset limpo
def load_cleaned_data(filepath="D:/Pastas/Infnet/Infnet - 2024.2/Projeto de bloco/TP1/cleaned_energy_data.csv"):
    return pd.read_csv(filepath)

# Remover outliers de uma coluna específica
def remove_outliers_iqr(df, column):
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    df_filtered = df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]
    return df_filtered

# Remover outliers de várias colunas
def clean_data(df):
    df = remove_outliers_iqr(df, 'energy')
    df = remove_outliers_iqr(df, 'capacity')
    df = remove_outliers_iqr(df, 'total_profit')
    
    # Calcular eficiência energética
    df['efficiency'] = df['total_profit'] / df['energy']
    return df

# Gerar matriz de correlação
def plot_correlation_matrix(df, st):
    df_numerical = df.select_dtypes(include=['float64', 'int64'])
    corr = df_numerical.corr()

    plt.figure(figsize=(10, 8))
    sns.heatmap(corr, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
    plt.title('Matriz de Correlação das Variáveis Numéricas')
    st.pyplot(plt)

# Plotar distribuição da eficiência por região
def plot_efficiency_distribution(df, st):
    median_efficiency = df['efficiency'].median()

    plt.figure(figsize=(10, 6))
    sns.boxplot(x='region', y='efficiency', data=df, palette="Set2")
    plt.yscale('log')
    sns.stripplot(x='region', y='efficiency', data=df, color='black', alpha=0.5)
    plt.axhline(median_efficiency, color='red', linestyle='--', label=f'Mediana Geral: {median_efficiency:.2f}')
    plt.title('Distribuição da Eficiência por Região (após limpeza)')
    plt.xlabel('Região')
    plt.ylabel('Eficiência (Lucro por kWh)')
    plt.xticks(rotation=45)
    plt.legend()
    st.pyplot(plt)

# Plotar média de eficiência por região
def plot_region_efficiency(df, st):
    df_region_efficiency = df.groupby('region')['efficiency'].mean().reset_index()
    df_region_efficiency = df_region_efficiency.sort_values(by='efficiency', ascending=False)

    plt.figure(figsize=(12, 6))
    palette = sns.color_palette("Blues_d", len(df_region_efficiency))
    sns.barplot(x='region', y='efficiency', data=df_region_efficiency, palette=palette)

    for index, value in enumerate(df_region_efficiency['efficiency']):
        plt.text(index, value + 0.01, f'{value:.2f}', ha='center', va='bottom')

    plt.title('Média de Eficiência Energética por Região (Lucro por kWh)', fontsize=16, fontweight='bold')
    plt.xlabel('Região', fontsize=12)
    plt.ylabel('Eficiência (Lucro por kWh)', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    st.pyplot(plt)

# Plotar evolução da energia e lucro ao longo do ano
def plot_monthly_evolution(df, st):
    df_monthly = df.groupby('month')[['energy', 'total_profit']].mean().reset_index()

    plt.figure(figsize=(12, 6))
    sns.lineplot(x='month', y='energy', data=df_monthly, marker='o', label='Energy', color='blue', linewidth=2.5)
    sns.lineplot(x='month', y='total_profit', data=df_monthly, marker='s', label='Total Profit', color='green', linewidth=2.5)

    max_energy = df_monthly['energy'].max()
    min_energy = df_monthly['energy'].min()
    max_profit = df_monthly['total_profit'].max()
    min_profit = df_monthly['total_profit'].min()

    plt.text(df_monthly['month'][df_monthly['energy'].idxmax()], max_energy, f'Máx: {max_energy:.2f}', 
             horizontalalignment='left', color='blue', fontsize=12)
    plt.text(df_monthly['month'][df_monthly['energy'].idxmin()], min_energy, f'Mín: {min_energy:.2f}', 
             horizontalalignment='left', color='blue', fontsize=12)

    plt.text(df_monthly['month'][df_monthly['total_profit'].idxmax()], max_profit, f'Máx: {max_profit:.2f}', 
             horizontalalignment='left', color='green', fontsize=12)
    plt.text(df_monthly['month'][df_monthly['total_profit'].idxmin()], min_profit, f'Mín: {min_profit:.2f}', 
             horizontalalignment='left', color='green', fontsize=12)

    plt.title('Evolução da Energia e Lucro ao Longo de 2030 (após limpeza)', fontsize=16, fontweight='bold')
    plt.xlabel('Mês', fontsize=14)
    plt.ylabel('Valor Médio', fontsize=14)
    plt.legend(title='Métricas', title_fontsize='13', fontsize='12', loc='upper left', bbox_to_anchor=(1, 1))
    plt.tight_layout()
    st.pyplot(plt)


# Descrição final do dataset
def describe_data(df):
    print(df.describe())
