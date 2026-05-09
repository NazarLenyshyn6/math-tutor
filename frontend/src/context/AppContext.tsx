import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import * as api from '../api/client';
import type { DocumentInfo, DocumentRef, Interaction } from '../types';

interface AppContextValue {
  // State
  sessions: string[];
  activeSession: string | null;
  interactions: Interaction[];
  documents: DocumentInfo[];
  isStreaming: boolean;
  streamingText: string;
  viewingPage: DocumentRef | null;
  isUploadOpen: boolean;
  isNewSessionOpen: boolean;
  error: string | null;
  isLoadingSession: boolean;
  isLoadingDocs: boolean;

  // Actions
  createSession: (name: string) => Promise<void>;
  activateSession: (name: string) => Promise<void>;
  deleteSession: (name: string) => Promise<void>;
  uploadDocument: (name: string, description: string, file: File) => Promise<{ existed: boolean; existing_document_name: string; upload_document_name: string }>;
  deleteDocument: (name: string) => Promise<void>;
  sendMessage: (query: string) => Promise<void>;
  setViewingPage: (page: DocumentRef | null) => void;
  setIsUploadOpen: (open: boolean) => void;
  setIsNewSessionOpen: (open: boolean) => void;
  clearError: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [sessions, setSessions] = useState<string[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [viewingPage, setViewingPage] = useState<DocumentRef | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isNewSessionOpen, setIsNewSessionOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingSession, setIsLoadingSession] = useState(false);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  const showError = (msg: string) => setError(msg);
  const clearError = () => setError(null);

  const loadSessionData = useCallback(async () => {
    setIsLoadingSession(true);
    try {
      const data = await api.loadSession();
      setInteractions(data);
    } catch {
      setInteractions([]);
    } finally {
      setIsLoadingSession(false);
    }
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const sessionList = await api.listSessions();
      setSessions(sessionList.map((s) => s.name));
      const active = sessionList.find((s) => s.active);
      setActiveSession(active ? active.name : null);
    } catch {
      setSessions([]);
    }
  }, []);

  const refreshDocuments = useCallback(async () => {
    setIsLoadingDocs(true);
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
    } catch {
      setDocuments([]);
    } finally {
      setIsLoadingDocs(false);
    }
  }, []);

  // Bootstrap on mount
  useEffect(() => {
    async function init() {
      // Load sessions + documents in parallel
      await Promise.all([refreshSessions(), refreshDocuments()]);
      // Then load the active session's history
      await loadSessionData();
    }
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const createSession = useCallback(async (name: string) => {
    await api.createSession(name);
    setActiveSession(name);
    await refreshSessions();
    await loadSessionData();
  }, [refreshSessions, loadSessionData]);

  const activateSession = useCallback(async (name: string) => {
    await api.activateSession(name);
    setActiveSession(name);
    await loadSessionData();
  }, [loadSessionData]);

  const deleteSession = useCallback(async (name: string) => {
    await api.deleteSession(name);
    if (activeSession === name) {
      setActiveSession(null);
      setInteractions([]);
    }
    await refreshSessions();
  }, [activeSession, refreshSessions]);

  const uploadDocument = useCallback(async (name: string, description: string, file: File) => {
    const result = await api.uploadDocument(name, description, file) as { existed: boolean; existing_document_name: string; upload_document_name: string };
    await refreshDocuments();
    return result;
  }, [refreshDocuments]);

  const deleteDocument = useCallback(async (name: string) => {
    await api.deleteDocument(name);
    await refreshDocuments();
  }, [refreshDocuments]);

  const sendMessage = useCallback(async (query: string) => {
    if (isStreaming) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsStreaming(true);
    setStreamingText('');

    try {
      let accumulated = '';
      await api.streamChat(
        query,
        (chunk) => {
          accumulated += chunk;
          setStreamingText(accumulated);
        },
        controller.signal
      );
    } catch (err: unknown) {
      if ((err as Error)?.name !== 'AbortError') {
        showError('Failed to get a response. Please try again.');
      }
    } finally {
      setIsStreaming(false);
      setStreamingText('');
      // Reload session to pick up new interaction + document references
      await loadSessionData();
    }
  }, [isStreaming, loadSessionData]);

  const value: AppContextValue = {
    sessions,
    activeSession,
    interactions,
    documents,
    isStreaming,
    streamingText,
    viewingPage,
    isUploadOpen,
    isNewSessionOpen,
    error,
    isLoadingSession,
    isLoadingDocs,
    createSession,
    activateSession,
    deleteSession,
    uploadDocument,
    deleteDocument,
    sendMessage,
    setViewingPage,
    setIsUploadOpen,
    setIsNewSessionOpen,
    clearError,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}
