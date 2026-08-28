from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
import duckdb
import math
import os

app = FastAPI(title="ICRM-HiTek Gateway", version="1.0")

# DuckDB with httpfs
con = duckdb.connect()
con.execute("INSTALL httpfs")
con.execute("LOAD httpfs")

# Base URL of the dataset on Hugging Face
BASE_URL = "https://huggingface.co/datasets/Kzr0xx/icrm-hitek-full-db-mixed/resolve/main"

# List of phone index shards (0..6)
PHONE_SHARDS = [f"{BASE_URL}/idx_phone.{i}.parquet" for i in range(7)]
AADHAR_SHARDS = [f"{BASE_URL}/idx_aadhar.{i}.parquet" for i in range(7)]

# The raw data (for full‑text search fallback)
RAW_URL = "https://huggingface.co/datasets/Kzr0xx/Icmr-and-hitek/resolve/main/data.parquet"

# Helper: clean NaN/Inf for JSON
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
        "message": "ICRM-HiTek Data Gateway",
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
    Look up a phone number using the pre‑sorted phone index.
    Returns all matching records.
    """
    try:
        # Read all phone shards (glob) and filter
        # We need to pass a list of filenames to read_parquet
        query = f"""
            SELECT * FROM read_parquet({PHONE_SHARDS}) 
            WHERE phoneNumber = '{Number}'
        """
        # DuckDB can accept a list of strings as the first argument to read_parquet
        # But we need to format it properly: we'll build a list of filenames in the query.
        # However, DuckDB's read_parquet does not accept a list directly in SQL string.
        # We'll use the `read_parquet` with `union` or use the glob pattern:
        # Using glob: 'https://.../idx_phone.*.parquet' works.
        # Let's use glob for simplicity:
        glob_url = f"{BASE_URL}/idx_phone.*.parquet"
        query = f"""
            SELECT * FROM read_parquet('{glob_url}') 
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
    Look up an Aadhar number using the pre‑sorted Aadhar index.
    """
    try:
        glob_url = f"{BASE_URL}/idx_aadhar.*.parquet"
        query = f"""
            SELECT * FROM read_parquet('{glob_url}') 
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
    Use the 'field' parameter to specify which column to match.
    """
    try:
        # We search the raw data (not indexed) – this is slower
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
