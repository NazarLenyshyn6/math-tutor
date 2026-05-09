import { useRef, useState } from 'react';
import { ArrowUp, Loader2, MessageSquare } from 'lucide-react';
import clsx from 'clsx';
import { useApp } from '../context/AppContext';

export default function ChatInput() {
  const { sendMessage, isStreaming, activeSession, sessions, setIsNewSessionOpen } = useApp();
  const [query, setQuery] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = query.trim().length > 0 && !isStreaming && !!activeSession;

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setQuery(e.target.value);
    // Auto-resize
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }

  async function handleSend() {
    const trimmed = query.trim();
    if (!trimmed || isStreaming || !activeSession) return;
    setQuery('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    await sendMessage(trimmed);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const hasSession = !!activeSession || sessions.length > 0;

  return (
    <div className="shrink-0 px-4 pb-4 pt-3 bg-gradient-to-t from-bg-base to-transparent">
      <div className="max-w-3xl mx-auto">
        {!activeSession && (
          <div className="mb-2 flex items-center gap-2 text-sm text-txt-muted
                          justify-center">
            <MessageSquare className="w-4 h-4" />
            <span>
              {sessions.length === 0 ? (
                <>
                  <button
                    onClick={() => setIsNewSessionOpen(true)}
                    className="text-primary hover:text-primary-light underline
                               underline-offset-2 transition-colors"
                  >
                    Create a session
                  </button>{' '}
                  to start chatting
                </>
              ) : (
                'Select or create a session to start chatting'
              )}
            </span>
          </div>
        )}

        <div
          className={clsx(
            'flex items-end gap-3 rounded-2xl px-4 py-3',
            'bg-bg-elevated border transition-all duration-150',
            activeSession
              ? 'border-border hover:border-primary/30 focus-within:border-primary/50 focus-within:shadow-glow-sm'
              : 'border-border/50 opacity-60'
          )}
        >
          <textarea
            ref={textareaRef}
            value={query}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            disabled={!activeSession || isStreaming}
            placeholder={
              activeSession
                ? 'Ask anything about your documents… (Enter to send, Shift+Enter for new line)'
                : 'Select a session to start chatting'
            }
            rows={1}
            className="flex-1 resize-none bg-transparent outline-none text-txt-primary
                       placeholder:text-txt-muted text-[0.95rem] leading-relaxed
                       disabled:cursor-not-allowed min-h-[1.5rem] max-h-[200px]"
            style={{ height: 'auto' }}
          />

          <button
            onClick={handleSend}
            disabled={!canSend}
            className={clsx(
              'w-9 h-9 rounded-xl flex items-center justify-center shrink-0',
              'transition-all duration-150',
              canSend
                ? 'bg-primary hover:bg-primary-dark text-white shadow-glow-sm hover:shadow-glow cursor-pointer'
                : 'bg-bg-card text-txt-muted cursor-not-allowed'
            )}
            title="Send message"
          >
            {isStreaming
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <ArrowUp className="w-4 h-4" />}
          </button>
        </div>

        <p className="text-center text-xs text-txt-muted mt-2 opacity-60">
          AI responses are grounded in your uploaded documents.
        </p>
      </div>
    </div>
  );
}
