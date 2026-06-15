from schemas import TableMetadata
from typing import List
import pandas as pd

def get_selected_columns(table: TableMetadata, selected_col_names: List[str]):
    """
    Get the selected columns from the metadata.
    Add all the primary keys of the table.
    """
    return [col for col in table.columns if col.name in selected_col_names or col.is_primary_key]

def is_basic_entity(table: TableMetadata, selected_col_names: List[str]) -> bool:
    cols = get_selected_columns(table, selected_col_names)

    total_fks = sum(1 for c in cols if c.is_foreign_key)

    pk_fks = [c.name for c in cols if c.is_primary_key and c.is_foreign_key]

    if total_fks == 0:
        return True

    if len(pk_fks) == 1 and all(pk in pk_fks for pk in table.primary_keys):
        return True
    
    if len(table.primary_keys) == 0:
        return True
    
    return False

def is_weak_entity(table: TableMetadata, selected_col_names: List[str]) -> bool:
    cols = get_selected_columns(table, selected_col_names)

    pk_fks = [c.name for c in cols if c.is_primary_key and c.is_foreign_key]

    if not pk_fks:
        return False
    
    if all(pk in pk_fks for pk in table.primary_keys):
        return False
    
    chosen_pk_fks = [fk for fk in table.foreign_keys if fk.child_column in pk_fks]

    parent_tables = set(fk.parent_table for fk in chosen_pk_fks)
    if len(parent_tables) == 1:
        return True
    
    return False

def is_complete(engine, chosen_pk_names: List[str], chosen_fk_names: List[str], table_name: str) -> bool:
    """
    Check if the weak entity is "complete".
    :param chosen_fk_names: parent keys, k1
    :param chosen_pk_names: the whole primary keys, k1 + k2
    """
    partial_pks = [pk for pk in chosen_pk_names if pk not in chosen_fk_names]
    selected_cols = chosen_fk_names + partial_pks
    sql = f"SELECT {', '.join(selected_cols)} FROM public.{table_name}"

    try:
        df = pd.read_sql(sql, engine)
        if df.empty:
            return False
        
        counts = df.groupby(chosen_fk_names).size()

        return counts.nunique() == 1
    
    except Exception as e:
        print(f"Error checking completeness: {e}")
        return False

