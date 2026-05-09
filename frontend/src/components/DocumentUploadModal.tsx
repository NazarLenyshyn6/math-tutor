import { useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, BookOpen, CheckCircle, FileText, Loader2, Trash2, Upload, X } from 'lucide-react';
import clsx from 'clsx';
import { useApp } from '../context/AppContext';

type Phase = 'form' | 'uploading' | 'done' | 'duplicate' | 'replacing';

interface DuplicateInfo {
  existingName: string;
  uploadedName: string;
  isSameName: boolean;
}

export default function DocumentUploadModal() {
  const { uploadDocument, deleteDocument, setIsUploadOpen } = useApp();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>('form');
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [dupInfo, setDupInfo] = useState<DuplicateInfo | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  function validate() {
    if (!name.trim()) return 'Document name is required.';
    if (!description.trim()) return 'Please describe what topics this document covers.';
    if (!file) return 'Please select a PDF file.';
    if (file.type !== 'application/pdf') return 'Only PDF files are accepted.';
    return '';
  }

  async function handleUpload() {
    const err = validate();
    if (err) return setError(err);
    setError('');
    setPhase('uploading');
    try {
      const result = await uploadDocument(name.trim(), description.trim(), file!);
      if (result.existed && result.existing_document_name !== result.upload_document_name) {
        // Same content already exists under a different name
        setDupInfo({
          existingName: result.existing_document_name,
          uploadedName: result.upload_document_name,
          isSameName: false,
        });
        setPhase('duplicate');
      } else if (result.existed && result.existing_document_name === result.upload_document_name) {
        // Same content already exists under the same name
        setDupInfo({
          existingName: result.existing_document_name,
          uploadedName: result.upload_document_name,
          isSameName: true,
        });
        setPhase('duplicate');
      } else {
        setPhase('done');
      }
    } catch (e: unknown) {
      setError((e as Error)?.message || 'Upload failed.');
      setPhase('form');
    }
  }

  async function handleDeleteAndReupload() {
    if (!dupInfo || !file) return;
    setPhase('replacing');
    try {
      await deleteDocument(dupInfo.existingName);
      const result = await uploadDocument(name.trim(), description.trim(), file);
      if (!result.existed) {
        setPhase('done');
      } else {
        setError('Upload still detected as duplicate after deletion. Please try again.');
        setPhase('form');
      }
    } catch (e: unknown) {
      setError((e as Error)?.message || 'Replace failed.');
      setPhase('form');
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.type === 'application/pdf') {
      setFile(dropped);
      if (!name) setName(dropped.name.replace(/\.pdf$/i, ''));
      setError('');
    } else {
      setError('Only PDF files are accepted.');
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      if (!name) setName(f.name.replace(/\.pdf$/i, ''));
      setError('');
    }
  }

  const isLocked = phase === 'uploading' || phase === 'replacing';

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-40 flex items-center justify-center p-4
                 bg-black/60 backdrop-blur-sm"
      onClick={() => !isLocked && setIsUploadOpen(false)}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.9, opacity: 0, y: 20 }}
        transition={{ type: 'spring', stiffness: 300, damping: 25 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg bg-bg-card border border-border rounded-2xl
                   shadow-modal p-6"
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className={clsx(
              'w-10 h-10 rounded-xl border flex items-center justify-center',
              phase === 'duplicate'
                ? 'bg-amber-500/10 border-amber-500/25'
                : 'bg-accent-muted border-accent/25'
            )}>
              {phase === 'duplicate'
                ? <AlertTriangle className="w-5 h-5 text-amber-400" />
                : <Upload className="w-5 h-5 text-accent" />
              }
            </div>
            <div>
              <h2 className="font-semibold text-txt-primary">
                {phase === 'duplicate' ? 'Duplicate Document' : 'Upload Document'}
              </h2>
              <p className="text-xs text-txt-muted">
                {phase === 'duplicate' ? 'This content already exists' : 'PDF textbooks and lecture notes'}
              </p>
            </div>
          </div>
          {!isLocked && (
            <button
              onClick={() => setIsUploadOpen(false)}
              className="w-8 h-8 rounded-lg flex items-center justify-center
                         text-txt-muted hover:text-txt-primary hover:bg-bg-hover
                         transition-all duration-150"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* ── Done ── */}
        {phase === 'done' && (
          <div className="flex flex-col items-center py-8 gap-4">
            <div className="w-16 h-16 rounded-full bg-green-500/15 border border-green-500/30
                            flex items-center justify-center">
              <CheckCircle className="w-8 h-8 text-green-400" />
            </div>
            <div className="text-center">
              <p className="font-semibold text-txt-primary text-lg">Document uploaded!</p>
              <p className="text-txt-muted text-sm mt-1">
                <strong className="text-txt-secondary">{name}</strong> has been processed
                and is ready for queries.
              </p>
            </div>
            <button
              onClick={() => setIsUploadOpen(false)}
              className="mt-2 px-6 py-2.5 rounded-xl bg-primary hover:bg-primary-dark
                         text-white text-sm font-medium transition-all duration-150
                         shadow-glow-sm"
            >
              Done
            </button>
          </div>
        )}

        {/* ── Duplicate warning ── */}
        {phase === 'duplicate' && dupInfo && (
          <div className="space-y-5">
            <div className="rounded-xl border border-amber-500/25 bg-amber-500/8 p-4 space-y-2">
              {dupInfo.isSameName ? (
                <>
                  <p className="text-sm text-txt-primary font-medium">
                    A document named <span className="text-amber-300 font-semibold">"{dupInfo.existingName}"</span> already exists with identical content.
                  </p>
                  <p className="text-xs text-txt-muted leading-relaxed">
                    You already have this document uploaded. You can use it directly, or delete it and re-upload if you want to replace it.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm text-txt-primary font-medium">
                    This file is already uploaded as <span className="text-amber-300 font-semibold">"{dupInfo.existingName}"</span>.
                  </p>
                  <p className="text-xs text-txt-muted leading-relaxed">
                    The same document content cannot be stored under two different names. You can either use the existing document, or delete <span className="font-medium text-txt-secondary">"{dupInfo.existingName}"</span> and re-upload under <span className="font-medium text-txt-secondary">"{dupInfo.uploadedName}"</span>.
                  </p>
                </>
              )}
            </div>

            {/* Existing document card */}
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-bg-elevated border border-border">
              <div className="w-9 h-9 rounded-lg bg-primary/15 border border-primary/20
                              flex items-center justify-center shrink-0">
                <BookOpen className="w-4 h-4 text-primary-light" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-txt-primary truncate">{dupInfo.existingName}</p>
                <p className="text-xs text-txt-muted">Existing document</p>
              </div>
            </div>

            <div className="flex gap-2 pt-1">
              <button
                onClick={() => setIsUploadOpen(false)}
                className="flex-1 py-2.5 rounded-xl border border-border text-txt-secondary
                           hover:bg-bg-hover text-sm font-medium
                           transition-all duration-150"
              >
                Use "{dupInfo.existingName}"
              </button>
              <button
                onClick={handleDeleteAndReupload}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl
                           bg-red-600/80 hover:bg-red-600 text-white text-sm font-medium
                           transition-all duration-150"
              >
                <Trash2 className="w-4 h-4" />
                Delete &amp; re-upload as "{dupInfo.uploadedName}"
              </button>
            </div>
          </div>
        )}

        {/* ── Replacing spinner ── */}
        {phase === 'replacing' && (
          <div className="flex flex-col items-center py-10 gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <p className="text-sm text-txt-muted text-center">
              Deleting existing document and re-uploading…
            </p>
          </div>
        )}

        {/* ── Upload form ── */}
        {(phase === 'form' || phase === 'uploading') && (
          <div className="space-y-4">
            {/* Drop zone */}
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onClick={() => fileInputRef.current?.click()}
              className={clsx(
                'relative flex flex-col items-center justify-center gap-3 h-36 rounded-xl',
                'border-2 border-dashed cursor-pointer transition-all duration-150',
                dragOver
                  ? 'border-accent bg-accent-muted'
                  : file
                  ? 'border-primary/40 bg-primary-muted'
                  : 'border-border hover:border-primary/40 hover:bg-bg-elevated'
              )}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleFileChange}
                className="hidden"
              />
              {file ? (
                <>
                  <FileText className="w-8 h-8 text-primary" />
                  <div className="text-center">
                    <p className="text-sm font-medium text-txt-primary">{file.name}</p>
                    <p className="text-xs text-txt-muted">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <Upload className="w-8 h-8 text-txt-muted" />
                  <div className="text-center">
                    <p className="text-sm font-medium text-txt-secondary">
                      Drop your PDF here or click to browse
                    </p>
                    <p className="text-xs text-txt-muted mt-0.5">PDF files only</p>
                  </div>
                </>
              )}
            </div>

            {/* Name */}
            <div>
              <label className="block text-xs text-txt-muted font-medium mb-1.5 px-0.5">
                Document name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => { setName(e.target.value); setError(''); }}
                placeholder="e.g. calculus, linear_algebra…"
                disabled={isLocked}
                className="w-full px-4 py-2.5 rounded-xl bg-bg-elevated border border-border
                           text-txt-primary placeholder:text-txt-muted text-sm outline-none
                           focus:border-primary/50 focus:shadow-glow-sm
                           disabled:opacity-50 transition-all duration-150"
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs text-txt-muted font-medium mb-1.5 px-0.5">
                Topics covered <span className="text-red-400">*</span>
              </label>
              <textarea
                value={description}
                onChange={(e) => { setDescription(e.target.value); setError(''); }}
                placeholder="e.g. Calculus textbook covering limits, derivatives, integrals, and differential equations…"
                disabled={isLocked}
                rows={3}
                className="w-full px-4 py-2.5 rounded-xl bg-bg-elevated border border-border
                           text-txt-primary placeholder:text-txt-muted text-sm outline-none
                           focus:border-primary/50 focus:shadow-glow-sm resize-none
                           disabled:opacity-50 transition-all duration-150"
              />
              <p className="text-xs text-txt-muted mt-1 px-0.5">
                This helps the AI find the right document for each query.
              </p>
            </div>

            {error && (
              <p className="text-red-400 text-xs px-1 flex items-center gap-1.5">
                <span>⚠</span> {error}
              </p>
            )}

            {/* Actions */}
            <div className="flex gap-2 pt-1">
              <button
                onClick={() => setIsUploadOpen(false)}
                disabled={isLocked}
                className="flex-1 py-2.5 rounded-xl border border-border text-txt-secondary
                           hover:bg-bg-hover text-sm font-medium
                           disabled:opacity-50 transition-all duration-150"
              >
                Cancel
              </button>
              <button
                onClick={handleUpload}
                disabled={isLocked}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl
                           bg-accent hover:bg-accent-light text-white text-sm font-medium
                           disabled:opacity-50 disabled:cursor-not-allowed
                           transition-all duration-150"
              >
                {phase === 'uploading' ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Processing…
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Upload
                  </>
                )}
              </button>
            </div>

            {phase === 'uploading' && (
              <p className="text-center text-xs text-txt-muted animate-pulse-slow">
                Rendering pages, embedding chunks, indexing… this may take a moment.
              </p>
            )}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}
