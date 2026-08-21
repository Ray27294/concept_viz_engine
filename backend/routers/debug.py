from fastapi import APIRouter
from database import db_manager
from services.metadata_service import extract_database_metadata
from services.inference_service import (
    is_basic_entity, 
    is_weak_entity, 
    is_one_many_relationship, 
    is_many_many_relationship, 
    is_reflexive
)

router = APIRouter(prefix="/debug", tags=["Debug Endpoints"])

@router.get("/test-all-patterns")
def test_all_database_patterns():
    all_tables = extract_database_metadata(db_manager.get_engine())
    report = []

    for table in all_tables:
        all_col_names = [col.name for col in table.columns]
        
        pattern_result = "Unknown"
        
        if is_many_many_relationship(table, all_col_names):
            if is_reflexive(table):
                pattern_result = "Reflexive Many-to-Many"
            else:
                pattern_result = "Many-to-Many"
        elif is_weak_entity(table, all_col_names):
            pattern_result = "Weak Entity"
        elif is_one_many_relationship(table, all_col_names):
            pattern_result = "One-to-Many"
        elif is_basic_entity(table, all_col_names):
            pattern_result = "Basic Entity"

        report.append({
            "table_name": table.table_name,
            "inferred_pattern": pattern_result,
            "columns_count": len(all_col_names),
            "foreign_keys_count": len(table.foreign_keys)
        })

    return {
        "total_tables_scanned": len(all_tables), 
        "results": report
    }