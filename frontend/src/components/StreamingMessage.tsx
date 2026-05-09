import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import type { Components } from 'react-markdown';
import { BookOpen } from 'lucide-react';
import { Loader2 } from 'lucide-react';
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
  p: ({ children }) => <p className="my-2 leading-relaxed text-[0.95rem]">{children}</p>,
  ul: ({ children }) => <ul className="my-2 pl-5 space-y-1 list-disc">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 pl-5 space-y-1 list-decimal">{children}</ol>,
  li: ({ children }) => <li className="text-[0.95rem] text-txt-secondary/90">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-txt-primary">{children}</strong>,
  em: ({ children }) => <em className="italic text-primary-light">{children}</em>,
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

interface Props {
  text: string;
}

export default function StreamingMessage({ text }: Props) {
  return (
    <div className="flex justify-start py-3">
      <div className="flex items-start gap-2.5 max-w-[90%]">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-primary-dark
                        flex items-center justify-center shrink-0 mt-0.5 shadow-glow-sm">
          <BookOpen className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="rounded-2xl rounded-tl-sm px-5 py-4
                          bg-bg-elevated border border-primary/20 shadow-glow-sm">
            {text ? (
              <div className="prose-content streaming-cursor">
                <ReactMarkdown
                  remarkPlugins={[remarkMath, remarkGfm]}
                  rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }], rehypeHighlight]}
                  components={markdownComponents}
                >
                  {normalizeMath(text)}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-txt-muted">
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                <span className="text-sm">Thinking…</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
