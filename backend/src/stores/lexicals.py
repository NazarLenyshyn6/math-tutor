import json
from pathlib import Path
from typing import Any, AsyncIterator, Mapping

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from langchain_classic.retrievers import MergerRetriever
from langchain_core.documents import Document
from langchain_elasticsearch import ElasticsearchRetriever

from core.settings import settings

DEFAULT_K = 10


class LexicalsStore:
    def __init__(self, k: int = DEFAULT_K) -> None:
        self._store_root = Path(settings.storage_root_path) / "lexical"
        self._registry_path = self._store_root / "indices_registry.json"

        self._store_root.mkdir(parents=True, exist_ok=True)

        self._k = k
        self._es_url = settings.elasticsearch_url
        self._async_es_client = AsyncElasticsearch(self._es_url)

        self._index_registry = self._load_registry()

    def _load_registry(self) -> dict[str, dict[str, Any]]:
        if not self._registry_path.exists():
            self._registry_path.write_text("{}", encoding="utf-8")
            return {}

        try:
            return json.loads(self._registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Lexical store registry is corrupted: {self._registry_path}"
            ) from exc

    def _save_registry(self) -> None:
        self._registry_path.write_text(
            json.dumps(self._index_registry, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    async def _create_index(self, index_name: str) -> None:
        exists = await self._async_es_client.indices.exists(index=index_name)
        if exists:
            return

        await self._async_es_client.indices.create(
            index=index_name,
            mappings={
                "properties": {
                    "text": {"type": "text"},
                    "metadata": {"type": "object", "enabled": True},
                }
            },
        )

    async def _iter_index_actions(
        self,
        index_name: str,
        chunks: list[Document],
    ) -> AsyncIterator[dict[str, Any]]:
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{index_name}:{idx}"

            yield {
                "_op_type": "index",
                "_index": index_name,
                "_id": chunk_id,
                "_source": {
                    "text": chunk.page_content,
                    "metadata": {
                        **chunk.metadata,
                        "chunk_id": chunk_id,
                    },
                },
            }

    async def _index_chunks(self, index_name: str, chunks: list[Document]) -> None:
        await async_bulk(
            client=self._async_es_client,
            actions=self._iter_index_actions(index_name, chunks),
        )

        await self._async_es_client.indices.refresh(index=index_name)

    def _load_retriever(self, index_name: str) -> ElasticsearchRetriever:
        def _body_func(query: str) -> dict[str, Any]:
            return {
                "size": k,
                "query": {
                    "match": {
                        "text": {
                            "query": query,
                            "operator": "or",
                        }
                    }
                },
            }

        def _document_mapper(hit: Mapping[str, Any]) -> Document:
            content = hit["_source"].pop("text", "")
            return Document(page_content=content, metadata=hit["_source"]["metadata"])

        if index_name not in self._index_registry:
            raise KeyError(f"Index '{index_name}' is not registered in lexical store.")

        k = self._k

        return ElasticsearchRetriever(
            es_url=self._es_url,
            index_name=index_name,
            body_func=_body_func,
            document_mapper=_document_mapper,
        )

    async def aadd_document(
        self,
        document_name: str,
        chunks: list[Document],
    ) -> None:
        if not chunks:
            raise ValueError("Document was loaded but produced no chunks")

        index_name = document_name

        if index_name in self._index_registry:
            return

        await self._create_index(index_name)
        await self._index_chunks(index_name, chunks)

        self._index_registry[index_name] = {}

        self._save_registry()

    async def aremove_document(self, document_name: str) -> None:
        index_name = document_name

        if index_name not in self._index_registry:
            return

        exists = await self._async_es_client.indices.exists(index=index_name)
        if exists:
            await self._async_es_client.indices.delete(index=index_name)

        self._index_registry.pop(index_name)
        self._save_registry()

    def get_retriever(self, selected_indices: list[str]) -> MergerRetriever:
        retrievers = [
            self._load_retriever(index_name) for index_name in selected_indices
        ]
        return MergerRetriever(retrievers=retrievers)

    async def aclose(self) -> None:
        await self._async_es_client.close()
