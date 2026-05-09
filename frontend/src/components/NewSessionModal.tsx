import { useState } from 'react';
import { motion } from 'framer-motion';
import { Loader2, MessageSquarePlus, X } from 'lucide-react';
import { useApp } from '../context/AppContext';

export default function NewSessionModal() {
  const { createSession, setIsNewSessionOpen, sessions } = useApp();
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleCreate() {
    const trimmed = name.trim();
    if (!trimmed) return setError('Session name is required.');
    if (sessions.includes(trimmed)) return setError('A session with that name already exists.');

    setError('');
    setLoading(true);
    try {
      await createSession(trimmed);
      setIsNewSessionOpen(false);
    } catch (e: unknown) {
      setError((e as Error)?.message || 'Failed to create session.');
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') handleCreate();
    if (e.key === 'Escape') setIsNewSessionOpen(false);
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-40 flex items-center justify-center p-4
                 bg-black/60 backdrop-blur-sm"
      onClick={() => setIsNewSessionOpen(false)}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.9, opacity: 0, y: 20 }}
        transition={{ type: 'spring', stiffness: 300, damping: 25 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-bg-card border border-border rounded-2xl
                   shadow-modal p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-muted border border-primary/25
                            flex items-center justify-center">
              <MessageSquarePlus className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold text-txt-primary">New Session</h2>
              <p className="text-xs text-txt-muted">Give your study session a name</p>
            </div>
          </div>
          <button
            onClick={() => setIsNewSessionOpen(false)}
            className="w-8 h-8 rounded-lg flex items-center justify-center
                       text-txt-muted hover:text-txt-primary hover:bg-bg-hover
                       transition-all duration-150"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          <input
            autoFocus
            type="text"
            value={name}
            onChange={(e) => { setName(e.target.value); setError(''); }}
            onKeyDown={handleKeyDown}
            placeholder="e.g. Calculus Study, Chapter 3 Review…"
            className="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-border
                       text-txt-primary placeholder:text-txt-muted text-sm outline-none
                       focus:border-primary/50 focus:shadow-glow-sm transition-all duration-150"
          />
          {error && <p className="text-red-400 text-xs px-1">{error}</p>}
        </div>

        <div className="flex gap-2 mt-5">
          <button
            onClick={() => setIsNewSessionOpen(false)}
            className="flex-1 py-2.5 rounded-xl border border-border text-txt-secondary
                       hover:bg-bg-hover text-sm font-medium transition-all duration-150"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={loading || !name.trim()}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl
                       bg-primary hover:bg-primary-dark text-white text-sm font-medium
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-150 shadow-glow-sm"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Create Session
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
