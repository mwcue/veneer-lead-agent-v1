# main.py  ─ FastAPI entrypoint for Cloud Run
import os
import uuid
import io
import csv
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from agent_runner import run_lead_generation_process

# ──────────────────────────────────────────────────────────────
# FastAPI setup
# ──────────────────────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # adjust later if you like
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# shared API key (set via Cloud Run env-var)
API_KEY = os.getenv("MY_SHARED_API_KEY", "")

# simple in-memory cache:  job_id  →  io.BytesIO()
results_cache: dict[str, io.BytesIO] = {}

# ──────────────────────────────────────────────────────────────
# Request / response pydantic model
# ──────────────────────────────────────────────────────────────
class SegmentRequest(BaseModel):
    segments: list[str]

# ──────────────────────────────────────────────────────────────
# POST  /run-generator
# ──────────────────────────────────────────────────────────────
@app.post("/run-generator")
async def run_generator(req: Request, seg_req: SegmentRequest):
    # API-key check
    api_key = req.headers.get("x-api-key")
    if api_key != API_KEY:
        logger.warning("Unauthorized request – bad API key.")
        raise HTTPException(status_code=403, detail="Unauthorized")

    job_id = str(uuid.uuid4())
    logger.info(f"→ Starting agent pipeline…  Segments: {seg_req.segments}")

    try:
        results = run_lead_generation_process(seg_req.segments)
        logger.info("→ Agent pipeline finished – serializing CSV.")

        # If the pipeline returned an error-dict, surface it to caller
        if not isinstance(results, list):
            return JSONResponse(results, status_code=500)

        # build CSV in-memory
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=["name", "website"])
        writer.writeheader()

        for row in results:
            if isinstance(row, dict) and {"name", "website"} <= row.keys():
                writer.writerow({"name": row["name"], "website": row["website"]})
            elif isinstance(row, str):
                writer.writerow({"name": row.strip(), "website": ""})
            # else skip any unusable row

        # nothing extracted?  inform caller
        if csv_buf.tell() == len("name,website\r\n"):
            logger.warning("Lead list is empty – returning 204.")
            return JSONResponse({"message": "No leads found."}, status_code=204)

        # cache for later download
        results_cache[job_id] = io.BytesIO(csv_buf.getvalue().encode("utf-8"))
        logger.info(f"Cached CSV under job_id {job_id}")

        return JSONResponse({"job_id": job_id})

    except Exception as e:
        logger.exception("Unhandled exception during generation")
        raise HTTPException(status_code=500, detail=str(e))

# ──────────────────────────────────────────────────────────────
# GET   /results/{job_id}
# ──────────────────────────────────────────────────────────────
@app.get("/results/{job_id}")
async def get_result(job_id: str):
    buf = results_cache.get(job_id)
    if buf is None:
        raise HTTPException(status_code=404, detail="Result not found or expired")

    buf.seek(0)
    headers = {
        "Content-Disposition": f'attachment; filename="leads.csv"'
    }
    return StreamingResponse(buf, media_type="text/csv", headers=headers)
