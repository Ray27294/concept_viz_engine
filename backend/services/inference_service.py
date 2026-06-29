from schemas import TableMetadata, Column
from typing import List, Set
import pandas as pd

def _get_pk_names(table: TableMetadata) -> Set[str]:
    """Get the set of primary key column names for the given table."""
    if not table.primary_key:
        return set()
    return {col.name for col in table.primary_key.columns}

def _get_fk_names(table: TableMetadata) -> Set[str]:
    """Get the set of foreign key column names for the given table."""
    fk_names = set()
    for fk in table.foreign_keys:
        for col in fk.source.columns:
            fk_names.add(col.name)
    return fk_names

def get_selected_columns(table: TableMetadata, selected_col_names: List[str]):
    """
    Get the selected columns from the metadata.
    Add the primary key of the table.
    """
    pk_names = _get_pk_names(table)
    return [col for col in table.columns if col.name in selected_col_names or col.name in pk_names]

def is_basic_entity(table: TableMetadata, selected_col_names: List[str]) -> bool:
    selected_cols = get_selected_columns(table, selected_col_names)
    selected_names = {c.name for c in selected_cols}

    pk_names = _get_pk_names(table)
    fk_names = _get_fk_names(table)

    selected_fks = selected_names & fk_names
    pk_fks = pk_names & fk_names

    if len(selected_fks) == 0:
        return True

    if len(pk_fks) == 1 and pk_fks == pk_names:
        return True
    
    return False

def is_weak_entity(table: TableMetadata, selected_col_names: List[str]) -> bool:
    selected_cols = get_selected_columns(table, selected_col_names)
    selected_names = {c.name for c in selected_cols}

    pk_names = _get_pk_names(table)
    fk_names = _get_fk_names(table)

    pk_fks = pk_names & fk_names

    if not pk_fks:
        return False
    
    if pk_fks == pk_names:
        return False
    
    chosen_pk_fks = [fk for fk in table.foreign_keys
                     if any(c.name in pk_fks for c in fk.source.columns)]

    parent_tables = set(fk.target.table_name for fk in chosen_pk_fks)
    if len(parent_tables) == 1:
        return True
    
    return False

def is_complete_weak(engine, chosen_pk_names: List[str], chosen_fk_names: List[str], table_name: str) -> bool:
    """
    Check if the weak entity is "complete".
    :param chosen_fk_names: parent keys, k1
    :param chosen_pk_names: the whole primary key, k1 + k2
    """
    partial_pks = [pk for pk in chosen_pk_names if pk not in chosen_fk_names]
    selected_cols = chosen_fk_names + partial_pks
    sql = f"SELECT {', '.join(selected_cols)} FROM public.{table_name}"

    try:
        df = pd.read_sql(sql, engine)
        if df.empty:
            return False
        
        df['k2_tuple'] = df[partial_pks].apply(tuple, axis=1)
        
        k2_sets = df.groupby(chosen_fk_names)['k2_tuple'].apply(frozenset)

        return k2_sets.nunique() == 1
    
    except Exception as e:
        print(f"Error checking completeness: {e}")
        return False
    
def is_one_many_relationship(table: TableMetadata, selected_col_names: List[str]) -> bool:
    selected_cols = get_selected_columns(table, selected_col_names)
    selected_names = {c.name for c in selected_cols}
    
    pk_names = _get_pk_names(table)
    fk_names = _get_fk_names(table)
    
    # pure foreign keys: selected foreign keys that are not primary keys
    pure_fks = (selected_names & fk_names) - pk_names
    
    if len(pure_fks) == 0:
        return False
        
    chosen_fks = [
        fk for fk in table.foreign_keys 
        if any(c.name in pure_fks for c in fk.source.columns)
    ]
    
    parent_tables = {fk.target.table_name for fk in chosen_fks}
    if len(parent_tables) == 1:
        return True
    return False

def is_many_many_relationship(table: TableMetadata, selected_col_names: List[str]) -> bool:
    pk_names = _get_pk_names(table)
    fk_names = _get_fk_names(table)
    
    if pk_names != fk_names:
        return False
        
    if len(table.foreign_keys) < 2:
        return False
        
    return True

def is_reflexive(table: TableMetadata) -> bool:
    parent_tables = {fk.target.table_name for fk in table.foreign_keys}

    return len(parent_tables) == 1

