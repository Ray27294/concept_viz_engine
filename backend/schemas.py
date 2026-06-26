from pydantic import BaseModel, Field
from typing import List, Optional

class TableMetadata(BaseModel):
    table_name: str
    columns: List[Column]
    primary_key: Optional[Key]
    foreign_keys: List[ForeignKey]

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
    source: TableColumnGroup = Field(alias='from')
    target: Key = Field(alias='to')
    class Config:
        populate_by_name = True