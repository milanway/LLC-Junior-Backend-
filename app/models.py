from sqlalchemy import Column, Integer, String, Text, DateTime, ARRAY
from app.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    rubrics = Column(ARRAY(String), nullable=False)
    text = Column(Text, nullable=False)
    created_date = Column(DateTime, nullable=False)