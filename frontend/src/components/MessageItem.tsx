import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import type { Components } from 'react-markdown';
import { BookOpen, User, FileImage } from 'lucide-react';
import { useApp } from '../context/AppContext';
import type { Interaction, DocumentRef } from '../types';
import { documentPageUrl } from '../api/client';
import { normalizeMath } from '../utils/normalizeMath';

const markdownComponents: Components = {
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold text-txt-primary mt-5 mb-2 pb-2
                   border-b border-primary/20 first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-semibold text-txt-primary/90 mt-4 mb-1.5">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-sm font-semibold text-txt-secondary mt-3 mb-1">{children}</h4>
  ),
  p: ({ children }) => <p className="my-2 leading-relaxed text-[0.95rem]">{children}</p>,
  ul: ({ children }) => <ul className="my-2 pl-5 space-y-1 list-disc">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 pl-5 space-y-1 list-decimal">{children}</ol>,
  li: ({ children }) => <li className="text-[0.95rem] text-txt-secondary/90">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-txt-primary">{children}</strong>,
  em: ({ children }) => <em className="italic text-primary-light">{children}</em>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-primary/40 pl-4 py-1 my-3
                           text-txt-muted italic text-sm">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-border my-4" />,
  code: ({ children, className }) => {
    const isInline = !className;
    if (isInline) {
      return (
        <code className="font-mono text-[0.82em] px-1.5 py-0.5 rounded
                         bg-primary-muted border border-primary/20 text-primary-light">
          {children}
        </code>
      );
    }
    return <code className={className}>{children}</code>;
  },
  pre: ({ children }) => (
    <pre className="my-3 rounded-lg border border-border overflow-x-auto
                    bg-[#0F0F1E] text-sm font-mono">
      {children}
    </pre>
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer"
       className="text-primary-light underline underline-offset-2 hover:text-primary
                  transition-colors">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-4 rounded-xl border border-border">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-primary/10 border-b-2 border-primary/30">{children}</thead>
  ),
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => (
    <tr className="border-b border-border/40 hover:bg-primary/5 transition-colors last:border-0">
      {children}
    </tr>
  ),
  th: ({ children }) => (
    <th className="px-4 py-2.5 text-left font-semibold text-txt-primary whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-4 py-2.5 text-txt-secondary">{children}</td>
  ),
};

interface PageThumbProps {
  doc: DocumentRef;
}

function PageThumb({ doc }: PageThumbProps) {
  const { setViewingPage } = useApp();
  const imgUrl = documentPageUrl(doc.document_name, doc.page);

  return (
    <button
      onClick={() => setViewingPage(doc)}
      className="group flex items-center gap-2 px-2.5 py-1.5 rounded-lg
                 bg-bg-elevated border border-border hover:border-primary/40
                 hover:bg-primary-muted transition-all duration-150"
      title={`View ${doc.document_name}, page ${doc.page}`}
    >
      {/* Small preview thumbnail */}
      <div className="w-8 h-10 rounded overflow-hidden bg-bg-card border border-border/60
                      shrink-0 relative">
        <img
          src={imgUrl}
          alt={`Page ${doc.page}`}
          className="w-full h-full object-cover object-top"
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = 'none';
          }}
        />
        <div className="absolute inset-0 flex items-center justify-center
                        bg-bg-card group-hover:bg-transparent transition-colors">
          <FileImage className="w-3 h-3 text-txt-muted group-hover:opacity-0 transition-opacity" />
        </div>
      </div>
      <div className="text-left min-w-0">
        <p className="text-xs font-medium text-txt-secondary truncate max-w-[120px]">
          {doc.document_name}
        </p>
        <p className="text-xs text-txt-muted">Page {doc.page}</p>
      </div>
    </button>
  );
}

interface Props {
  interaction: Interaction;
}

export default function MessageItem({ interaction }: Props) {
  return (
    <div className="space-y-4 py-3">
      {/* User message */}
      <div className="flex justify-end">
        <div className="flex items-end gap-2.5 max-w-[75%]">
          <div className="rounded-2xl rounded-br-sm px-4 py-3
                          bg-gradient-to-br from-[#5B21B6] to-[#4C1D95]
                          border border-primary/20 shadow-glow-sm">
            <p className="text-[0.95rem] text-white leading-relaxed whitespace-pre-wrap">
              {interaction.user}
            </p>
          </div>
          <div className="w-8 h-8 rounded-full bg-bg-card border border-border
                          flex items-center justify-center shrink-0">
            <User className="w-4 h-4 text-txt-muted" />
          </div>
        </div>
      </div>

      {/* Assistant message */}
      <div className="flex justify-start">
        <div className="flex items-start gap-2.5 max-w-[90%]">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-primary-dark
                          flex items-center justify-center shrink-0 mt-0.5 shadow-glow-sm">
            <BookOpen className="w-4 h-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="rounded-2xl rounded-tl-sm px-5 py-4
                            bg-bg-elevated border border-border
                            shadow-card">
              <div className="prose-content">
                <ReactMarkdown
                  remarkPlugins={[remarkMath, remarkGfm]}
                  rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }], rehypeHighlight]}
                  components={markdownComponents}
                >
                  {normalizeMath(interaction.assistant)}
                </ReactMarkdown>
              </div>

              {/* Document references */}
              {interaction.documents && interaction.documents.length > 0 && (
                <div className="mt-4 pt-3 border-t border-border/60">
                  <p className="text-xs text-txt-muted mb-2 font-medium uppercase tracking-wide">
                    Referenced pages
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {interaction.documents
                      .filter((doc, i, arr) =>
                        arr.findIndex(d => d.document_name === doc.document_name && d.page === doc.page) === i
                      )
                      .map((doc, i) => (
                      <PageThumb key={i} doc={doc} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
