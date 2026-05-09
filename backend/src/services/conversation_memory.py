import json
from pathlib import Path
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from core.settings import settings

N_LAST_MESSAGES = 3


class ConversationMemoryService:
    def __init__(self, n_last_messages: int = N_LAST_MESSAGES):
        self._memory_dir = Path(settings.storage_root_path) / "conversation_memory"
        self._sessions_dir = self._memory_dir / "sessions"

        self._sessions_registry_file = self._memory_dir / "sessions_registry.json"
        self._session_names_file = self._memory_dir / "session_name_to_id_mapping.json"

        self._memory_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

        self._sessions_registry = self._load_json_file(self._sessions_registry_file)
        self._session_name_to_id = self._load_json_file(self._session_names_file)
        self._active_session_id = self._get_active_session_id()

        self._n_last_messages = n_last_messages

    def _load_json_file(self, file_path: Path) -> dict:
        if not file_path.exists():
            file_path.write_text("{}", encoding="utf-8")
            return {}

        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"JSON file is corrupted: {file_path}") from exc

    def _save_json_file(self, file_path: Path, data) -> None:
        file_path.write_text(
            json.dumps(data, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    def _save_sessions_registry(self) -> None:
        self._save_json_file(self._sessions_registry_file, self._sessions_registry)

    def _save_session_name_mapping(self) -> None:
        self._save_json_file(self._session_names_file, self._session_name_to_id)

    def _save_metadata(self) -> None:
        self._save_session_name_mapping()
        self._save_sessions_registry()

    def _get_session_path(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.json"

    def _get_active_session_id(self) -> str | None:
        for session_id, metadata in self._sessions_registry.items():
            if metadata.get("active") is True:
                return session_id

        return None

    def _get_session_id_by_name(self, name: str) -> str:
        if name not in self._session_name_to_id:
            raise ValueError(f"Session does not exist: {name}")

        return self._session_name_to_id[name]

    def create_session(self, name: str) -> str:
        if name in self._session_name_to_id:
            raise ValueError(f"Session already exists: {name}")

        session_id = uuid4().hex

        if self._active_session_id:
            self._sessions_registry[self._active_session_id]["active"] = False

        self._session_name_to_id[name] = session_id
        self._sessions_registry[session_id] = {"active": True}
        self._active_session_id = session_id

        self._save_metadata()

    def delete_session(self, name: str) -> None:
        session_id = self._get_session_id_by_name(name)

        if session_id == self._active_session_id:
            self._active_session_id = None

        session_path = self._get_session_path(session_id)

        self._sessions_registry.pop(session_id)
        self._session_name_to_id.pop(name)

        if session_path.exists():
            session_path.unlink()

        self._save_metadata()

    def activate_session(self, name: str) -> None:
        session_id = self._get_session_id_by_name(name)

        if self._active_session_id:
            self._sessions_registry[self._active_session_id]["active"] = False

        self._sessions_registry[session_id]["active"] = True
        self._active_session_id = session_id

        self._save_sessions_registry()

    def load_session(self) -> list[dict]:
        if not self._active_session_id:
            raise RuntimeError("No active session")

        session_path = self._get_session_path(self._active_session_id)

        if not session_path.exists():
            session_path.write_text("[]", encoding="utf-8")
            return []

        try:
            return json.loads(session_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Session {self._active_session_id} is corrupted"
            ) from exc

    def add_interaction(
        self,
        query: str,
        response: str,
        documents: list[Document],
    ) -> None:
        session = self.load_session()

        documents_store = []
        seen_documents = set()

        for document in documents:
            document_id = (
                document.metadata["document_name"] + f"{document.metadata["page"]}"
            )
            if document_id not in seen_documents:
                documents_store.append(
                    {
                        "document_name": document.metadata["document_name"],
                        "page": document.metadata["page"],
                    }
                )
                seen_documents.add(document_id)

        session.append(
            {
                "user": query,
                "assistant": response,
                "documents": documents_store,
            }
        )

        session_path = self._get_session_path(self._active_session_id)
        self._save_json_file(session_path, session)

    def list_sessions(self) -> list[dict]:
        result = []
        for name, session_id in self._session_name_to_id.items():
            meta = self._sessions_registry.get(session_id, {})
            result.append({"name": name, "active": bool(meta.get("active"))})
        return result

    def get_conversation_history(self) -> list[HumanMessage | AIMessage]:
        session = self.load_session()

        conversation_history = []

        for interaction in session:
            conversation_history.extend(
                [
                    HumanMessage(content=interaction["user"]),
                    AIMessage(content=interaction["assistant"]),
                ]
            )

        return conversation_history[(-self._n_last_messages * 2) :]
