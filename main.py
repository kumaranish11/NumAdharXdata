from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
import duckdb
import math
import os

app = FastAPI(title="NumAdharXdata Gateway", version="1.0")

# DuckDB with httpfs
con = duckdb.connect()
con.execute("INSTALL httpfs")
con.execute("LOAD httpfs")

# Set Hugging Face token from environment variable
# MUST be set on Render: HF_TOKEN=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
HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    print("WARNING: HF_TOKEN environment variable not set. Private datasets will fail.")

# Use hf:// protocol for authenticated access
# Base path for the private dataset
DATASET_PATH = "hf://datasets/Kzr0xx/icrm-hitek-full-db-mixed"

# The raw data (if needed) - this might also be private, but we'll define it
RAW_URL = f"{DATASET_PATH}/data.parquet"

# Helper: clean NaN/Inf for JSON compliance
def clean_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    return obj

# ---------- PUBLIC ENDPOINTS ----------
@app.get("/", response_class=JSONResponse)
def root():
    return {
        "status": "online",
        "message": "NumAdharXdata Gateway (Private Dataset)",
        "endpoints": [
            "/FetchData?Number=phone",
            "/FetchAadhar?Aadhar=aadhar",
            "/Search?q=text&field=column&limit=10"
        ],
        "Developer": "@Aswatthama_0x"
    }

@app.get("/FetchData")
def fetch_by_phone(Number: str = Query(..., min_length=10, max_length=15, regex=r"^\d+$")):
    """
    Look up a phone number using the pre‑sorted phone index (private dataset).
    """
    try:
        # List all 7 phone index shards explicitly
        shards = [f"{DATASET_PATH}/idx_phone.{i}.parquet" for i in range(7)]
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
    """
    Look up an Aadhar number using the pre‑sorted Aadhar index (private dataset).
    """
    try:
        # List all 7 Aadhar index shards explicitly
        shards = [f"{DATASET_PATH}/idx_aadhar.{i}.parquet" for i in range(7)]
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

@app.get("/Search")
def search(
    q: str = Query(..., description="Search term"),
    field: str = Query("name", description="Column to search (e.g., name, district, state)"),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Generic text search across the raw data (slower, but flexible).
    This uses the raw Parquet file (may be large and also private).
    """
    try:
        # Search the raw data file (if it exists in the dataset)
        query = f"""
            SELECT * FROM read_parquet('{RAW_URL}') 
            WHERE LOWER(CAST({field} AS VARCHAR)) LIKE LOWER('%{q}%')
            LIMIT {limit}
        """
        result = con.execute(query)
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description]
        data = [dict(zip(columns, row)) for row in rows]

        return {
            "status": "success",
            "count": len(data),
            "data": clean_nan(data)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
