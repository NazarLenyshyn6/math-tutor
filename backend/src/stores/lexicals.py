import json
from pathlib import Path
from typing import Any, AsyncIterator, Mapping

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk
from langchain_classic.retrievers import MergerRetriever
from langchain_core.documents import Document
from langchain_elasticsearch import ElasticsearchRetriever

from core.settings import settings
from core.logger import get_logger

logger = get_logger(__file__)

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

        logger.info(
            "Lexical store initialized: root='%s', registered_indices=%s, k=%s",
            self._store_root,
            len(self._index_registry),
            self._k,
        )

    def _load_registry(self) -> dict[str, dict[str, Any]]:
        if not self._registry_path.exists():
            logger.info(
                "Lexical registry not found; creating empty registry: %s",
                self._registry_path,
            )
            self._registry_path.write_text("{}", encoding="utf-8")
            return {}

        try:
            registry = json.loads(self._registry_path.read_text(encoding="utf-8"))
            logger.info("Loaded lexical registry: indices=%s", len(registry))
            return registry
        except json.JSONDecodeError as exc:
            logger.exception("Lexical registry is corrupted: %s", self._registry_path)
            raise RuntimeError(
                f"Lexical store registry is corrupted: {self._registry_path}"
            ) from exc

    def _save_registry(self) -> None:
        try:
            self._registry_path.write_text(
                json.dumps(self._index_registry, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Saved lexical registry: indices=%s", len(self._index_registry))
        except Exception:
            logger.exception("Failed to save lexical registry: %s", self._registry_path)
            raise

    async def _create_index(self, index_name: str) -> None:
        exists = await self._async_es_client.indices.exists(index=index_name)
        if exists:
            logger.info(
                "Lexical index creation skipped; already exists: index='%s'", index_name
            )
            return

        logger.info("Creating lexical index: index='%s'", index_name)
        try:
            await self._async_es_client.indices.create(
                index=index_name,
                mappings={
                    "properties": {
                        "text": {"type": "text"},
                        "metadata": {"type": "object", "enabled": True},
                    }
                },
            )
        except Exception:
            logger.exception("Failed to create lexical index: index='%s'", index_name)
            raise

        logger.info("Lexical index created: index='%s'", index_name)

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
        logger.info(
            "Indexing lexical chunks: index='%s', chunks=%s",
            index_name,
            len(chunks),
        )

        try:
            success_count, errors = await async_bulk(
                client=self._async_es_client,
                actions=self._iter_index_actions(index_name, chunks),
            )

            await self._async_es_client.indices.refresh(index=index_name)
        except Exception:
            logger.exception("Failed to index lexical chunks: index='%s'", index_name)
            raise

        if errors:
            logger.error(
                "Lexical chunk indexing completed with errors: index='%s', indexed=%s, errors=%s",
                index_name,
                success_count,
                len(errors),
            )
            raise RuntimeError(
                f"Failed to index some chunks for lexical index '{index_name}'"
            )

        logger.info(
            "Lexical chunks indexed successfully: index='%s', indexed=%s",
            index_name,
            success_count,
        )

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
            logger.error(
                "Cannot load retriever; index is not registered: index='%s'", index_name
            )
            raise KeyError(f"Index '{index_name}' is not registered in lexical store.")

        k = self._k

        logger.debug("Loading lexical retriever: index='%s', k=%s", index_name, k)

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
            logger.error(
                "Cannot add document to lexical store; no chunks produced: document='%s'",
                document_name,
            )
            raise ValueError("Document was loaded but produced no chunks")

        index_name = document_name

        if index_name in self._index_registry:
            logger.info(
                "Lexical document add skipped; already registered: document='%s', index='%s'",
                document_name,
                index_name,
            )
            return

        logger.info(
            "Adding document to lexical store: document='%s', index='%s', chunks=%s",
            document_name,
            index_name,
            len(chunks),
        )

        try:
            await self._create_index(index_name)
            await self._index_chunks(index_name, chunks)

            self._index_registry[index_name] = {}

            self._save_registry()

        except Exception:
            logger.exception(
                "Failed to add document to lexical store: document='%s', index='%s'",
                document_name,
                index_name,
            )
            raise

        logger.info(
            "Document added to lexical store successfully: document='%s', index='%s'",
            document_name,
            index_name,
        )

    async def aremove_document(self, document_name: str) -> None:
        index_name = document_name

        if index_name not in self._index_registry:
            logger.info(
                "Lexical document remove skipped; not registered: document='%s', index='%s'",
                document_name,
                index_name,
            )
            return

        logger.info(
            "Removing document from lexical store: document='%s', index='%s'",
            document_name,
            index_name,
        )

        try:
            exists = await self._async_es_client.indices.exists(index=index_name)
            if exists:
                await self._async_es_client.indices.delete(index=index_name)

            self._index_registry.pop(index_name)
            self._save_registry()

        except Exception:
            logger.exception(
                "Failed to remove document from lexical store: document='%s', index='%s'",
                document_name,
                index_name,
            )
            raise

        logger.info(
            "Document removed from lexical store successfully: document='%s', index='%s'",
            document_name,
            index_name,
        )

    def get_retriever(self, selected_indices: list[str]) -> MergerRetriever:
        logger.info(
            "Creating lexical merger retriever: selected_indices=%s",
            len(selected_indices),
        )
        retrievers = [
            self._load_retriever(index_name) for index_name in selected_indices
        ]
        return MergerRetriever(retrievers=retrievers)
