from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import SessionLocal, engine
from schemas import TableMetadata
from typing import List
from services import metadata_service
from routers import debug

app = FastAPI(title="Concept Viz Engine API")

app.include_router(debug.router)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Concept Viz Engine API!"}

@app.get("/test-db")
def test_database_connection(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT current_database();")).scalar()
        return {
            "status": "success",
            "message": "Successfully connected to the database.",
            "connected_to": result
        }
    except Exception as e:
        return {
            "status": "failed",
            "message": "Failed to connect to the database.",
            "error": str(e)
        }

@app.get("/metadata", response_model=List[TableMetadata])
def fetch_database_metadata():
    return metadata_service.extract_database_metadata(engine)