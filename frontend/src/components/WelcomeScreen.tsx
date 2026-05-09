import { BookOpen, FileText, MessageSquarePlus, Sparkles, Upload } from 'lucide-react';
import { useApp } from '../context/AppContext';

const EXAMPLE_QUESTIONS = [
  'What is the chain rule and how is it used?',
  'Explain the fundamental theorem of calculus.',
  'How do I find the integral of a rational function?',
  'What is a limit and how do I compute one?',
];

function Logo() {
  return (
    <div className="relative mb-8">
      <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-primary via-primary-dark to-purple-900
                      flex items-center justify-center shadow-glow-lg mx-auto">
        <BookOpen className="w-10 h-10 text-white" />
      </div>
      <div className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-accent
                      flex items-center justify-center shadow-sm">
        <Sparkles className="w-3.5 h-3.5 text-white" />
      </div>
    </div>
  );
}

export default function WelcomeScreen() {
  const { sendMessage, activeSession, setIsNewSessionOpen, setIsUploadOpen, documents, sessions } =
    useApp();

  const hasSession = !!activeSession;
  const hasDocs = documents.length > 0;
  const hasPreviousSessions = sessions.length > 0;

  // No active session but previous sessions exist — user deleted the active one
  if (!hasSession && hasPreviousSessions) {
    return (
      <div className="flex flex-col items-center justify-center h-full px-6 py-12 text-center">
        <Logo />
        <h2 className="text-3xl font-bold gradient-text mb-3">No Active Session</h2>
        <p className="text-txt-muted text-base mb-10 max-w-md">
          The current session was deleted. Activate an existing session from the sidebar,
          or start a new one.
        </p>
        <button
          onClick={() => setIsNewSessionOpen(true)}
          className="flex items-center gap-3 px-5 py-3.5 rounded-xl
                     bg-bg-elevated border border-primary/25 hover:border-primary/50
                     hover:bg-primary-muted transition-all duration-150 group"
        >
          <div className="w-9 h-9 rounded-lg bg-primary-muted border border-primary/30
                          flex items-center justify-center shrink-0
                          group-hover:bg-primary group-hover:border-transparent
                          transition-all duration-150">
            <MessageSquarePlus className="w-4.5 h-4.5 text-primary group-hover:text-white transition-colors" />
          </div>
          <div className="text-left">
            <p className="font-semibold text-txt-primary text-sm">Create a new session</p>
            <p className="text-txt-muted text-xs">Or click a session in the sidebar to activate it</p>
          </div>
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-full px-6 py-12 text-center">
      <Logo />

      <h2 className="text-3xl font-bold gradient-text mb-3">Math Tutor</h2>
      <p className="text-txt-muted text-base mb-10 max-w-md">
        Your AI-powered mathematics learning assistant. Upload your textbooks and
        lecture notes, then ask anything.
      </p>

      {/* Setup checklist */}
      {(!hasSession || !hasDocs) && (
        <div className="flex flex-col sm:flex-row gap-3 mb-10 w-full max-w-lg">
          {!hasSession && (
            <button
              onClick={() => setIsNewSessionOpen(true)}
              className="flex-1 flex items-center gap-3 px-4 py-4 rounded-xl
                         bg-bg-elevated border border-primary/25 hover:border-primary/50
                         hover:bg-primary-muted text-left transition-all duration-150 group"
            >
              <div className="w-10 h-10 rounded-xl bg-primary-muted border border-primary/30
                              flex items-center justify-center shrink-0
                              group-hover:bg-primary group-hover:border-transparent
                              transition-all duration-150">
                <MessageSquarePlus className="w-5 h-5 text-primary group-hover:text-white
                                              transition-colors" />
              </div>
              <div>
                <p className="font-semibold text-txt-primary text-sm">Create a session</p>
                <p className="text-txt-muted text-xs">Name your study session</p>
              </div>
            </button>
          )}
          {!hasDocs && (
            <button
              onClick={() => setIsUploadOpen(true)}
              className="flex-1 flex items-center gap-3 px-4 py-4 rounded-xl
                         bg-bg-elevated border border-accent/25 hover:border-accent/50
                         hover:bg-accent-muted text-left transition-all duration-150 group"
            >
              <div className="w-10 h-10 rounded-xl bg-accent-muted border border-accent/30
                              flex items-center justify-center shrink-0
                              group-hover:bg-accent group-hover:border-transparent
                              transition-all duration-150">
                <Upload className="w-5 h-5 text-accent group-hover:text-white transition-colors" />
              </div>
              <div>
                <p className="font-semibold text-txt-primary text-sm">Upload a document</p>
                <p className="text-txt-muted text-xs">PDF textbooks or notes</p>
              </div>
            </button>
          )}
        </div>
      )}

      {/* Example questions */}
      {hasSession && hasDocs && (
        <div className="w-full max-w-xl">
          <p className="text-xs text-txt-muted uppercase tracking-wider font-semibold mb-4">
            Try asking
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => sendMessage(q)}
                className="flex items-start gap-2.5 px-4 py-3 rounded-xl text-left
                           bg-bg-elevated border border-border hover:border-primary/35
                           hover:bg-primary-muted transition-all duration-150 group"
              >
                <FileText className="w-4 h-4 text-txt-muted group-hover:text-primary
                                    shrink-0 mt-0.5 transition-colors" />
                <span className="text-sm text-txt-secondary group-hover:text-txt-primary
                                 transition-colors leading-snug">
                  {q}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
