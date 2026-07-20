from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from database import engine
from schemas import DataPreviewRequest, DataPreviewResponse

router = APIRouter(prefix="/data", tags=["Data Preview"])

@router.post("/preview", response_model=DataPreviewResponse)
def get_data_preview(request: DataPreviewRequest):
    if not request.selected_columns:
        return DataPreviewResponse(columns=[], rows=[])

    safe_cols = ", ".join([f'"{c}"' for c in request.selected_columns])
    safe_table = f'"{request.table_name}"'

    query = text(f"SELECT {safe_cols} FROM public.{safe_table} LIMIT :limit")

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"limit": request.limit})
            rows = [dict(row._mapping) for row in result]
            return DataPreviewResponse(columns=request.selected_columns, rows=rows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))