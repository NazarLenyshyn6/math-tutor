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

_PROCESS_POOL = ProcessPoolExecutor(max_workers=int(os.cpu_count() * 0.7))


def _render_pdf_to_pages(
    document_name: str, document_path: str, document_store_path_: str
) -> None:
    source_path = Path(document_path)
    document_store_path = Path(document_store_path_)

    if not source_path.exists():
        raise FileNotFoundError(
            f"Cannot add document. File does not exist: {source_path}"
        )

    if not source_path.is_file():
        raise ValueError(f"Cannot add document. Expected file path, got: {source_path}")

    document_store_path.mkdir(parents=True, exist_ok=True)

    try:
        document = pymupdf.open(str(source_path))
    except Exception as exc:
        raise RuntimeError(f"Failed to open document: {source_path}") from exc

    try:
        page_count = len(document)

        if page_count == 0:
            raise ValueError(f"Document contains no pages: {source_path}")

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

    finally:
        document.close()


class DocumentsStore:
    def __init__(self) -> None:
        self._store_root = Path(settings.storage_root_path) / "documents"
        self._store_root.mkdir(parents=True, exist_ok=True)

    def _get_document_path(self, document_name: str) -> Path:
        return self._store_root / document_name

    async def aadd_document(
        self,
        document_name: str,
        document_path: str,
    ) -> None:
        storage_name = document_name
        document_store_path = str(self._get_document_path(storage_name))

        loop = asyncio.get_running_loop()

        await loop.run_in_executor(
            _PROCESS_POOL,
            _render_pdf_to_pages,
            document_name,
            document_path,
            document_store_path,
        )

    async def aremove_document(self, document_name: str) -> None:
        storage_name = document_name
        document_store_path = self._get_document_path(storage_name)

        if not document_store_path.exists():
            return

        shutil.rmtree(document_store_path)

    def get_page(self, document_name: str, page: int) -> dict:
        if page < 0:
            raise ValueError(f"Page index must be >= 0, got: {page}")

        storage_name = document_name
        document_store_path = self._get_document_path(storage_name)

        if not document_store_path.exists():
            raise FileNotFoundError(f"Document '{document_name}' is not stored.")

        page_path = document_store_path / f"page_{page:04d}.webp"

        if not page_path.exists():
            raise FileNotFoundError(
                f"Page {page} was not found for document '{document_name}'."
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
            return []
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            return [
                {"name": name, "user_description": meta.get("user_description", "")}
                for name, meta in data.items()
            ]
        except Exception:
            return []
