import json
from pathlib import Path
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from core.settings import settings
from core.logger import get_logger

logger = get_logger(__file__)

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

        logger.info(
            "Conversation memory initialized: sessions=%s, active_session=%s, n_last_messages=%s",
            len(self._session_name_to_id),
            bool(self._active_session_id),
            self._n_last_messages,
        )

    def _load_json_file(self, file_path: Path) -> dict:
        if not file_path.exists():
            logger.info(
                "Memory JSON file not found; creating empty file: %s", file_path
            )
            file_path.write_text("{}", encoding="utf-8")
            return {}

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            logger.debug("Loaded memory JSON file: %s", file_path)
            return data

        except json.JSONDecodeError as exc:
            logger.exception("Memory JSON file is corrupted: %s", file_path)
            raise RuntimeError(f"JSON file is corrupted: {file_path}") from exc

    def _save_json_file(self, file_path: Path, data) -> None:
        try:
            file_path.write_text(
                json.dumps(data, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("Saved memory JSON file: %s", file_path)

        except Exception:
            logger.exception("Failed to save memory JSON file: %s", file_path)
            raise

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
            logger.error(
                "Session lookup failed; session does not exist: name='%s'", name
            )
            raise ValueError(f"Session does not exist: {name}")

        return self._session_name_to_id[name]

    def create_session(self, name: str) -> str:
        if name in self._session_name_to_id:
            logger.error("Cannot create session; already exists: name='%s'", name)
            raise ValueError(f"Session already exists: {name}")

        session_id = uuid4().hex

        logger.info("Creating conversation session: name='%s'", name)

        if self._active_session_id:
            self._sessions_registry[self._active_session_id]["active"] = False

        self._session_name_to_id[name] = session_id
        self._sessions_registry[session_id] = {"active": True}
        self._active_session_id = session_id

        try:
            self._save_metadata()

        except Exception:
            logger.exception("Failed to save conversation session metadata: name='%s'", name)
            raise

        logger.info("Conversation session created: name='%s'", name)

        return session_id

    def delete_session(self, name: str) -> None:
        session_id = self._get_session_id_by_name(name)

        logger.info("Deleting conversation session: name='%s'", name)

        if session_id == self._active_session_id:
            self._active_session_id = None

        session_path = self._get_session_path(session_id)

        try:
            self._sessions_registry.pop(session_id)
            self._session_name_to_id.pop(name)

            if session_path.exists():
                session_path.unlink()

            self._save_metadata()

        except Exception:
            logger.exception("Failed to delete conversation session: name='%s'", name)
            raise

        logger.info("Conversation session deleted: name='%s'", name)

    def activate_session(self, name: str) -> None:
        session_id = self._get_session_id_by_name(name)

        if session_id == self._active_session_id:
            logger.info("Conversation session already active: name='%s'", name)
            return

        logger.info("Activating conversation session: name='%s'", name)

        if self._active_session_id:
            self._sessions_registry[self._active_session_id]["active"] = False

        self._sessions_registry[session_id]["active"] = True
        self._active_session_id = session_id

        try:
            self._save_sessions_registry()

        except Exception:
            logger.exception("Failed to save session activation: name='%s'", name)
            raise

        logger.info("Conversation session activated: name='%s'", name)

    def load_session(self) -> list[dict]:
        if not self._active_session_id:
            logger.error("Cannot load conversation session; no active session")
            raise RuntimeError("No active session")

        session_path = self._get_session_path(self._active_session_id)

        if not session_path.exists():
            logger.info(
                "Active conversation session file not found; creating empty session"
            )
            session_path.write_text("[]", encoding="utf-8")
            return []

        try:
            session = json.loads(session_path.read_text(encoding="utf-8"))
            logger.debug(
                "Loaded conversation session: interactions=%s",
                len(session),
            )
            return session

        except json.JSONDecodeError as exc:
            logger.exception(
                "Conversation session file is corrupted: session_id='%s'",
                self._active_session_id,
            )
            raise RuntimeError(
                f"Session {self._active_session_id} is corrupted"
            ) from exc

    def add_interaction(
        self,
        query: str,
        response: str,
        documents: list[Document],
    ) -> None:
        logger.info(
            "Adding interaction to session: session_id='%s'",
            self._active_session_id,
        )

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

        try:
            self._save_json_file(session_path, session)

        except Exception:
            logger.exception("Failed to save conversation interaction")
            raise

        logger.info(
            "Conversation interaction added: stored_documents=%s, total_interactions=%s",
            len(documents_store),
            len(session),
        )

    def list_sessions(self) -> list[dict]:
        result = []
        for name, session_id in self._session_name_to_id.items():
            meta = self._sessions_registry.get(session_id, {})
            result.append({"name": name, "active": bool(meta.get("active"))})

        logger.info("Listed conversation sessions: count=%s", len(result))

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

        history = conversation_history[(-self._n_last_messages * 2) :]

        logger.debug(
            "Built conversation history: total_messages=%s, returned_messages=%s",
            len(conversation_history),
            len(history),
        )

        return history
