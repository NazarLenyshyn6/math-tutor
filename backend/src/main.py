import shutil
from uuid import uuid4
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse

from core.settings import settings
from core.logger import get_logger
from stores.documents import DocumentsStore
from stores.lexicals import LexicalsStore
from stores.semantics import SemanticsStore
from services.document_ingestion import DocumentIngestionService
from services.document_retrieval import DocumentRetrievalService
from services.conversation_memory import ConversationMemoryService
from services.response_synthesis import ResponseSynthesisService

logger = get_logger(__file__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and wire all application services at startup, then clean up on shutdown.

    Services are attached to ``app.state`` so they can be accessed from any route handler
    without using global variables or dependency injection boilerplate.
    """
    logger.info("Application starting up")

    documents_store = DocumentsStore()
    semantics_store = SemanticsStore()
    lexicals_store = LexicalsStore()
    document_ingestion_service = DocumentIngestionService(
        documents_store=documents_store,
        semantics_store=semantics_store,
        lexicals_store=lexicals_store,
    )
    document_retrieval_service = DocumentRetrievalService(document_ingestion_service)
    conversation_memory_service = ConversationMemoryService()
    response_synthesis_service = ResponseSynthesisService(
        document_retrieval_service, conversation_memory_service
    )

    app.state.documents_store = documents_store
    app.state.semantics_store = semantics_store
    app.state.lexicals_store = lexicals_store
    app.state.document_ingestion_service = document_ingestion_service
    app.state.document_retrieval_service = document_retrieval_service
    app.state.conversation_memory_service = conversation_memory_service
    app.state.response_synthesis_service = response_synthesis_service

    logger.info("Application startup complete")

    yield

    logger.info("Application shutting down")


app = FastAPI(
    lifespan=lifespan,
    title="Math Tutor API",
    description=(
        "RAG-based math tutoring backend. "
        "Upload PDF learning materials (textbooks, lecture notes, worksheets) and ask questions — "
        "the API retrieves relevant content using hybrid semantic + lexical search, reranks it, "
        "and streams a grounded, step-by-step explanation from an LLM. "
        "Conversation history is maintained per session."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/sessions", tags=["Session"])
async def list_sessions():
    """Return all saved sessions with their active status.

    Returns:
        list[dict]: Each item has ``name`` (str) and ``active`` (bool).

    Raises:
        HTTPException 500: If the session store cannot be read.
    """
    try:
        return app.state.conversation_memory_service.list_sessions()
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list sessions: {exc}"
        ) from exc


@app.get("/session", tags=["Session"])
async def load_active_session():
    """Load the currently active session, including its full interaction history.

    Returns:
        dict: Session data with name, metadata, and interaction list.

    Raises:
        HTTPException 404: If no session is currently active.
        HTTPException 500: If the session file cannot be read.
    """
    try:
        return app.state.conversation_memory_service.load_session()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"No active session found: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to load active session: {exc}"
        ) from exc


@app.post("/session", tags=["Session"])
async def create_session(name: str):
    """Create a new session and make it the active one.

    Args:
        name: Unique human-readable label for the session.

    Returns:
        dict: The newly created session object.

    Raises:
        HTTPException 409: If a session with that name already exists.
        HTTPException 500: If the session cannot be persisted.
    """
    try:
        return app.state.conversation_memory_service.create_session(name)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=409, detail=f"Session '{name}' already exists: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create session '{name}': {exc}"
        ) from exc


@app.post("/session/activate", tags=["Session"])
async def activate_session(name: str):
    """Set the named session as the currently active one.

    Args:
        name: Name of an existing session to activate.

    Returns:
        dict: The activated session object.

    Raises:
        HTTPException 404: If no session with the given name exists.
        HTTPException 500: If the activation cannot be persisted.
    """
    try:
        return app.state.conversation_memory_service.activate_session(name)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Session '{name}' not found: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to activate session '{name}': {exc}"
        ) from exc


@app.delete("/session", tags=["Session"])
async def delete_session(name: str):
    """Delete a session and its full interaction history.

    If the deleted session was the active one, no session will be active afterwards.

    Args:
        name: Name of the session to delete.

    Returns:
        dict: Confirmation payload ``{"ok": True}``.

    Raises:
        HTTPException 404: If no session with the given name exists.
        HTTPException 500: If the session file cannot be removed.
    """
    try:
        return app.state.conversation_memory_service.delete_session(name)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Session '{name}' not found: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete session '{name}': {exc}"
        ) from exc


@app.get("/documents/list", tags=["Documents"])
async def list_documents():
    """Return metadata for all ingested documents from the collections registry.

    Returns:
        list[dict]: Each item contains at minimum ``name`` and ``description``.

    Raises:
        HTTPException 500: If the document registry cannot be read.
    """
    try:
        return app.state.documents_store.list_documents()
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list documents: {exc}"
        ) from exc


@app.get("/documents/{document_name}/pages/{page}", tags=["Documents"])
async def serve_document_page_image(document_name: str, page: int):
    """Serve a single rendered page of a document as a WebP image.

    Args:
        document_name: Registered name of the document.
        page: 1-based page number to retrieve.

    Returns:
        FileResponse: The WebP image for the requested page.

    Raises:
        HTTPException 404: If the document or the requested page does not exist.
        HTTPException 500: If the image file cannot be read.
    """
    try:
        page_data = app.state.documents_store.get_page(document_name, page)
        return FileResponse(page_data["path"], media_type="image/webp")
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page} of document '{document_name}' not found: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to serve page {page} of document '{document_name}': {exc}",
        ) from exc


@app.get("/documents", tags=["Documents"])
async def get_document_page(name: str, page: int):
    """Return metadata for a specific page of a document.

    Args:
        name: Registered name of the document.
        page: 1-based page number.

    Returns:
        dict: Page metadata including the file path and page number.

    Raises:
        HTTPException 404: If the document or the requested page does not exist.
        HTTPException 500: If the page metadata cannot be retrieved.
    """
    try:
        return app.state.documents_store.get_page(name, page)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page} of document '{name}' not found: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve page {page} of document '{name}': {exc}",
        ) from exc


@app.post("/documents", tags=["Documents"])
async def upload_document(
    name: str = Form(...), description: str = Form(...), file: UploadFile = File(...)
):
    """Upload a PDF document, ingest it into the vector and lexical stores, and render its pages.

    The uploaded file is saved to a temporary path, processed by the ingestion pipeline,
    and then deleted regardless of success or failure.

    Args:
        name: Unique name to register the document under.
        description: Short human-readable description of the document's content.
        file: The PDF file to ingest (``Content-Type`` must be ``application/pdf``).

    Returns:
        dict: Ingestion result with document metadata and page count.

    Raises:
        HTTPException 400: If the uploaded file is not a PDF.
        HTTPException 409: If a document with the given name already exists.
        HTTPException 500: If ingestion fails for any other reason.
    """
    file_path = Path(settings.storage_root_path) / f"{str(uuid4())}.pdf"
    try:
        if file.content_type != "application/pdf":
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type '{file.content_type}'. Only PDF files are accepted.",
            )

        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = await app.state.document_ingestion_service.aadd_document(
            name, description, str(file_path)
        )

        return result

    except HTTPException:
        raise
    except FileExistsError as exc:
        raise HTTPException(
            status_code=409, detail=f"Document '{name}' already exists: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to ingest document '{name}': {exc}"
        ) from exc

    finally:
        file_path.unlink(missing_ok=True)


@app.delete("/documents", tags=["Documents"])
async def delete_document(name: str):
    """Remove a document from all stores (vector, lexical, and page images).

    Args:
        name: Registered name of the document to delete.

    Returns:
        dict: Confirmation payload ``{"ok": True}``.

    Raises:
        HTTPException 404: If no document with the given name exists.
        HTTPException 500: If deletion fails for any other reason.
    """
    try:
        await app.state.document_ingestion_service.aremove_document(name)
        return {"ok": True}
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Document '{name}' not found: {exc}"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete document '{name}': {exc}"
        ) from exc


@app.get("/chat/stream", tags=["Chat"])
async def stream_chat_response(query: str):
    """Stream a tutoring response for the given query using RAG over ingested documents.

    The response is generated token-by-token and delivered as a chunked plain-text stream.
    The active session's conversation history is used as context, and the session is updated
    with the new interaction after the stream completes.

    Args:
        query: The student's question or message.

    Returns:
        StreamingResponse: A ``text/plain; charset=utf-8`` chunked response.

    Raises:
        HTTPException 400: If the query string is empty.
        HTTPException 500: If the response synthesis pipeline fails to start.
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    try:
        async def token_generator():
            async for token in app.state.response_synthesis_service.astream_response(query):
                yield token

        return StreamingResponse(
            token_generator(),
            media_type="text/plain; charset=utf-8",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to start response stream: {exc}"
        ) from exc
