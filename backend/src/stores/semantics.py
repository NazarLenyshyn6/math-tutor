import asyncio
import gc
import json
import shutil
from pathlib import Path
from typing import Any

import chromadb
from langchain_chroma import Chroma
from langchain_classic.retrievers import MergerRetriever
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_huggingface.embeddings import HuggingFaceEndpointEmbeddings

from core.settings import settings
from core.logger import get_logger

logger = get_logger(__file__)

DEFAULT_K = 10


class SemanticsStore:
    def __init__(
        self,
        k: int = DEFAULT_K,
    ) -> None:
        self._store_root = Path(settings.storage_root_path) / "semantics"
        self._chroma_root = self._store_root / "chroma"
        self._registry_path = self._store_root / "collections_registry.json"

        self._store_root.mkdir(parents=True, exist_ok=True)
        self._chroma_root.mkdir(parents=True, exist_ok=True)

        self._k = k
        self._embeddings = HuggingFaceEndpointEmbeddings(
            model=settings.embedding_model_name,
            huggingfacehub_api_token=settings.hf_api_token,
        )

        self._collection_registry = self._load_registry()

        logger.info(
            "Semantic store initialized: root='%s', collections=%s, k=%s",
            self._store_root,
            len(self._collection_registry),
            self._k,
        )

    def _load_registry(self) -> dict[str, dict[str, Any]]:
        if not self._registry_path.exists():
            logger.info(
                "Semantic registry not found; creating empty registry: %s",
                self._registry_path,
            )
            self._registry_path.write_text("{}", encoding="utf-8")
            return {}

        try:
            registry = json.loads(self._registry_path.read_text(encoding="utf-8"))
            logger.info("Loaded semantic registry: collections=%s", len(registry))
            return registry

        except json.JSONDecodeError as exc:
            logger.exception("Semantic registry is corrupted: %s", self._registry_path)
            raise RuntimeError(
                f"Semantic store registry is corrupted: {self._registry_path}"
            ) from exc

    def _save_registry(self) -> None:
        try:
            self._registry_path.write_text(
                json.dumps(self._collection_registry, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )

            logger.info(
                "Saved semantic registry: collections=%s",
                len(self._collection_registry),
            )

        except Exception:
            logger.exception("Failed to save semantic registry: %s", self._registry_path)
            raise

    def _get_collection_persist_dir(self, collection_name: str) -> Path:
        return self._chroma_root / collection_name

    async def _create_collection(
        self,
        collection_name: str,
        chunks: list[Document],
    ) -> str:
        persist_directory = self._get_collection_persist_dir(collection_name)

        logger.info(
            "Creating semantic collection: collection='%s', chunks=%s, persist_directory='%s'",
            collection_name,
            len(chunks),
            persist_directory,
        )

        try:
            await Chroma.afrom_documents(
                documents=chunks,
                collection_name=collection_name,
                embedding=self._embeddings,
                persist_directory=str(persist_directory),
            )
        except Exception:
            logger.exception(
                "Failed to create semantic collection: collection='%s'",
                collection_name,
            )
            raise

        logger.info(
            "Semantic collection created: collection='%s', chunks=%s, persist_directory='%s'",
            collection_name,
            len(chunks),
            persist_directory,
        )

        return str(persist_directory)

    def _load_retriever(self, collection_name: str) -> VectorStoreRetriever:
        if collection_name not in self._collection_registry:
            logger.error(
                "Cannot load semantic retriever; collection is not registered: collection='%s'",
                collection_name,
            )
            raise KeyError(
                f"Collection '{collection_name}' is not registered in semantic store."
            )

        persist_directory = self._collection_registry[collection_name][
            "persist_directory"
        ]

        logger.debug(
            "Loading semantic retriever: collection='%s', k=%s",
            collection_name,
            self._k,
        )

        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self._embeddings,
            persist_directory=persist_directory,
        )

        return vectorstore.as_retriever(search_kwargs={"k": self._k})

    def _get_retriever(self, collection_name: str) -> VectorStoreRetriever:
        logger.debug(
            "Getting semantic retriever directly: collection='%s', k=%s",
            collection_name,
            self._k,
        )
        return Chroma(
            collection_name=collection_name,
            embedding_function=self._embeddings,
            persist_directory=self._collection_registry[collection_name][
                "persist_directory"
            ],
        ).as_retriever(search_kwargs={"k": self._k})

    async def aadd_document(
        self,
        document_name: str,
        chunks: list[Document],
    ) -> None:
        if not chunks:
            logger.error(
                "Cannot add document to semantic store; no chunks produced: document='%s'",
                document_name,
            )
            raise ValueError("Document was loaded but produced no chunks")

        collection_name = document_name

        if collection_name in self._collection_registry:
            logger.info(
                "Semantic document add skipped; already registered: document='%s', collection='%s'",
                document_name,
                collection_name,
            )
            return

        logger.info(
            "Adding document to semantic store: document='%s', collection='%s', chunks=%s",
            document_name,
            collection_name,
            len(chunks),
        )

        try:
            persist_directory = await self._create_collection(
                collection_name=collection_name,
                chunks=chunks,
            )

            self._collection_registry[collection_name] = {
                "persist_directory": persist_directory,
            }

            self._save_registry()

        except Exception:
            logger.exception(
                "Failed to add document to semantic store: document='%s', collection='%s'",
                document_name,
                collection_name,
            )
            raise

        logger.info(
            "Document added to semantic store successfully: document='%s', collection='%s'",
            document_name,
            collection_name,
        )

    async def aremove_document(self, document_name: str) -> None:
        def _delete_chroma_collection(
            collection_name: str,
            persist_directory: Path,
        ):
            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=self._embeddings,
                persist_directory=str(persist_directory),
            )
            vectorstore.delete_collection()
            del vectorstore
            # Evict the cached system so its SQLite handles are released
            chromadb.api.client.SharedSystemClient.clear_system_cache()
            gc.collect()
            shutil.rmtree(persist_directory, ignore_errors=True)

        collection_name = document_name
        if collection_name not in self._collection_registry:
            logger.info(
                "Semantic document remove skipped; not registered: document='%s', collection='%s'",
                document_name,
                collection_name,
            )
            return

        persist_directory = Path(
            self._collection_registry[collection_name]["persist_directory"]
        )

        logger.info(
            "Removing document from semantic store: document='%s', collection='%s', persist_directory='%s'",
            document_name,
            collection_name,
            persist_directory,
        )

        try:
            await asyncio.to_thread(
                _delete_chroma_collection, collection_name, persist_directory
            )

            self._collection_registry.pop(collection_name)
            self._save_registry()

        except Exception as exc:
            logger.exception(
                "Failed to remove document from semantic store: document='%s', collection='%s'",
                document_name,
                collection_name,
            )
            raise RuntimeError(
                f"Failed to delete Chroma collection '{collection_name}'."
            ) from exc

        logger.info(
            "Document removed from semantic store successfully: document='%s', collection='%s'",
            document_name,
            collection_name,
        )

    def get_retriever(self, selected_collections: list[str]) -> MergerRetriever:
        logger.info(
            "Creating semantic merger retriever: selected_collections=%s",
            len(selected_collections),
        )
        retrievers = [
            self._load_retriever(collection_name)
            for collection_name in selected_collections
        ]
        return MergerRetriever(retrievers=retrievers)
