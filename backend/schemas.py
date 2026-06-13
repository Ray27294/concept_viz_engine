from pydantic import BaseModel
from typing import List, Optional

class ForeignKeyInfo(BaseModel):
    parent_table: str
    parent_column: str
    child_table: str
    child_column: str

class ColumnInfo(BaseModel):
    name: str
    type: str
    is_primary_key: bool
    is_foreign_key: bool
    semantic_type: str # numeric, temporal or lexical

class TableMetadata(BaseModel):
    table_name: str
    columns: List[ColumnInfo]
    primary_keys: List[str]
    foreign_keys: List[ForeignKeyInfo]