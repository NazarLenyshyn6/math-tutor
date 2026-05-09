import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { useApp } from '../context/AppContext';
import MessageItem from './MessageItem';
import ChatInput from './ChatInput';
import WelcomeScreen from './WelcomeScreen';
import StreamingMessage from './StreamingMessage';

export default function ChatArea() {
  const {
    interactions,
    isStreaming,
    streamingText,
    activeSession,
    isLoadingSession,
  } = useApp();

  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages / streaming
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [interactions.length, streamingText]);

  const hasMessages = interactions.length > 0 || isStreaming;

  return (
    <div className="flex flex-col h-full">
      {/* Header bar */}
      <div className="flex items-center justify-between px-6 py-3.5
                      border-b border-border/60 bg-bg-surface/50 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse-slow" />
          <span className="text-sm font-medium text-txt-secondary">
            {activeSession ? (
              <span>
                <span className="text-txt-muted">Session:</span>{' '}
                <span className="text-txt-primary">{activeSession}</span>
              </span>
            ) : (
              <span className="text-txt-muted">No active session</span>
            )}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-txt-muted">
            {interactions.length > 0 && `${interactions.length} message${interactions.length > 1 ? 's' : ''}`}
          </span>
        </div>
      </div>

      {/* Messages scroll area */}
      <div className="flex-1 overflow-y-auto">
        {isLoadingSession ? (
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
              <p className="text-sm text-txt-muted">Loading session…</p>
            </div>
          </div>
        ) : !hasMessages ? (
          <WelcomeScreen />
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-1">
            {interactions.map((interaction, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, delay: i === interactions.length - 1 ? 0 : 0 }}
              >
                <MessageItem interaction={interaction} />
              </motion.div>
            ))}
            {isStreaming && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
              >
                <StreamingMessage text={streamingText} />
              </motion.div>
            )}
          </div>
        )}
        <div ref={bottomRef} className="h-6" />
      </div>

      {/* Input area */}
      <ChatInput />
    </div>
  );
}
