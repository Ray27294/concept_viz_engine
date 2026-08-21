from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None

    def connect(self, db_url: str):
        self.engine = create_engine(db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        with self.engine.connect() as conn:
            pass 

    def get_engine(self):
        if self.engine is None:
            raise Exception("Database is not connected yet. Please connect first.")
        return self.engine

db_manager = DatabaseManager()

Base = declarative_base()