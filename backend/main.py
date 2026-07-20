from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import SessionLocal, engine
from schemas import TableMetadata
from typing import List
from services import metadata_service
from routers import debug, recommend, data
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Concept Viz Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(debug.router)
app.include_router(recommend.router)
app.include_router(data.router)

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