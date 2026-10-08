from pydantic import BaseModel as BM
from datetime import datetime
from typing import List

class DocumentResponse(BM):
    id: int
    rubrics: List[str]
    text: str
    created_date: datetime

    class Config:
        from_attributes = True