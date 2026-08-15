from sqlalchemy import inspect, text
from typing import List
from schemas import TableMetadata, Column, TableColumnGroup, Key, ForeignKey

NUM_TYPES = ["NUMERIC", "INT", "FLOAT", "DOUBLE", "DECIMAL", "REAL"]
TEMP_TYPES = ["DATE", "TIME", "TIMESTAMP"]
LEX_TYPES = ["VARCHAR", "TEXT", "CHAR", "BPCHAR", "UUID"]

DISCRETE_THRESHOLD = 15

def get_semantic_type(db_type_str: str) -> str:
    db_type_str = db_type_str.upper()
    if any(t in db_type_str for t in NUM_TYPES):
        return "scalar"
    if any(t in db_type_str for t in TEMP_TYPES):
        return "temporal"
    if any(t in db_type_str for t in LEX_TYPES):
        return "discrete"
    return "unknown"

def extract_database_metadata(engine) -> List[TableMetadata]:
    inspector = inspect(engine)
    
    tables_metadata = []
    
    # Get all table names in the "public" schema
    table_names = inspector.get_table_names(schema="public")

    all_columns_cache = {}
    with engine.connect() as conn:
        for t_name in table_names:
            cols = inspector.get_columns(t_name, schema="public")
            col_objs = []
            
            for c in cols:
                col_name = c['name']
                db_type = str(c['type'])
                semantic_type = get_semantic_type(db_type)
                
                if semantic_type == "scalar":
                    try:
                        query = text(f'SELECT COUNT(DISTINCT "{col_name}") FROM public."{t_name}"')
                        distinct_count = conn.execute(query).scalar()
                        
                        if distinct_count is not None and 0 < distinct_count <= DISCRETE_THRESHOLD:
                            semantic_type = "discrete"
                            
                    except Exception as e:
                        print(f"failed to inspect {t_name}.{col_name}, downgrading to scalar: {e}")
                        pass

                col_objs.append(Column(
                    name=col_name,
                    type=db_type,
                    semantic_type=semantic_type
                ))
            
            all_columns_cache[t_name] = col_objs

    # Helper function to get Column objects for a given table and list of column names    
    def get_column_objs(t_name: str, col_names: List[str]) -> List[Column]:
        if t_name not in all_columns_cache:
            return []
        return [col for col in all_columns_cache[t_name] if col.name in col_names]
    
    tables_metadata = []

    for t_name in table_names:
        # Get the primary key for this table
        pk_constraint = inspector.get_pk_constraint(t_name, schema="public")
        pk_col_names = pk_constraint.get("constrained_columns", [])
        
        primary_key = None
        if pk_col_names:
            primary_key = Key(
                table_name=t_name,
                columns=get_column_objs(t_name, pk_col_names)
            )

        # Get foreign keys for this table
        fks = inspector.get_foreign_keys(t_name, schema="public")
        foreign_keys = []
        
        for fk in fks:
            # (TableColumnGroup)
            referencing_group = TableColumnGroup(
                table_name=t_name,
                columns=get_column_objs(t_name, fk['constrained_columns'])
            )
            
            # (Key)
            referenced_key = Key(
                table_name=fk['referred_table'],
                columns=get_column_objs(fk['referred_table'], fk['referred_columns'])
            )
            
            foreign_keys.append(ForeignKey(
                source=referencing_group,
                target=referenced_key
            ))

        tables_metadata.append(TableMetadata(
            table_name=t_name,
            columns=all_columns_cache[t_name],
            primary_key=primary_key,
            foreign_keys=foreign_keys
        ))
        
    return tables_metadata