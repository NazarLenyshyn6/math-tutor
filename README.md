# Math Tutor — AI-Powered RAG Learning System

A production-grade, document-grounded mathematics tutoring application. Users upload PDF textbooks and lecture notes; the system answers questions with responses strictly grounded in the uploaded material, rendered with full LaTeX/Markdown support and linked back to exact source pages.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Quick Start](#2-quick-start)
3. [Backend Architecture](#3-backend-architecture)
   - 3.1 [API Layer](#31-api-layer)
   - 3.2 [Document Ingestion Pipeline](#32-document-ingestion-pipeline)
   - 3.3 [Retrieval Pipeline (RAG)](#33-retrieval-pipeline-rag)
   - 3.4 [Response Synthesis](#34-response-synthesis)
   - 3.5 [Conversation Memory](#35-conversation-memory)
   - 3.6 [Storage Layer](#36-storage-layer)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Data Flow Walkthroughs](#5-data-flow-walkthroughs)
6. [Configuration](#6-configuration)
7. [Project Structure](#7-project-structure)
8. [Demos](#8-demos)

---

## 1. System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        Browser (React)                       │
│  Sidebar │ Chat Interface │ Document Viewer │ Upload Modal   │
└──────────────────────┬───────────────────────────────────────┘
                       │  HTTP / Chunked text streaming
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                  FastAPI  (port 8000)                        │
│                                                              │
│  /sessions   /session   /documents   /chat/stream            │
│                                                              │
│   ┌────────────┐  ┌────────────────┐  ┌───────────────────┐  │
│   │  Document  │  │   Document     │  │    Response       │  │
│   │ Ingestion  │  │   Retrieval    │  │    Synthesis      │  │
│   │  Service   │  │   Service      │  │    Service        │  │
│   └─────┬──────┘  └───────┬────────┘  └────────┬──────────┘  │
│         │                 │                     │            │
│   ┌─────▼──────┐  ┌───────▼────────┐  ┌────────▼──────────┐  │
│   │  Documents │  │  Semantics     │  │  Conversation     │  │
│   │  Store     │  │  Store +       │  │  Memory Service   │  │
│   │ (WebP imgs)│  │  Lexicals Store│  │  (JSON sessions)  │  │
│   └────────────┘  └───────┬────────┘  └───────────────────┘  │
└───────────────────────────┼──────────────────────────────────┘
                            │
              ┌─────────────┴──────────────┐
              │                            │
   ┌──────────▼──────┐         ┌───────────▼────────┐
   │   Chroma DB     │         │   Elasticsearch    │
   │ (Vector search) │         │  (Lexical search)  │
   │   local files   │         │   port 9200        │
   └─────────────────┘         └────────────────────┘
```

**Technology stack:**

| Layer | Technology |
|---|---|
| Backend framework | FastAPI + Uvicorn (async Python 3.12) |
| LLM | NVIDIA `llama-3.3-nemotron-super-49b-v1` via LangChain |
| Embeddings | HuggingFace `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store | Chroma (local persistence, HNSW index) |
| Full-text search | Elasticsearch 8.x |
| Reranking | `BAAI/bge-reranker-base` cross-encoder |
| PDF rendering | PyMuPDF → WebP images (250 DPI) |
| Text chunking | LangChain `RecursiveCharacterTextSplitter` + tiktoken |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Math rendering | KaTeX via `remark-math` + `rehype-katex` |
| Containerisation | Docker Compose (3 services) |

---

## 2. Quick Start

### Prerequisites
- Docker and Docker Compose
- NVIDIA AI Endpoints API key (`NVIDIA_API_KEY`)
- HuggingFace API token (`HF_API_TOKEN`)

### Run with Docker (recommended)

```bash
# 1. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# 2. Start all services
docker-compose up --build

# Frontend →  http://localhost:3000
# Backend  →  http://localhost:8000/docs
# ES       →  http://localhost:9200
```

### Run in development

```bash
# Terminal 1 — Elasticsearch
docker-compose up elasticsearch

# Terminal 2 — Backend (hot reload)
cd backend
uv sync
uv run uvicorn src.main:app --reload --port 8000

# Terminal 3 — Frontend (hot reload)
cd frontend
npm install
npm run dev   # http://localhost:5173
```

---

## 3. Backend Architecture

The backend is a single FastAPI application (`backend/src/main.py`) composed of four service layers over three specialised stores. All heavy I/O is async; CPU-bound work (PDF rendering) is offloaded to a `ProcessPoolExecutor`.

### 3.1 API Layer

`backend/src/main.py` — complete endpoint reference:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/sessions` | List all sessions `[{name, active}]` |
| `GET` | `/session` | Load active session interactions |
| `POST` | `/session?name=` | Create + activate a new session |
| `POST` | `/session/activate?name=` | Switch the active session |
| `DELETE` | `/session?name=` | Delete a session (non-active only) |
| `GET` | `/documents/list` | List all uploaded documents |
| `GET` | `/documents/{name}/pages/{page}` | Serve a rendered page as WebP image |
| `GET` | `/documents?name=&page=` | Get page metadata (path, url, mime) |
| `POST` | `/documents` | Upload + process a PDF (multipart) |
| `DELETE` | `/documents?name=` | Remove document from all stores |
| `GET` | `/chat/stream?query=` | Stream AI response (chunked `text/plain`) |

The `/chat/stream` endpoint returns `text/plain; charset=utf-8` with chunked transfer encoding — tokens arrive at the client as they are generated by the LLM. There is no server-side buffering. The frontend reads chunks incrementally via the browser's `ReadableStream` API.

CORS is enabled globally to support the Vite dev server. In Docker, the nginx reverse proxy handles same-origin routing so CORS is a non-issue in production.

---

### 3.2 Document Ingestion Pipeline

`backend/src/services/document_ingestion.py`

Triggered by `POST /documents`. The three storage operations in Step 5 run **in parallel** with `asyncio.gather`, cutting ingestion time significantly for large PDFs.

```
PDF File (uploaded via multipart)
    │
    ▼
Step 1 ── Load with PyMuPDFLoader
            Extract text + page numbers for every page
    │
    ▼
Step 2 ── SHA-256 Fingerprint Check
            Normalise text → compute hash
            Check document_fingerprint_registry.json
            If hash exists → return early (identical content already indexed)
    │
    ▼
Step 3 ── RecursiveCharacterTextSplitter  (tiktoken cl100k_base)
            chunk_size  = 350 tokens
            chunk_overlap = 30 tokens
            Math-aware separator priority (see below)
            Each chunk carries metadata: {document_name, page}
    │
    ▼
Step 4 ── LLM Description Rewriting  (temperature=0.0, max 120 words)
            Expand user's description into topical keywords
            Stored in collections_registry.json for RAG routing decisions
    │
    ▼
Step 5 ── Parallel storage (asyncio.gather):
            ├── DocumentsStore.aadd_document()
            │     PDF page → 250 DPI pixmap → PNG → WebP
            │     Runs in ProcessPoolExecutor (bypasses GIL)
            ├── SemanticsStore.aadd_chunks()
            │     HuggingFace embedding → Chroma upsert
            └── LexicalsStore.aadd_chunks()
                  Bulk index to Elasticsearch
    │
    ▼
Step 6 ── Registry updates
            document_fingerprint_registry.json  ← new hash entry
            collections_registry.json           ← name + descriptions
```

**Math-aware chunking separators** (evaluated in priority order):
```python
[
    "\n\nTheorem ",   "\n\nDefinition ", "\n\nLemma ",
    "\n\nProposition ","\n\nCorollary ", "\n\nProof.",
    "\n\nExample ",   "\n\nExercise ",  "\n\nRemark ",
    "\n\nSolution.",  "\n\n",           "\n",
    ". ", "; ", ", ", " ", ""
]
```
This ensures theorem/definition/proof boundaries are respected before resorting to arbitrary character splits — essential because breaking mid-proof destroys the logical coherence of a chunk and severely degrades retrieval quality.

**PDF page rendering** (`backend/src/stores/documents.py`):
```
PyMuPDF page.get_pixmap(dpi=250, alpha=False)
    → PNG bytes
    → PIL Image
    → WebP (quality=90, method=6)
    → .store/documents/{name}/page_XXXX.webp
```
250 DPI produces sharp enough images to read equations and diagrams. WebP at method=6 gives optimal compression with best quality. Pages are zero-padded to 4 digits for consistent sorting.

---

### 3.3 Retrieval Pipeline (RAG)

`backend/src/services/document_retrieval.py`

This is the most sophisticated component — a 5-stage pipeline that combines multiple retrieval strategies, fuses them with a mathematically principled ranking algorithm, and applies a deep learning reranker for final precision.

```
User query
    │
    ▼
Stage 1 ── Query Expansion  (LLM, structured output schema)
            Generates 3 semantically equivalent alternative phrasings
            Preserves the original intent while varying vocabulary and notation
            Deduplicates against the original
            → [original_query, alt_1, alt_2, alt_3]
    │
    ▼
Stage 2 ── Multi-Source Parallel Retrieval
            ┌────────────────────────────────────────────────┐
            │         Semantic (Chroma)                      │
            │         Embeddings: all-MiniLM-L6-v2           │
            │         K=10 per query                         │
            │                                                │
            │  original  → K=10  weight = 1.0                │
            │  alt_1     → K=10  weight = 0.3                │
            │  alt_2     → K=10  weight = 0.3                │
            │  alt_3     → K=10  weight = 0.3                │
            ├────────────────────────────────────────────────┤
            │         Lexical (Elasticsearch)                │
            │         BM25-like full-text search             │
            │         match operator: "or"  (high recall)    │
            │                                                │
            │  original  → K=10  weight = 1.5                │
            └────────────────────────────────────────────────┘
    │
    ▼
Stage 3 ── Reciprocal Rank Fusion (weighted RRF)
            For each document d across all result lists:

              score(d) = Σᵢ  weight_i / (k + rank_i(d))

            k = 60  (standard constant, smooths rank differences)
            Merges duplicate chunks by ID/hash before scoring
            Keeps top 25 candidates  →  FUSION_TOP_K
    │
    ▼
Stage 4 ── Cross-Encoder Reranking
            Model: BAAI/bge-reranker-base
            Jointly encodes (query, document) pairs — much deeper than
            embedding cosine similarity
            Scores all 25 candidates against the original query
            (not the expansions — avoids scope drift)
            Keeps top 5  →  RERANK_TOP_K
    │
    ▼
Stage 5 ── Long Context Reordering
            LangChain LongContextReorder
            Transformer models exhibit "lost in the middle" attention loss —
            they attend more strongly to content at the beginning and end of
            the context window. Reordering places the highest-scored chunks
            at positions 1 and 5, the next at 2 and 4, etc.
    │
    ▼
    5 ordered, deduplicated, reranked chunks  →  Response Synthesis
```

**Why this specific design?**

| Failure mode | How this pipeline addresses it |
|---|---|
| Query uses different vocabulary than the document | Query expansion + semantic (embedding) retrieval |
| Query needs exact theorem/formula name matching | Lexical (BM25) retrieval with higher weight |
| Both retrievers return noise in lower ranks | Weighted RRF normalises ranks, noise cancels out |
| RRF ranks are still based on shallow signals | Cross-encoder provides deep query-document relevance |
| Best content ends up in the LLM's middle context | Long context reordering pushes it to the edges |

**Retrieval configuration:**
```python
QUERY_EXPANSION_COUNT     = 3
ORIGINAL_SEMANTIC_WEIGHT  = 1.0
REWRITTEN_SEMANTIC_WEIGHT = 0.3   # expansions get lower weight (less certain)
LEXICAL_WEIGHT            = 1.5   # slightly higher — math notation is exact
RRF_K                     = 60    # standard RRF constant
FUSION_TOP_K              = 25    # candidates into reranker
RERANK_TOP_K              = 5     # final chunks into LLM context
```

---

### 3.4 Response Synthesis

`backend/src/services/response_synthesis.py`

**Model:** `nvidia/llama-3.3-nemotron-super-49b-v1`
**Temperature:** 0.2 — low enough for factual precision, non-zero for natural prose
**Max tokens:** 8192 — supports long derivations and multi-step proofs

The service formats the 5 retrieved chunks into a numbered context block, appends the last 3 conversation exchanges, and streams the LLM response token by token.

**Context block format** (max 45,000 characters total):
```
[Material 1]
Source document: calcmolzon
Source page: 12
{chunk text — raw extracted text from the PDF}

---

[Material 2]
Source document: calcmolzon
Source page: 45
{chunk text}

--- (adds materials until 45,000 char limit is reached)
```

The `[Material N]` identifiers are **internal scaffolding** — the system prompt explicitly instructs the LLM never to echo them. All citations in the output use natural format: `(Document: calcmolzon.pdf, page 12)`.

**System prompt engineering highlights:**
- Role: "professional mathematics tutor in a RAG-based learning application"
- Priority order: mathematical correctness > grounding in material > clarity
- Teaching style: intuition first, then formal definition, then derivation
- Strict grounding: every definition, theorem, and formula must come from the provided material
- LaTeX mandate: **all** mathematical notation uses LaTeX — never ASCII (`x^2` is forbidden; `$x^2$` is required)
- Citation format: `(Document: name.pdf, page N)` — never invent names or numbers
- Forbidden phrases: "based on the context", "according to the provided material", "as a RAG system"
- Output structure enforced:
  ```
  ## Main idea
  [intuitive explanation]

  ## Explanation / Step-by-step derivation / Example
  [formal content with LaTeX]

  ## Sources used
  - Document: name.pdf, page N — what this supported
  ```

**Streaming implementation:**
```python
async def astream_response(query: str) -> AsyncIterator[str]:
    context = await retrieval_service.aretrieve(query)   # 5-stage pipeline
    history = memory_service.get_conversation_history()  # last 3 exchanges (6 msgs)

    chain = prompt | llm    # LangChain LCEL pipe

    full_response = ""
    async for chunk in chain.astream({"query": query, "context": context, "history": history}):
        content = getattr(chunk, "content", None)
        if content:
            full_response += content
            yield content                           # ← sent to client immediately

    # Only after the complete response is generated:
    memory_service.add_interaction(query, full_response, retrieved_docs)
```

This is why the frontend reloads `GET /session` after the stream ends — the document references (which pages the AI used) are only persisted to the session file once the full response is complete.

---

### 3.5 Conversation Memory

`backend/src/services/conversation_memory.py`

Sessions are identified by UUID hex strings internally. Human-readable names map to UUIDs via a registry file. Exactly one session is active at a time.

**Persistence structure:**
```
.store/conversation_memory/
├── sessions_registry.json           {"<uuid>": {"active": true/false}, ...}
├── session_name_to_id_mapping.json  {"Calculus Study": "<uuid>", ...}
└── sessions/
    └── <uuid>.json                  [{user, assistant, documents}, ...]
```

**Interaction record format:**
```json
{
  "user": "What is the chain rule?",
  "assistant": "## Main idea\nThe chain rule states...\n\n$$\\frac{d}{dx}[f(g(x))] = f'(g(x)) \\cdot g'(x)$$\n\n...",
  "documents": [
    {"document_name": "calcmolzon", "page": 44},
    {"document_name": "calcmolzon", "page": 47}
  ]
}
```

The `documents` array is the bridge between the AI response and the visual page viewer in the frontend — it records the exact pages that contributed to the answer.

**History window:** The last `N_LAST_MESSAGES = 3` exchanges (6 messages total — 3 user + 3 assistant) are injected into every new prompt, giving the LLM conversational continuity without unbounded context growth.

**Session lifecycle rules:**
- `create_session(name)` → generates UUID, deactivates current active session, activates new one
- `activate_session(name)` → switches the active pointer without deleting any history
- `delete_session(name)` → raises `RuntimeError` if attempting to delete the active session (safety guard — prevents orphaning the current conversation)
- `load_session()` → raises `RuntimeError("No active session")` if none is active; the frontend catches this and shows an empty state

---

### 3.6 Storage Layer

Three specialised stores, each holding a different representation of the same document content:

#### Documents Store (`backend/src/stores/documents.py`)
- **What it stores:** WebP renderings of every PDF page
- **Location:** `.store/documents/{document_name}/page_XXXX.webp`
- **How it's served:** `GET /documents/{name}/pages/{page}` returns a `FileResponse`
- **Why it exists:** Visual grounding — users can see the exact page the AI cited, including diagrams, tables, and handwritten-style notation that didn't survive text extraction

#### Semantics Store (`backend/src/stores/semantics.py`)
- **Technology:** Chroma with local persistence + HNSW index
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim, via HuggingFace Endpoint)
- **Location:** `.store/semantics/chroma/{document_name}/`
- **Registry:** `.store/semantics/collections_registry.json` → maps names to Chroma persist directories
- **K per query:** 10
- **Purpose:** Captures semantic similarity — finds content about "rate of change" even if the chunk says "instantaneous velocity"

#### Lexicals Store (`backend/src/stores/lexicals.py`)
- **Technology:** Elasticsearch 8.x (running as Docker service)
- **Index per document** — name lowercase, one index per uploaded document
- **Document schema:** `{text: text, metadata: {document_name, page, chunk_id}}`
- **Chunk IDs:** `{index_name}:{chunk_idx}` — enables RRF deduplication across retrievers
- **K per query:** 10, match operator `"or"` (maximises recall)
- **Registry:** `.store/lexical/indices_registry.json` → tracks which indices exist
- **Purpose:** Exact term matching — essential for theorem names (`Intermediate Value Theorem`), formula identifiers (`L'Hôpital's rule`), and precise notation that embeddings may normalise away

**Top-level registries in `.store/`:**
```
collections_registry.json           ← {name: {user_description, routing_description}}
document_fingerprint_registry.json  ← {sha256_hash: document_name}  (deduplication)
```

---

## 4. Frontend Architecture

`frontend/` — React 18 + TypeScript + Vite + Tailwind CSS, dark purple theme.

```
AppProvider  (React context, all state)
    ├── Sidebar
    │   ├── Sessions list  (create / activate / delete)
    │   └── Documents list (upload trigger / delete)
    ├── ChatArea
    │   ├── WelcomeScreen      (when no interactions exist)
    │   ├── MessageItem[]      (past interactions from GET /session)
    │   │   ├── User bubble    (gradient, right-aligned)
    │   │   ├── AI response    (full Markdown + LaTeX rendering)
    │   │   └── PageThumb[]    (referenced pages → click opens PageViewerModal)
    │   ├── StreamingMessage   (live token display while streaming)
    │   └── ChatInput          (auto-growing textarea, Enter to send)
    ├── NewSessionModal         (animated spring modal)
    ├── DocumentUploadModal     (drag-and-drop, shows progress)
    └── PageViewerModal         (zoom, keyboard navigation, page jumping)
```

**State management** — single React context with plain `useState` hooks. No external library needed for this single-user, single-page application.

**Streaming flow:**
1. User submits query → `fetch('/chat/stream?query=...')`
2. Get `response.body.getReader()` → `TextDecoder`
3. Loop reading chunks → append to `streamingText` state
4. `StreamingMessage` component re-renders on every chunk
5. Stream ends → `setIsStreaming(false)` → call `GET /session`
6. `MessageItem` for the new interaction appears with `PageThumb` references

**Math rendering pipeline:**
```
Markdown string
    → react-markdown
    → remark-math     (parses $...$ and $$...$$)
    → rehype-katex    (renders to MathML+HTML)
    → rehype-highlight (syntax-highlights code blocks)
    → DOM
```
KaTeX CSS is overridden for the dark theme (light text on dark backgrounds, purple left-border on display equations).

---

## 5. Data Flow Walkthroughs

### 5.1 Uploading a Document

```
User selects PDF + fills name/description
    ↓
POST /documents (multipart: name, description, file)
    ↓
SHA-256 fingerprint check
    If duplicate → return {existed: true, existing_document_name: "..."}
    ↓
RecursiveCharacterTextSplitter
    Math-aware separators, 350-token chunks, 30-token overlap
    Every chunk: {text, document_name, page}
    ↓
asyncio.gather (parallel):
    ├─ PyMuPDF render → WebP images  (.store/documents/name/)
    ├─ HuggingFace embed → Chroma    (.store/semantics/chroma/name/)
    └─ ES bulk index                  (elasticsearch:9200/name/)
    ↓
LLM rewrites description (temperature=0.0) → collections_registry.json
    ↓
Frontend: refreshes document list from GET /documents/list
```

### 5.2 Asking a Question

```
User types question, presses Enter
    ↓
GET /chat/stream?query=...   (frontend opens ReadableStream)
    ↓
Query Expansion: LLM generates 3 alternatives
    ↓
Parallel retrieval:
    Chroma: original(×10) + alt1(×10) + alt2(×10) + alt3(×10)
    ES:     original(×10)
    ↓
Weighted RRF fusion → top 25 candidates
    ↓
BAAI/bge-reranker-base cross-encoder → top 5
    ↓
LongContextReorder (best chunks at position 1 and 5)
    ↓
Build prompt:
    system_prompt (math tutor instructions)
    + conversation history (last 3 exchanges)
    + [Material 1..5] context blocks
    + user query
    ↓
LLM streams tokens → each token yielded → HTTP chunk sent
    ↓  (in parallel on client:)
    Frontend appends chunk to streamingText → re-renders ReactMarkdown+KaTeX
    ↓
Stream complete → memory_service.add_interaction(query, response, docs)
    ↓
Frontend: GET /session → hydrates document references → PageThumb chips appear
```

---

## 6. Configuration

All runtime settings in `backend/.env` (loaded via Pydantic `BaseSettings`):

```env
# LLM (NVIDIA AI Endpoints)
NVIDIA_API_KEY=nvapi-...
LLM_MODEL_NAME=nvidia/llama-3.3-nemotron-super-49b-v1

# Embeddings (HuggingFace Inference Endpoints)
HF_API_TOKEN=hf_...
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2

# Search
ELASTICSEARCH_URL=http://elasticsearch:9200

# Storage
STORAGE_ROOT_PATH=/app/.store
```

---

## 7. Project Structure

```
math_tutor/
├── backend/
│   ├── src/
│   │   ├── main.py                       ← FastAPI app, all endpoints, CORS
│   │   ├── core/
│   │   │   └── settings.py               ← Pydantic BaseSettings (env vars)
│   │   ├── services/
│   │   │   ├── document_ingestion.py     ← Upload pipeline (Steps 1-6)
│   │   │   ├── document_retrieval.py     ← 5-stage RAG pipeline
│   │   │   ├── response_synthesis.py     ← LLM prompt + async streaming
│   │   │   └── conversation_memory.py    ← Session CRUD + history window
│   │   └── stores/
│   │       ├── documents.py              ← PDF → WebP page rendering
│   │       ├── semantics.py              ← Chroma vector DB operations
│   │       └── lexicals.py               ← Elasticsearch operations
│   ├── pyproject.toml                    ← Dependencies (uv)
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── api/client.ts                 ← All API calls + streaming reader
│   │   ├── context/AppContext.tsx        ← Global state (sessions, streaming, docs)
│   │   ├── types/index.ts                ← Shared TypeScript interfaces
│   │   └── components/
│   │       ├── Sidebar.tsx               ← Session + document management
│   │       ├── ChatArea.tsx              ← Message list + auto-scroll
│   │       ├── MessageItem.tsx           ← Markdown + KaTeX + page refs
│   │       ├── StreamingMessage.tsx      ← Live token display
│   │       ├── ChatInput.tsx             ← Auto-growing textarea
│   │       ├── WelcomeScreen.tsx         ← Empty state + example prompts
│   │       ├── NewSessionModal.tsx       ← Session creation
│   │       ├── DocumentUploadModal.tsx   ← Drag-and-drop PDF upload
│   │       └── PageViewerModal.tsx       ← PDF page viewer with zoom
│   ├── nginx.conf                        ← Proxy /session /documents /chat → backend
│   └── Dockerfile                        ← Node build → nginx serve
│
├── .store/                               ← All persisted data (gitignore this)
│   ├── collections_registry.json         ← {name: {user_desc, routing_desc}}
│   ├── document_fingerprint_registry.json← {sha256: document_name}
│   ├── documents/                        ← WebP page images
│   │   └── {name}/
│   │       └── page_XXXX.webp
│   ├── semantics/                        ← Chroma vector databases
│   │   ├── collections_registry.json
│   │   └── chroma/{name}/
│   ├── lexical/
│   │   └── indices_registry.json         ← ES index tracking
│   └── conversation_memory/
│       ├── sessions_registry.json        ← {uuid: {active}}
│       ├── session_name_to_id_mapping.json
│       └── sessions/
│           └── {uuid}.json               ← [{user, assistant, documents}]
│
├── data/
│   ├── sample-docs/                      ← Sample PDFs for testing
│   │   ├── calculus.pdf
│   │   └── linear_algebra.pdf
│   └── demos/                            ← Screen recordings
│       ├── 01_sessions.mov
│       ├── 02_documents.mp4
│       ├── 03_conversation.mov
│       └── 04_memory.mov
│
└── docker-compose.yml                    ← elasticsearch + backend + frontend
```

---

## 8. Demos

The `data/sample-docs/` directory contains sample textbooks you can upload to test the full RAG pipeline without needing your own books.

Below are short walkthroughs of each core feature.

---

### Sessions — create, switch, and delete study sessions

Each session keeps its own independent conversation history, so you can maintain different sessions side by side.

<video src="https://github.com/user-attachments/assets/8f3df5f9-5227-4f5d-8350-771544d66387" controls width="100%"></video>

---

### Documents — upload a PDF and browse source pages

Upload a textbook, track ingestion progress, and explore the document list.

<video src="https://github.com/user-attachments/assets/7c4c3361-b8c9-47b3-b05a-79ff4891694d" controls width="100%"></video>

---

### Conversation — ask questions and get streamed answers

Type a question, watch the AI stream its response token by token, and see the source page thumbnails appear once the answer is complete.

<video src="https://github.com/user-attachments/assets/dbef9bc8-b63c-471c-9586-0b1ef895030d" controls width="100%"></video>

---

### Memory — where everything is stored

Every session, page image, vector database, and Elasticsearch index is persisted in `.store/` on disk. Nothing lives in memory only — all data survives a full container restart.

<video src="https://github.com/user-attachments/assets/3c38f925-6f8e-4acd-bd96-fd99bef12b4c" controls width="100%"></video>
