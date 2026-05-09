import json
import asyncio
import hashlib
from pathlib import Path
from typing import Any


from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.settings import settings
from core.logger import get_logger
from stores.documents import DocumentsStore
from stores.semantics import SemanticsStore
from stores.lexicals import LexicalsStore

logger = get_logger(__file__)

DEFAULT_CHUNK_SIZE = 350
DEFAULT_CHUNK_OVERLAP = 30

DEFAULT_SEPARATORS = [
    "\n\nTheorem ",
    "\n\nDefinition ",
    "\n\nLemma ",
    "\n\nProposition ",
    "\n\nCorollary ",
    "\n\nProof.",
    "\n\nExample ",
    "\n\nExercise ",
    "\n\nRemark ",
    "\n\nSolution.",
    "\n\n",
    "\n",
    ". ",
    "; ",
    ", ",
    " ",
    "",
]


class DocumentIngestionService:
    def __init__(
        self,
        documents_store: DocumentsStore = DocumentsStore(),
        semantics_store: SemanticsStore = SemanticsStore(),
        lexicals_store: LexicalsStore = LexicalsStore(),
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        separators: list[str] = DEFAULT_SEPARATORS,
    ):
        self._store_root = Path(settings.storage_root_path)
        self._collection_registry_path = self._store_root / "collections_registry.json"
        self._document_fingerprint_registry_path = (
            self._store_root / "document_fingerprint_registry.json"
        )

        self._store_root.mkdir(parents=True, exist_ok=True)

        self._documents_store = documents_store
        self._semantics_store = semantics_store
        self._lexicals_store = lexicals_store

        self._splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
        )

        self._router_llm = ChatNVIDIA(
            api_key=settings.nvidia_api_key,
            model=settings.llm_model_name,
            temperature=0.0,
            max_completion_tokens=128,
        )

        self._routing_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a high-recall routing classifier for a retrieval system.\n"
                        "Your job is to decide whether a document collection might contain "
                        "information useful for answering the user query.\n\n"
                        "Critical rule:\n"
                        "- It is much worse to miss a relevant collection than to include an extra one.\n"
                        "- Return True if the collection is clearly relevant OR possibly relevant.\n"
                        "- Return True if the query uses related terminology, broader concepts, prerequisites, "
                        "examples, exercises, proofs, definitions, or surrounding context that may appear in the collection.\n"
                        "- Return False only when the collection is clearly unrelated.\n\n"
                        "Use both descriptions:\n"
                        "- The user description may be vague, informal, or incomplete.\n"
                        "- The routing description is rewritten for retrieval, but may still be imperfect.\n"
                        "- If either description suggests possible relevance, return True.\n\n"
                        "Return exactly one token: True or False.\n"
                        "Do not explain your answer."
                    ),
                ),
                (
                    "human",
                    (
                        "User query:\n{query}\n\n"
                        "Original user-provided description:\n{user_description}\n\n"
                        "Rewritten routing description:\n{routing_description}\n\n"
                        "Should this collection be searched?"
                    ),
                ),
            ]
        )

        self._description_rewrite_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You rewrite document descriptions for a retrieval routing system.\n"
                        "The rewritten description must help decide when this document should be searched.\n\n"
                        "Rules:\n"
                        "- Keep it factual.\n"
                        "- Do not invent content.\n"
                        "- Expand vague descriptions into useful topical keywords when possible.\n"
                        "- Mention likely subject areas, concepts, and use cases.\n"
                        "- Return only the rewritten description.\n"
                        "- Keep it under 120 words."
                    ),
                ),
                (
                    "human",
                    (
                        "Document name:\n{document_name}\n\n"
                        "User-provided description:\n{user_description}\n\n"
                        "Rewrite this description for semantic retrieval routing."
                    ),
                ),
            ]
        )

        self._collection_registry = self._load_json_registry(
            self._collection_registry_path,
            "Collection registry",
        )

        self._document_fingerprint_registry = self._load_json_registry(
            self._document_fingerprint_registry_path,
            "Document fingerprint registry",
        )

        logger.info(
            "Document ingestion service initialized: collections=%s, fingerprints=%s",
            len(self._collection_registry),
            len(self._document_fingerprint_registry),
        )

    def _load_json_registry(
        self,
        registry_path: Path,
        registry_name: str,
    ) -> dict[str, Any]:
        if not registry_path.exists():
            logger.info(
                "%s not found; creating empty registry: %s",
                registry_name,
                registry_path,
            )
            registry_path.write_text("{}", encoding="utf-8")
            return {}

        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            logger.info("Loaded %s: entries=%s", registry_name, len(data))
            return data
        except json.JSONDecodeError as exc:
            logger.exception("%s is corrupted: %s", registry_name, registry_path)
            raise RuntimeError(
                f"{registry_name} is corrupted: {registry_path}"
            ) from exc

    def _save_json_registry(
        self,
        registry_path: Path,
        registry: dict[str, Any],
    ) -> None:
        try:
            registry_path.write_text(
                json.dumps(registry, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("Saved registry: path='%s', entries=%s", registry_path, len(registry))
        except Exception:
            logger.exception("Failed to save registry: %s", registry_path)
            raise

    def _save_collection_registry(self) -> None:
        self._save_json_registry(
            self._collection_registry_path,
            self._collection_registry,
        )

    def _save_document_fingerprint_registry(self) -> None:
        self._save_json_registry(
            self._document_fingerprint_registry_path,
            self._document_fingerprint_registry,
        )

    def _compute_document_fingerprint(self, documents) -> str:
        document_text = "\n".join(document.page_content for document in documents)

        normalized_text = " ".join(document_text.split())

        return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

    def _rewrite_document_description(
        self,
        document_name: str,
        user_description: str,
    ) -> str:
        logger.info("Rewriting document description: document='%s'", document_name)

        messages = self._description_rewrite_prompt.format_messages(
            document_name=document_name,
            user_description=user_description,
        )

        response = self._router_llm.invoke(messages)
        rewritten = str(response.content).strip()

        if not rewritten:
            logger.warning(
                "Description rewrite returned empty; falling back to user description: document='%s'",
                document_name,
            )
            return user_description

        logger.info("Document description rewritten: document='%s'", document_name)
        return rewritten

    async def _is_collection_relevant(
        self,
        query: str,
        user_description: str,
        routing_description: str,
    ) -> bool:
        messages = self._routing_prompt.format_messages(
            query=query,
            user_description=user_description,
            routing_description=routing_description,
        )

        response = await self._router_llm.ainvoke(messages)
        answer = str(response.content).strip().lower()

        if answer.startswith("false"):
            logger.debug("Collection relevance check: relevant=False")
            return False

        # High-recall default: include collection if output is unclear.
        logger.debug("Collection relevance check: relevant=True")
        return True

    async def _select_relevant_collections(self, query: str) -> list[str]:
        if not self._collection_registry:
            logger.info("Collection selection skipped; no collections registered")
            return []

        collection_names = list(self._collection_registry.keys())

        logger.info(
            "Selecting relevant collections: total_collections=%s",
            len(collection_names),
        )

        tasks = [
            self._is_collection_relevant(
                query=query,
                user_description=self._collection_registry[collection_name][
                    "user_description"
                ],
                routing_description=self._collection_registry[collection_name][
                    "routing_description"
                ],
            )
            for collection_name in collection_names
        ]

        relevance_results = await asyncio.gather(*tasks)

        selected_collections = [
            collection_name
            for collection_name, is_relevant in zip(collection_names, relevance_results)
            if is_relevant
        ]

        result = selected_collections or collection_names

        logger.info(
            "Collections selected: selected=%s, total=%s",
            len(result),
            len(collection_names),
        )

        return result

    async def aadd_document(
        self,
        document_name: str,
        document_description: str,
        document_path: str,
    ) -> dict:
        source_path = Path(document_path)

        logger.info(
            "Adding document: document='%s', source='%s'",
            document_name,
            source_path,
        )

        if not source_path.exists():
            logger.error("Document add failed: source file does not exist: %s", source_path)
            raise FileNotFoundError(
                f"Cannot add document. File does not exist: {source_path}"
            )

        if not source_path.is_file():
            logger.error("Document add failed: source path is not a file: %s", source_path)
            raise ValueError(
                f"Cannot add document. Expected a file path, got: {source_path}"
            )

        documents = PyMuPDFLoader(str(source_path)).load()
        if not documents:
            logger.error("Document add failed: no pages loaded: source='%s'", source_path)
            raise ValueError(f"No pages were loaded from document: {source_path}")

        logger.info(
            "Document loaded: document='%s', pages=%s",
            document_name,
            len(documents),
        )

        document_fingerprint = self._compute_document_fingerprint(documents)
        existing_document_name = self._document_fingerprint_registry.get(
            document_fingerprint
        )

        if existing_document_name is not None:
            logger.info(
                "Document add skipped; duplicate detected: document='%s', existing='%s'",
                document_name,
                existing_document_name,
            )
            return {
                "existed": True,
                "existing_document_name": existing_document_name,
                "upload_document_name": document_name,
            }

        chunks = self._splitter.split_documents(documents)
        if not chunks:
            logger.error(
                "Document add failed: no chunks produced: document='%s', source='%s'",
                document_name,
                source_path,
            )
            raise ValueError(
                f"Document was loaded but produced no chunks: {source_path}"
            )

        logger.info(
            "Document chunked: document='%s', chunks=%s",
            document_name,
            len(chunks),
        )

        for chunk in chunks:
            chunk.metadata["document_name"] = document_name

        try:
            tasks = [
                self._documents_store.aadd_document(document_name, document_path),
                self._semantics_store.aadd_document(document_name, chunks),
                self._lexicals_store.aadd_document(document_name, chunks),
            ]

            await asyncio.gather(*tasks)
        except Exception:
            logger.exception("Failed to ingest document into stores: document='%s'", document_name)
            raise

        routing_description = self._rewrite_document_description(
            document_name=document_name,
            user_description=document_description,
        )

        self._collection_registry[document_name] = {
            "user_description": document_description,
            "routing_description": routing_description,
        }
        self._document_fingerprint_registry[document_fingerprint] = document_name

        self._save_collection_registry()
        self._save_document_fingerprint_registry()

        logger.info("Document added successfully: document='%s'", document_name)

        return {
            "existed": False,
            "existing_document_name": document_name,
            "upload_document_name": document_name,
        }

    async def aremove_document(self, document_name: str) -> None:
        if document_name not in self._collection_registry:
            logger.info(
                "Document remove skipped; not registered: document='%s'", document_name
            )
            return

        logger.info("Removing document: document='%s'", document_name)

        try:
            tasks = [
                self._documents_store.aremove_document(document_name),
                self._semantics_store.aremove_document(document_name),
                self._lexicals_store.aremove_document(document_name),
            ]

            await asyncio.gather(*tasks)
        except Exception:
            logger.exception("Failed to remove document from stores: document='%s'", document_name)
            raise

        self._collection_registry.pop(document_name)

        fingerprints_to_remove = [
            fingerprint
            for fingerprint, stored_document_name in self._document_fingerprint_registry.items()
            if stored_document_name == document_name
        ]

        for fingerprint in fingerprints_to_remove:
            self._document_fingerprint_registry.pop(fingerprint)

        logger.info(
            "Document removed: document='%s', fingerprints_removed=%s",
            document_name,
            len(fingerprints_to_remove),
        )

        self._save_collection_registry()
        self._save_document_fingerprint_registry()

    async def aget_retrievers(self, query: str):
        selected_collections = await self._select_relevant_collections(query)
        if not selected_collections:
            logger.error("Cannot create retrievers; no collections registered")
            raise RuntimeError(
                "Cannot create retriever. No documents are registered in semantic store."
            )

        logger.info(
            "Building retrievers: selected_collections=%s",
            len(selected_collections),
        )

        semantics_retriever = self._semantics_store.get_retriever(selected_collections)
        lexicals_retriever = self._lexicals_store.get_retriever(selected_collections)

        logger.info("Retrievers built successfully")

        return {
            "semantics_retriever": semantics_retriever,
            "lexicals_retriever": lexicals_retriever,
        }
