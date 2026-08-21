from fastapi import APIRouter, HTTPException
from database import db_manager
from schemas import RecommendRequest, RecommendationResponse
from services.metadata_service import extract_database_metadata
from services.recommend_service import recommend_components
from services.inference_service import (
    is_basic_entity, 
    is_weak_entity, 
    is_one_many_relationship, 
    is_many_many_relationship, 
    is_reflexive,
    is_complete_weak,
    _get_pk_names,
    _get_fk_names
)

router = APIRouter(prefix="/recommend", tags=["Recommendation Engine"])

@router.post("/", response_model=RecommendationResponse)
def get_recommendations(request: RecommendRequest):
    all_metadata = extract_database_metadata(db_manager.get_engine())
    
    target_table = next((t for t in all_metadata if t.table_name == request.table_name), None)
    
    if not target_table:
        raise HTTPException(status_code=404, detail=f"Table not found: {request.table_name}")

    pattern = "Unknown"
    is_complete = False
    cols = request.selected_columns

    if is_many_many_relationship(target_table, cols):
        pattern = "Reflexive Many-to-Many" if is_reflexive(target_table) else "Many-to-Many"
        
    elif is_weak_entity(target_table, cols):
        pattern = "Weak Entity"
        pk_names = list(_get_pk_names(target_table))
        fk_names = list(_get_fk_names(target_table))
        is_complete = is_complete_weak(db_manager.get_engine(), pk_names, fk_names, request.table_name)
        
    elif is_one_many_relationship(target_table, cols):
        pattern = "One-to-Many"
        
    elif is_basic_entity(target_table, cols):
        pattern = "Basic Entity"

    recommendation = recommend_components(
        table=target_table,
        selected_col_names=cols,
        pattern=pattern,
        is_complete=is_complete
    )

    return recommendation