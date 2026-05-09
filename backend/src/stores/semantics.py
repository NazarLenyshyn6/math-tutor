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

    def _load_registry(self) -> dict[str, dict[str, Any]]:
        if not self._registry_path.exists():
            self._registry_path.write_text("{}", encoding="utf-8")
            return {}

        try:
            return json.loads(self._registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Semantic store registry is corrupted: {self._registry_path}"
            ) from exc

    def _save_registry(self) -> None:
        self._registry_path.write_text(
            json.dumps(self._collection_registry, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    def _get_collection_persist_dir(self, collection_name: str) -> Path:
        return self._chroma_root / collection_name

    async def _create_collection(
        self,
        collection_name: str,
        chunks: list[Document],
    ) -> str:
        persist_directory = self._get_collection_persist_dir(collection_name)

        await Chroma.afrom_documents(
            documents=chunks,
            collection_name=collection_name,
            embedding=self._embeddings,
            persist_directory=str(persist_directory),
        )

        return str(persist_directory)

    def _load_retriever(self, collection_name: str) -> VectorStoreRetriever:
        if collection_name not in self._collection_registry:
            raise KeyError(
                f"Collection '{collection_name}' is not registered in semantic store."
            )

        persist_directory = self._collection_registry[collection_name][
            "persist_directory"
        ]

        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self._embeddings,
            persist_directory=persist_directory,
        )

        return vectorstore.as_retriever(search_kwargs={"k": self._k})

    def _get_retriever(self, collection_name: str) -> VectorStoreRetriever:
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
            raise ValueError("Document was loaded but produced no chunks")

        collection_name = document_name

        persist_directory = await self._create_collection(
            collection_name=collection_name,
            chunks=chunks,
        )

        self._collection_registry[collection_name] = {
            "persist_directory": persist_directory,
        }

        self._save_registry()

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
            return

        persist_directory = Path(
            self._collection_registry[collection_name]["persist_directory"]
        )

        try:
            await asyncio.to_thread(
                _delete_chroma_collection, collection_name, persist_directory
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to delete Chroma collection '{collection_name}'."
            ) from exc

        self._collection_registry.pop(collection_name)
        self._save_registry()

    def get_retriever(self, selected_collections: str) -> MergerRetriever:
        retrievers = [
            self._load_retriever(collection_name)
            for collection_name in selected_collections
        ]
        return MergerRetriever(retrievers=retrievers)
