import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  BookOpen, ChevronRight, FileText, Loader2,
  MessageSquarePlus, Plus, Trash2, Upload
} from 'lucide-react';
import { useApp } from '../context/AppContext';
import clsx from 'clsx';

export default function Sidebar() {
  const {
    sessions,
    activeSession,
    documents,
    isLoadingDocs,
    activateSession,
    deleteSession,
    deleteDocument,
    setIsUploadOpen,
    setIsNewSessionOpen,
  } = useApp();

  const [deletingSession, setDeletingSession] = useState<string | null>(null);
  const [deletingDoc, setDeletingDoc] = useState<string | null>(null);

  async function handleActivate(name: string) {
    if (name === activeSession) return;
    await activateSession(name);
  }

  async function handleDeleteSession(e: React.MouseEvent, name: string) {
    e.stopPropagation();
    setDeletingSession(name);
    try { await deleteSession(name); } finally { setDeletingSession(null); }
  }

  async function handleDeleteDoc(e: React.MouseEvent, name: string) {
    e.stopPropagation();
    setDeletingDoc(name);
    try { await deleteDocument(name); } finally { setDeletingDoc(null); }
  }

  return (
    <aside className="w-72 shrink-0 flex flex-col h-full bg-bg-surface border-r border-border">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-border/60">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-primary-dark
                          flex items-center justify-center shadow-glow-sm">
            <BookOpen className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-txt-primary leading-tight">Math Tutor</h1>
            <p className="text-xs text-txt-muted">AI-Powered Learning</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {/* Sessions */}
        <section>
          <div className="flex items-center justify-between px-2 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-txt-muted">
              Sessions
            </span>
            <button
              onClick={() => setIsNewSessionOpen(true)}
              title="New session"
              className="w-6 h-6 rounded-md flex items-center justify-center
                         text-txt-muted hover:text-primary hover:bg-primary-muted
                         transition-all duration-150"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>

          {sessions.length === 0 ? (
            <button
              onClick={() => setIsNewSessionOpen(true)}
              className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg
                         border border-dashed border-border hover:border-primary/40
                         hover:bg-primary-muted text-txt-muted hover:text-txt-secondary
                         transition-all duration-150 text-sm"
            >
              <MessageSquarePlus className="w-4 h-4" />
              <span>Create a session</span>
            </button>
          ) : (
            <ul className="space-y-0.5">
              <AnimatePresence initial={false}>
                {sessions.map((name) => {
                  const isActive = name === activeSession;
                  const isDeleting = deletingSession === name;
                  return (
                    <motion.li
                      key={name}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -8 }}
                      transition={{ duration: 0.15 }}
                    >
                      <button
                        onClick={() => handleActivate(name)}
                        className={clsx(
                          'group w-full flex items-center gap-2 px-3 py-2.5 rounded-lg',
                          'transition-all duration-150 text-sm text-left relative',
                          isActive
                            ? 'bg-primary-muted border border-primary/25 text-txt-primary'
                            : 'text-txt-secondary hover:bg-bg-hover hover:text-txt-primary'
                        )}
                      >
                        {isActive && (
                          <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5
                                           bg-primary rounded-r-full" />
                        )}
                        <ChevronRight
                          className={clsx(
                            'w-3.5 h-3.5 shrink-0 transition-transform duration-150',
                            isActive ? 'text-primary rotate-90' : 'text-txt-muted'
                          )}
                        />
                        <span className="flex-1 truncate font-medium">{name}</span>
                        <button
                          onClick={(e) => handleDeleteSession(e, name)}
                          disabled={isDeleting}
                          className="opacity-0 group-hover:opacity-100 w-5 h-5 rounded
                                     flex items-center justify-center shrink-0
                                     text-txt-muted hover:text-red-400 hover:bg-red-500/10
                                     transition-all duration-150"
                          title="Delete session"
                        >
                          {isDeleting
                            ? <Loader2 className="w-3 h-3 animate-spin" />
                            : <Trash2 className="w-3 h-3" />}
                        </button>
                      </button>
                    </motion.li>
                  );
                })}
              </AnimatePresence>
            </ul>
          )}
        </section>

        {/* Documents */}
        <section>
          <div className="flex items-center justify-between px-2 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-txt-muted">
              Documents
            </span>
            <button
              onClick={() => setIsUploadOpen(true)}
              title="Upload document"
              className="w-6 h-6 rounded-md flex items-center justify-center
                         text-txt-muted hover:text-accent hover:bg-accent-muted
                         transition-all duration-150"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>

          {isLoadingDocs ? (
            <div className="flex items-center gap-2 px-3 py-2 text-txt-muted text-sm">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Loading...</span>
            </div>
          ) : documents.length === 0 ? (
            <button
              onClick={() => setIsUploadOpen(true)}
              className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg
                         border border-dashed border-border hover:border-accent/40
                         hover:bg-accent-muted text-txt-muted hover:text-txt-secondary
                         transition-all duration-150 text-sm"
            >
              <Upload className="w-4 h-4" />
              <span>Upload a PDF</span>
            </button>
          ) : (
            <ul className="space-y-0.5">
              <AnimatePresence initial={false}>
                {documents.map((doc) => {
                  const isDeleting = deletingDoc === doc.name;
                  return (
                    <motion.li
                      key={doc.name}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -8 }}
                      transition={{ duration: 0.15 }}
                    >
                      <div
                        className="group flex items-center gap-2 px-3 py-2.5 rounded-lg
                                   hover:bg-bg-hover transition-all duration-150 text-sm"
                      >
                        <FileText className="w-4 h-4 text-accent shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-txt-primary truncate font-medium">{doc.name}</p>
                          {doc.user_description && (
                            <p className="text-txt-muted text-xs truncate">{doc.user_description}</p>
                          )}
                        </div>
                        <button
                          onClick={(e) => handleDeleteDoc(e, doc.name)}
                          disabled={isDeleting}
                          className="opacity-0 group-hover:opacity-100 w-5 h-5 rounded
                                     flex items-center justify-center shrink-0
                                     text-txt-muted hover:text-red-400 hover:bg-red-500/10
                                     transition-all duration-150"
                          title="Delete document"
                        >
                          {isDeleting
                            ? <Loader2 className="w-3 h-3 animate-spin" />
                            : <Trash2 className="w-3 h-3" />}
                        </button>
                      </div>
                    </motion.li>
                  );
                })}
              </AnimatePresence>
            </ul>
          )}
        </section>
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-border/60">
        <p className="text-xs text-txt-muted text-center">
          RAG-powered mathematics tutor
        </p>
      </div>
    </aside>
  );
}
