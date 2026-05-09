import { AnimatePresence, motion } from 'framer-motion';
import { AlertCircle, X } from 'lucide-react';
import { useApp } from './context/AppContext';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import DocumentUploadModal from './components/DocumentUploadModal';
import NewSessionModal from './components/NewSessionModal';
import PageViewerModal from './components/PageViewerModal';

export default function App() {
  const { error, clearError, viewingPage, isUploadOpen, isNewSessionOpen } = useApp();

  return (
    <div className="flex h-screen bg-bg-base overflow-hidden">
      {/* Sidebar */}
      <Sidebar />

      {/* Main area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <ChatArea />
      </main>

      {/* Modals */}
      <AnimatePresence>
        {isUploadOpen && <DocumentUploadModal />}
      </AnimatePresence>
      <AnimatePresence>
        {isNewSessionOpen && <NewSessionModal />}
      </AnimatePresence>
      <AnimatePresence>
        {viewingPage && <PageViewerModal />}
      </AnimatePresence>

      {/* Error toast */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="fixed bottom-6 right-6 z-50 flex items-start gap-3 max-w-sm
                       bg-red-950/90 border border-red-500/30 rounded-xl px-4 py-3
                       shadow-modal backdrop-blur-xl"
          >
            <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
            <p className="text-sm text-red-200 flex-1">{error}</p>
            <button
              onClick={clearError}
              className="text-red-400 hover:text-red-200 transition-colors shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
