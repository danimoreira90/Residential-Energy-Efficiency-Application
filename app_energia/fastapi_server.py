from fastapi import FastAPI, HTTPException
from typing import Optional
import httpx

app = FastAPI()

async def fetch_data_from_aneel(resource_id: str, limit: int, query: Optional[str] = None):
    base_url = "https://dadosabertos.aneel.gov.br/pt_BR/api/3/action/datastore_search"
    params = {
        "resource_id": resource_id,
        "limit": limit,
    }
    if query:
        params["q"] = query

    async with httpx.AsyncClient() as client:
        response = await client.get(base_url, params=params)
        if response.status_code == 200:
            return response.json()['result']['records']
        else:
            raise Exception("Failed to fetch data from ANEEL API")

@app.get("/fetch_data/")
async def fetch_data(resource_id: str, limit: int = 5, query: Optional[str] = None):
    try:
        data = await fetch_data_from_aneel(resource_id, limit, query)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
