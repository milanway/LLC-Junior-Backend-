from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from app.database import engine, Base, get_db
from app.models import Document
from app.search_engine import es_client, create_index, INDEX_NAME
from app.schemas import DocumentResponse
import pandas as pd
import io
import ast

app = FastAPI(title="Test Search Service")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await create_index()

@app.on_event("shutdown")
async def shutdown():
    await es_client.close()

@app.post("/upload_data")
async def upload_data(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    content = await file.read()

    df = None
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(content), encoding=enc)
            break
        except UnicodeDecodeError:
            continue

    if df is None:
        raise HTTPException(status_code=400, detail="не та хуйня")

    count = 0
    for _, row in df.iterrows():
        raw_rubrics = row.get("rubrics", "[]")
        rubrics_list = []
        if isinstance(raw_rubrics, str):
            try:
                rubrics_list = ast.literal_eval(raw_rubrics)
                if not isinstance(rubrics_list, list):
                    rubrics_list = [str(rubrics_list)]
            except (ValueError, SyntaxError):
                rubrics_list = [r.strip() for r in raw_rubrics.split(",") if r.strip()]

        try:
            created = pd.to_datetime(row["created_date"]).to_pydatetime()
        except Exception:
            continue

        doc = Document(
            rubrics=rubrics_list,
            text=str(row["text"]),
            created_date=created
        )
        db.add(doc)
        await db.flush() 

        await es_client.index(
            index=INDEX_NAME,
            id=doc.id,
            document={"id": doc.id, "text": doc.text}
        )
        count += 1

    await db.commit()
    return {"status": "ok", "loaded": count}


@app.get("/search", response_model=List[DocumentResponse])
async def search_documents(query: str, db: AsyncSession = Depends(get_db)):
    search_body = {
        "query": {"match": {"text": query}},
        "size": 100
    }

    try:
        resp = await es_client.search(index=INDEX_NAME, body=search_body)
        doc_ids = [hit["_source"]["id"] for hit in resp["hits"]["hits"]]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch error: {e}")

    if not doc_ids:
        return []

    stmt = (
        select(Document)
        .where(Document.id.in_(doc_ids))
        .order_by(Document.created_date.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    return result.scalars().all()

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    stmt = delete(Document).where(Document.id == doc_id)
    result = await db.execute(stmt)

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Document not found in DB")

    await db.commit()

    try:
        await es_client.delete(index=INDEX_NAME, id=doc_id)
    except Exception:
        pass

    return {"status": "deleted", "id": doc_id}