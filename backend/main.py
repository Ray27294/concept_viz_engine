from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from schemas import TableMetadata
from typing import List
from services import metadata_service
from database import db_manager
from routers import debug, recommend, data, plot
from fastapi.middleware.cors import CORSMiddleware
import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend for matplotlib

app = FastAPI(title="Concept Viz Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

class DBConnectRequest(BaseModel):
    host: str
    port: str = "5432"
    database: str
    username: str
    password: str

app.include_router(debug.router)
app.include_router(recommend.router)
app.include_router(data.router)
app.include_router(plot.router)

def get_db():
    if db_manager.SessionLocal is None:
        raise HTTPException(status_code=500, detail="Database is not connected. Please connect first.")
    
    db = db_manager.SessionLocal()
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
    try:
        engine = db_manager.get_engine()
        return metadata_service.extract_database_metadata(engine)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/connect")
def connect_database(req: DBConnectRequest):
    db_url = f"postgresql://{req.username}:{req.password}@{req.host}:{req.port}/{req.database}"
    try:
        db_manager.connect(db_url)
        return {"status": "success", "message": f"Successfully connected to {req.database} at {req.host}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to database: {str(e)}")