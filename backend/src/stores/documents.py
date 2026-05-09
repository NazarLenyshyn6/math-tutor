import os
import io
import json
import asyncio
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pymupdf
from PIL import Image
from tqdm import tqdm

from core.settings import settings
from core.logger import get_logger

logger = get_logger(__file__)

_PROCESS_POOL = ProcessPoolExecutor(max_workers=int(os.cpu_count() * 0.7))


def _render_pdf_to_pages(
    document_name: str, document_path: str, document_store_path_: str
) -> None:
    source_path = Path(document_path)
    document_store_path = Path(document_store_path_)

    logger.info(
        "Starting PDF render pipeline: document='%s', source='%s', output='%s'",
        document_name,
        source_path,
        document_store_path,
    )

    if not source_path.exists():
        logger.error("PDF render failed: source file does not exist: %s", source_path)
        raise FileNotFoundError(
            f"Cannot add document. File does not exist: {source_path}"
        )

    if not source_path.is_file():
        logger.error("PDF render failed: source path is not a file: %s", source_path)
        raise ValueError(f"Cannot add document. Expected file path, got: {source_path}")

    document_store_path.mkdir(parents=True, exist_ok=True)

    try:
        document = pymupdf.open(str(source_path))
    except Exception as exc:
        logger.exception("Failed to open PDF document: %s", source_path)
        raise RuntimeError(f"Failed to open document: {source_path}") from exc

    try:
        page_count = len(document)

        if page_count == 0:
            logger.error("PDF render failed: document has no pages: %s", source_path)
            raise ValueError(f"Document contains no pages: {source_path}")

        logger.info(
            "Rendering PDF pages: document='%s', pages=%s",
            document_name,
            page_count,
        )

        for page_idx in tqdm(
            range(page_count),
            desc=f"Rendering '{document_name}' pages",
        ):
            page = document.load_page(page_idx)

            pix = page.get_pixmap(dpi=250, alpha=False)
            png_bytes = pix.tobytes("png")

            image = Image.open(io.BytesIO(png_bytes))

            page_path = document_store_path / f"page_{page_idx:04d}.webp"

            image.save(
                page_path,
                format="WEBP",
                quality=90,
                method=6,
            )

        logger.info(
            "Finished PDF render pipeline: document='%s', pages=%s, output='%s'",
            document_name,
            page_count,
            document_store_path,
        )

    except Exception:
        logger.exception(
            "PDF render pipeline failed: document='%s', source='%s'",
            document_name,
            source_path,
        )
        raise

    finally:
        document.close()


class DocumentsStore:
    def __init__(self) -> None:
        self._store_root = Path(settings.storage_root_path) / "documents"
        self._store_root.mkdir(parents=True, exist_ok=True)

        logger.info("Documents store initialized: root='%s'", self._store_root)

    def _get_document_path(self, document_name: str) -> Path:
        return self._store_root / document_name

    async def aadd_document(
        self,
        document_name: str,
        document_path: str,
    ) -> None:
        storage_name = document_name
        document_store_path = str(self._get_document_path(storage_name))

        logger.info(
            "Adding document to store: document='%s', source='%s'",
            document_name,
            document_path,
        )

        loop = asyncio.get_running_loop()

        try:
            await loop.run_in_executor(
                _PROCESS_POOL,
                _render_pdf_to_pages,
                document_name,
                document_path,
                document_store_path,
            )
        except Exception:
            logger.exception("Failed to add document: document='%s'", document_name)
            raise

        logger.info("Document added successfully: document='%s'", document_name)

    async def aremove_document(self, document_name: str) -> None:
        storage_name = document_name
        document_store_path = self._get_document_path(storage_name)

        if not document_store_path.exists():
            logger.warning(
                "Document remove skipped; not found: document='%s'", document_name
            )
            return

        try:
            shutil.rmtree(document_store_path)
        except Exception:
            logger.exception("Failed to remove document: document='%s'", document_name)
            raise

        logger.info("Document removed successfully: document='%s'", document_name)

    def get_page(self, document_name: str, page: int) -> dict:
        if page < 0:
            logger.error(
                "Invalid page request: document='%s', page=%s",
                document_name,
                page,
            )
            raise ValueError(f"Page index must be >= 0, got: {page}")

        storage_name = document_name
        document_store_path = self._get_document_path(storage_name)

        if not document_store_path.exists():
            logger.error("Document not found in store: document='%s'", document_name)
            raise FileNotFoundError(f"Document '{document_name}' is not stored.")

        page_path = document_store_path / f"page_{page:04d}.webp"

        if not page_path.exists():
            logger.error(
                "Document page not found: document='%s', page=%s",
                document_name,
                page,
            )
            raise FileNotFoundError(
                f"Page {page} was not found for document '{document_name}'."
            )

        logger.info(
            "Document page resolved: document='%s', page=%s, path='%s'",
            document_name,
            page,
            page_path,
        )

        return {
            "document_name": document_name,
            "storage_name": storage_name,
            "page": page,
            "mime_type": "image/webp",
            "filename": page_path.name,
            "path": str(page_path),
            "url": f"/documents/{storage_name}/pages/{page}",
        }

    def list_documents(self):
        registry_path = Path(settings.storage_root_path) / "collections_registry.json"

        if not registry_path.exists():
            logger.info("Documents registry not found: %s", registry_path)
            return []
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            documents = [
                {"name": name, "user_description": meta.get("user_description", "")}
                for name, meta in data.items()
            ]

            logger.info("Listed documents: count=%s", len(documents))
            return documents

        except Exception:
            logger.exception("Failed to read documents registry: %s", registry_path)
            return []
