# pages/calculadora.py
import streamlit as st
import pandas as pd


@st.cache_data  
def load_data():
    path = 'D:\\Pastas\\Infnet\\Infnet - 2024.2\\Projeto de bloco\\Dados\\calculadora.json'
    return pd.read_json(path)

# Função que encapsula toda a lógica da calculadora
def calculadora():
    data = load_data()

    # Dropdown para selecionar a distribuidora
    option = st.selectbox('Escolha a Distribuidora', data['sigDistribuidora'].unique())

    # Inputs do usuário
    power_electric = st.number_input('Potência Elétrica (Watts)', value=1000)
    amount_devices = st.number_input('Quantidade de Dispositivos', value=1)
    use_duration = st.number_input('Duração de Uso (Horas)', value=1)
    period = st.number_input('Período (Dias)', value=30)
    device_name = st.text_input('Nome do Dispositivo', value='Dispositivo X')

    # Obter a tarifa selecionada
    def get_tariff(distributor_name):
        dist_data = data[data['sigDistribuidora'] == distributor_name].iloc[0]
        return dist_data['vlrTotaTRFConvencional']

    # Botão para realizar cálculo
    if st.button('Calcular Consumo'):
        tariff = get_tariff(option)
        power_electric_kW = power_electric / 1000  # Convertendo para kW
        electrical_consumption = amount_devices * power_electric_kW * use_duration * period
        cost = electrical_consumption * tariff
        cost_formatted = f'R$ {cost:.2f}'
        
        st.write(f'Custo estimado para {device_name}: {cost_formatted}')

    # Usando session_state para armazenar e exibir múltiplos resultados
    if 'results' not in st.session_state:
        st.session_state['results'] = []

    if st.button('Adicionar Resultado'):
        st.session_state['results'].append({
            'device_name': device_name,
            'amount_devices': amount_devices,
            'use_duration': f'{use_duration} Horas',
            'electrical_consumption': f'{electrical_consumption:.2f} kW',
            'period': f'{period} Dias',
            'power_supply': option,
            'cost': cost_formatted
        })

    # Exibir resultados
    if st.session_state['results']:
        df_results = pd.DataFrame(st.session_state['results'])
        st.write(df_results)
