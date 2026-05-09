import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, Loader2, X, ZoomIn, ZoomOut } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { documentPageUrl } from '../api/client';
import clsx from 'clsx';

export default function PageViewerModal() {
  const { viewingPage, setViewingPage, interactions } = useApp();
  if (!viewingPage) return null;

  const { document_name, page: initialPage } = viewingPage;

  // Collect all pages referenced for this document from interactions
  const referencedPages = Array.from(
    new Set(
      interactions
        .flatMap((i) => i.documents)
        .filter((d) => d.document_name === document_name)
        .map((d) => d.page)
    )
  ).sort((a, b) => a - b);

  const [currentPage, setCurrentPage] = useState(initialPage);
  const [zoom, setZoom] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const imgUrl = documentPageUrl(document_name, currentPage);

  function handlePrev() {
    setCurrentPage((p) => Math.max(0, p - 1));
    setLoading(true);
    setError(false);
  }

  function handleNext() {
    setCurrentPage((p) => p + 1);
    setLoading(true);
    setError(false);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setViewingPage(null);
      if (e.key === 'ArrowLeft') handlePrev();
      if (e.key === 'ArrowRight') handleNext();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4
                 bg-black/80 backdrop-blur-sm"
      onClick={() => setViewingPage(null)}
    >
      <motion.div
        initial={{ scale: 0.92, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.92, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 280, damping: 26 }}
        onClick={(e) => e.stopPropagation()}
        className="flex flex-col max-w-4xl w-full max-h-[92vh] bg-bg-card
                   border border-border rounded-2xl shadow-modal overflow-hidden"
      >
        {/* Toolbar */}
        <div className="flex items-center justify-between px-4 py-3
                        border-b border-border shrink-0 bg-bg-surface">
          <div className="flex items-center gap-3">
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-txt-primary">{document_name}</span>
              <span className="text-xs text-txt-muted">Page {currentPage}</span>
            </div>
          </div>

          <div className="flex items-center gap-1">
            {/* Referenced page jumps */}
            {referencedPages.length > 1 && (
              <div className="flex items-center gap-1 mr-3">
                <span className="text-xs text-txt-muted mr-1">Refs:</span>
                {referencedPages.map((p) => (
                  <button
                    key={p}
                    onClick={() => { setCurrentPage(p); setLoading(true); setError(false); }}
                    className={clsx(
                      'px-2 py-1 rounded text-xs font-mono transition-all duration-100',
                      currentPage === p
                        ? 'bg-primary text-white'
                        : 'bg-bg-elevated text-txt-secondary hover:bg-primary-muted hover:text-primary'
                    )}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}

            {/* Zoom */}
            <button
              onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
              disabled={zoom <= 0.5}
              className="w-8 h-8 rounded-lg flex items-center justify-center
                         text-txt-muted hover:text-txt-primary hover:bg-bg-elevated
                         disabled:opacity-30 transition-all duration-150"
              title="Zoom out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-xs text-txt-muted w-12 text-center">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => setZoom((z) => Math.min(3, z + 0.25))}
              disabled={zoom >= 3}
              className="w-8 h-8 rounded-lg flex items-center justify-center
                         text-txt-muted hover:text-txt-primary hover:bg-bg-elevated
                         disabled:opacity-30 transition-all duration-150"
              title="Zoom in"
            >
              <ZoomIn className="w-4 h-4" />
            </button>

            <div className="w-px h-5 bg-border mx-1" />

            {/* Close */}
            <button
              onClick={() => setViewingPage(null)}
              className="w-8 h-8 rounded-lg flex items-center justify-center
                         text-txt-muted hover:text-txt-primary hover:bg-bg-elevated
                         transition-all duration-150"
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Image area */}
        <div className="flex-1 overflow-auto flex items-center justify-center
                        p-4 bg-[#08080F] min-h-0">
          {loading && !error && (
            <div className="absolute inset-0 flex items-center justify-center z-10
                            pointer-events-none">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          )}
          {error ? (
            <div className="text-center text-txt-muted py-12">
              <p className="text-sm">Could not load page image.</p>
            </div>
          ) : (
            <img
              key={imgUrl}
              src={imgUrl}
              alt={`${document_name} page ${currentPage + 1}`}
              onLoad={() => setLoading(false)}
              onError={() => { setLoading(false); setError(true); }}
              className={clsx(
                'max-w-none rounded-md shadow-modal transition-opacity duration-200',
                loading ? 'opacity-0' : 'opacity-100'
              )}
              style={{
                width: `${Math.round(zoom * 700)}px`,
                maxWidth: 'none',
              }}
            />
          )}
        </div>

        {/* Navigation footer */}
        <div className="flex items-center justify-between px-4 py-3
                        border-t border-border shrink-0 bg-bg-surface">
          <button
            onClick={handlePrev}
            disabled={currentPage === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                       text-txt-secondary hover:text-txt-primary hover:bg-bg-elevated
                       disabled:opacity-30 disabled:cursor-not-allowed
                       transition-all duration-150 text-sm"
          >
            <ChevronLeft className="w-4 h-4" />
            Previous
          </button>

          <span className="text-sm text-txt-muted">
            Page{' '}
            <span className="text-txt-primary font-medium">{currentPage}</span>
          </span>

          <button
            onClick={handleNext}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                       text-txt-secondary hover:text-txt-primary hover:bg-bg-elevated
                       transition-all duration-150 text-sm"
          >
            Next
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
