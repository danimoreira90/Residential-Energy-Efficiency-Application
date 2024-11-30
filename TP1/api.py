from fastapi import FastAPI
import pandas as pd

app = FastAPI()

def load_excel_data():
    file_path = 'D:\\Pastas\\Infnet\\Infnet - 2024.2\\Projeto de bloco\\TP1\\Dados_abertos_Consumo_Mensal.xlsx'
    sheets_dict = pd.read_excel(file_path, sheet_name=None)  # Carrega todas as abas
    return sheets_dict

@app.get("/data/{sheet_name}")
async def get_data(sheet_name: str):
    data = load_excel_data()
    if sheet_name in data:
        return {"data": data[sheet_name].to_dict(orient='records')}
    return {"error": "Sheet not found"}

@app.get("/sheets")
async def get_sheets():
    data = load_excel_data()
    return {"sheets": list(data.keys())}
