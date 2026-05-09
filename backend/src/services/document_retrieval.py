import asyncio
from collections import defaultdict

from pydantic import BaseModel, Field
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_classic.retrievers import MergerRetriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_classic.retrievers.document_compressors.cross_encoder_rerank import (
    CrossEncoderReranker,
)
from langchain_community.document_transformers import LongContextReorder

from core.settings import settings
from core.logger import get_logger
from services.document_ingestion import DocumentIngestionService

logger = get_logger(__file__)

QEURY_EXPANSION_COUNT = 3
ORIGINAL_SEMANTIC_WEIGHT = 1.0
REWRITTEN_SEMANTIC_WEIGHT = 0.3
LEXICAL_WEIGHT = 1.5
RRF_K = 60
FUSION_TOP_K = 25
RERANK_TOP_K = 5


class QueryExpansion(BaseModel):
    queries: list[str] = Field(
        description="Concise alternative search queries that preserve the user's original retrieval intent."
    )


class DocumentRetrievalService:
    def __init__(
        self,
        document_ingestion_service: DocumentIngestionService,
        query_expansion_count: int = QEURY_EXPANSION_COUNT,
        original_semantic_weight: float = ORIGINAL_SEMANTIC_WEIGHT,
        rewritten_semantic_weight: float = REWRITTEN_SEMANTIC_WEIGHT,
        lexical_weight: float = LEXICAL_WEIGHT,
        rrf_k: int = RRF_K,
        fusion_top_k: int = FUSION_TOP_K,
        rerank_top_k: int = RERANK_TOP_K,
    ):
        self._document_ingestion_service = document_ingestion_service
        self._query_expansion_count = query_expansion_count
        self._original_semantic_weight = original_semantic_weight
        self._rewritten_semantic_weight = rewritten_semantic_weight
        self._lexical_weight = lexical_weight
        self._rrf_k = rrf_k
        self._fusion_top_k = fusion_top_k
        self._rerank_top_k = rerank_top_k

        self._query_rewriter = ChatNVIDIA(
            api_key=settings.nvidia_api_key,
            model=settings.llm_model_name,
            temperature=0.2,
            max_completion_tokens=256,
        ).with_structured_output(QueryExpansion)

        self._cross_encoder = HuggingFaceCrossEncoder(
            model_name="BAAI/bge-reranker-base",
        )

        self._reranker = CrossEncoderReranker(
            model=self._cross_encoder,
            top_n=rerank_top_k,
        )

        self._context_reorder = LongContextReorder()

        logger.info(
            "Document retrieval service initialized: query_expansion_count=%s, "
            "fusion_top_k=%s, rerank_top_k=%s, rrf_k=%s",
            self._query_expansion_count,
            self._fusion_top_k,
            self._rerank_top_k,
            self._rrf_k,
        )

        self._query_expansion_prompt = ChatPromptTemplate.from_template("""
You are a search query rewriting assistant for a RAG document retrieval system.

Your task is to rewrite the user's query into alternative search queries that improve semantic retrieval recall.

Generate queries that:
- Preserve the original intent.
- Use different wording and terminology.
- Include likely synonyms, related concepts, and domain-specific phrases.
- Expand abbreviations only when obvious.
- Do not change the meaning of the query.
- Do not answer the query.
- Do not add unrelated assumptions.
- Keep each query concise and searchable.
- Avoid duplicates or near-duplicates.

Return exactly {query_count} rewritten queries.

User query:
{query}
""")

    def _generate_search_queries(self, query: str) -> list[str]:
        logger.info(
            "Generating search queries: query_expansion_count=%s",
            self._query_expansion_count,
        )

        chain = self._query_expansion_prompt | self._query_rewriter

        result: QueryExpansion = chain.invoke(
            {
                "query": query,
                "query_count": self._query_expansion_count,
            }
        )

        seen = {query.strip().lower()}
        search_queries: list[str] = []

        for candidate in result.queries:
            normalized = candidate.strip()
            key = normalized.lower()

            if normalized and key not in seen:
                search_queries.append(normalized)
                seen.add(key)

        queries = search_queries[: self._query_expansion_count]

        logger.info("Search queries generated: count=%s", len(queries))

        return queries

    async def _aretrieve_documents(
        self, query: str, retriever: MergerRetriever
    ) -> list[Document]:
        return await retriever.ainvoke(query)

    def _get_document_key(self, document: Document) -> str:
        metadata = document.metadata or {}

        return str(metadata.get("id") or hash(document.page_content))

    def _fuse_documents(
        self,
        ranked_document_lists: list[list[Document]],
        weights: list[float],
    ) -> list[Document]:
        logger.debug(
            "Fusing document lists: lists=%s, fusion_top_k=%s",
            len(ranked_document_lists),
            self._fusion_top_k,
        )

        document_scores: dict[str, float] = defaultdict(float)
        documents_by_key: dict[str, Document] = {}

        for ranked_documents, weight in zip(ranked_document_lists, weights):
            for rank, document in enumerate(ranked_documents, start=1):
                document_key = self._get_document_key(document)

                documents_by_key.setdefault(document_key, document)
                document_scores[document_key] += weight / (self._rrf_k + rank)

        ranked_document_keys = sorted(
            document_scores,
            key=document_scores.get,
            reverse=True,
        )

        fused = [
            documents_by_key[document_key]
            for document_key in ranked_document_keys[: self._fusion_top_k]
        ]

        logger.info(
            "Documents fused: unique_docs=%s, returned=%s",
            len(documents_by_key),
            len(fused),
        )

        return fused

    def _rerank_documents(
        self,
        query: str,
        documents: list[Document],
    ) -> list[Document]:
        if not documents:
            logger.info("Reranking skipped; no documents to rerank")
            return []

        logger.info(
            "Reranking documents: input=%s, rerank_top_k=%s",
            len(documents),
            self._rerank_top_k,
        )

        reranked_documents = self._reranker.compress_documents(
            documents=documents,
            query=query,
        )

        result = list(reranked_documents)

        logger.info("Documents reranked: returned=%s", len(result))

        return result

    def _reorder_documents(
        self,
        documents: list[Document],
    ) -> list[Document]:
        if not documents:
            logger.info("Reordering skipped; no documents to reorder")
            return []

        reordered_documents = self._context_reorder.transform_documents(documents)
        result = list(reordered_documents)

        logger.debug("Documents reordered: count=%s", len(result))

        return result

    async def aretrieve(self, query: str) -> list[Document]:
        logger.info("Starting document retrieval pipeline")

        retrievers = await self._document_ingestion_service.aget_retrievers(query)

        semantic_retriever = retrievers.get("semantics_retriever")
        lexical_retriever = retrievers.get("lexicals_retriever")

        if not semantic_retriever:
            logger.error("Retrieval failed: semantic retriever not available")
            raise ValueError("Failed to get semantic retriever")

        if not lexical_retriever:
            logger.error("Retrieval failed: lexical retriever not available")
            raise ValueError("Failed to get lexical retriever")

        search_queries = self._generate_search_queries(query)

        retrieval_plan = [
            {
                "query": query,
                "retriever": semantic_retriever,
                "weight": self._original_semantic_weight,
            },
            *[
                {
                    "query": search_query,
                    "retriever": semantic_retriever,
                    "weight": self._rewritten_semantic_weight,
                }
                for search_query in search_queries
            ],
            {
                "query": query,
                "retriever": lexical_retriever,
                "weight": self._lexical_weight,
            },
        ]

        logger.info(
            "Executing retrieval plan: tasks=%s",
            len(retrieval_plan),
        )

        retrieval_tasks = [
            self._aretrieve_documents(
                item["query"],
                item["retriever"],
            )
            for item in retrieval_plan
        ]
        fusion_weights = [item["weight"] for item in retrieval_plan]

        retrieved_documents_list = await asyncio.gather(*retrieval_tasks)
        fused_documents = self._fuse_documents(retrieved_documents_list, fusion_weights)
        reranked_documents = self._rerank_documents(query, fused_documents)
        reordered_documents = self._reorder_documents(reranked_documents)

        logger.info(
            "Document retrieval pipeline complete: final_documents=%s",
            len(reordered_documents),
        )

        return reordered_documents
