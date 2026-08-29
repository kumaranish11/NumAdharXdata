from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import duckdb
import math
import os

app = FastAPI(title="NumAdharXdata Gateway", version="1.0")

# --- Corrected Connection Logic ---
con = duckdb.connect()
con.execute("INSTALL httpfs")
con.execute("LOAD httpfs")

HF_TOKEN = os.environ.get("HF_TOKEN")
if HF_TOKEN:
    # Create a secret for Hugging Face authentication
    con.execute(f"CREATE SECRET hf_token (TYPE HUGGINGFACE, TOKEN '{HF_TOKEN}')")
    print("Hugging Face secret created successfully.")
else:
    print("WARNING: HF_TOKEN environment variable not set.")

# ✅ Use the hf:// protocol with the correct bucket path
BASE_URL = "hf://buckets/Guptarajan845459/icrm-hitek-full-db-mixed-bucket"
# --- End of Corrected Connection Logic ---

# Helper: clean NaN/Inf for JSON compliance
def clean_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    return obj

# ---------- ENDPOINTS ----------
@app.get("/", response_class=JSONResponse)
def root():
    return {
        "status": "online",
        "message": "NumAdharXdata Gateway (Storage Bucket - hf://)",
        "endpoints": [
            "/FetchData?Number=phone",
            "/FetchAadhar?Aadhar=aadhar"
        ],
        "Developer": "@Aswatthama_0x"
    }

@app.get("/FetchData")
def fetch_by_phone(Number: str = Query(..., min_length=10, max_length=15, regex=r"^\d+$")):
    try:
        shards = [f"{BASE_URL}/idx_phone.{i}.parquet" for i in range(7)]
        shards_str = ', '.join([f"'{url}'" for url in shards])
        query = f"""
            SELECT * FROM read_parquet([{shards_str}]) 
            WHERE phoneNumber = '{Number}'
        """
        result = con.execute(query)
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description]
        data = [dict(zip(columns, row)) for row in rows]

        if not data:
            return JSONResponse(status_code=404, content={"status": "not_found", "phone": Number})

        return {
            "status": "success",
            "count": len(data),
            "data": clean_nan(data)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/FetchAadhar")
def fetch_by_aadhar(Aadhar: str = Query(..., min_length=12, max_length=12, regex=r"^\d+$")):
    try:
        shards = [f"{BASE_URL}/idx_aadhar.{i}.parquet" for i in range(7)]
        shards_str = ', '.join([f"'{url}'" for url in shards])
        query = f"""
            SELECT * FROM read_parquet([{shards_str}]) 
            WHERE aadharNumber = '{Aadhar}'
        """
        result = con.execute(query)
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description]
        data = [dict(zip(columns, row)) for row in rows]

        if not data:
            return JSONResponse(status_code=404, content={"status": "not_found", "aadhar": Aadhar})

        return {
            "status": "success",
            "count": len(data),
            "data": clean_nan(data)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
