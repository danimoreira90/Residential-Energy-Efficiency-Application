import streamlit as st
import requests
import pandas as pd

def aneel_data_page():
    st.title('Consulta de Dados à API da ANEEL')

    resource_id = st.text_input('Resource ID:', value='3710b245-88f0-4aa6-8cfb-8b1426e9021d')
    query = st.text_input('Digite a consulta:', value='')
    limit = st.number_input('Limite de resultados', min_value=1, max_value=100, value=5)
    
    if st.button('Buscar Dados'):
        data = fetch_data_from_api(resource_id, limit, query)
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df)
        else:
            st.error('Nenhum dado para mostrar')

def fetch_data_from_api(resource_id, limit, query):
    url = f"http://localhost:8000/fetch_data/?resource_id={resource_id}&limit={limit}&query={query}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()['data']
    else:
        st.error("Falha ao buscar dados")
        return None
