from sqlalchemy import inspect
from typing import List
from schemas import TableMetadata, ColumnInfo, ForeignKeyInfo

NUM_TYPES = ["NUMERIC", "INT", "FLOAT", "DOUBLE", "DECIMAL", "REAL"]
TEMP_TYPES = ["DATE", "TIME", "TIMESTAMP"]
LEX_TYPES = ["VARCHAR", "TEXT", "CHAR", "BPCHAR", "UUID"]

def get_semantic_type(db_type_str: str) -> str:
    db_type_str = db_type_str.upper()
    if any(t in db_type_str for t in NUM_TYPES):
        return "scalar"
    if any(t in db_type_str for t in TEMP_TYPES):
        return "temporal"
    if any(t in db_type_str for t in LEX_TYPES):
        return "lexical"
    return "unknown"

def extract_database_metadata(engine) -> List[TableMetadata]:
    inspector = inspect(engine)
    
    tables_metadata = []
    
    # Get all table names in the "public" schema
    table_names = inspector.get_table_names(schema="public")
    
    for table_name in table_names:
        # Get primary keys for this table
        pk_constraint = inspector.get_pk_constraint(table_name, schema="public")
        primary_keys = pk_constraint.get("constrained_columns", [])
        
        # Get foreign keys for this table
        fks = inspector.get_foreign_keys(table_name, schema="public")
        foreign_keys_info = []
        fk_column_names = []
        
        for fk in fks:
            # ForeignKeys have multiple columns
            for child_col, parent_col in zip(fk['constrained_columns'], fk['referred_columns']):
                foreign_keys_info.append(
                    ForeignKeyInfo(
                        parent_table=fk['referred_table'],
                        parent_column=parent_col,
                        child_table=table_name,
                        child_column=child_col
                    )
                )
                fk_column_names.append(child_col)
                
        # Get all columns for this table
        columns = inspector.get_columns(table_name, schema="public")
        columns_info = []
        
        for col in columns:
            # Get column name and type
            col_name = col['name']
            col_type = str(col['type']) 
            
            columns_info.append(
                ColumnInfo(
                    name=col_name,
                    type=col_type,
                    is_primary_key=(col_name in primary_keys),
                    is_foreign_key=(col_name in fk_column_names),
                    semantic_type=get_semantic_type(col_type)
                )
            )

        tables_metadata.append(
            TableMetadata(
                table_name=table_name,
                columns=columns_info,
                primary_keys=primary_keys,
                foreign_keys=foreign_keys_info
            )
        )
        
    return tables_metadata