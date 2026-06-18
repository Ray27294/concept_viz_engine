from pydantic import BaseModel
from typing import List, Optional

class Column(BaseModel):
    name: str
    type: str
    semantic_type: str # numeric, temporal or lexical

class TableColumnGroup(BaseModel):
    table_name: str
    columns: List[Column]

class Key(TableColumnGroup):
    pass

class ForeignKey(BaseModel):
    referencing: TableColumnGroup
    referenced: Key

class TableMetadata(BaseModel):
    table_name: str
    columns: List[Column]
    primary_key: Optional[Key]
    foreign_keys: List[ForeignKey]