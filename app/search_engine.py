import os
from elasticsearch import AsyncElasticsearch as AE

ELASTIC_URL = os.getenv("ELASTIC_URL", "http://localhost:9200")

es_client = AE([ELASTIC_URL])
INDEX_NAME = "documents"

async def create_index():
    if not await es_client.indices.exists(index=INDEX_NAME):
        await es_client.indices.create(
            index=INDEX_NAME,
            mappings={
                "properties": {
                    "id": {"type": "integer"},
                    "text": {"type": "text"}
                }
            }
        )