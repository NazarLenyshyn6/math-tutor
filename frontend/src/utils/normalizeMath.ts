/**
 * Normalize LLM math output so remark-math / KaTeX can render it.
 *
 * Handles:
 *  - \[...\]                → $$...$$   (display)
 *  - \(...\)                → $...$     (inline)
 *  - **...\begin{}...\end{}...**  → strip ** wrappers before wrapping
 *  - bare \begin{}...\end{} → $$...$$   (display, pre/post included)
 *  - lone \ row-break fix inside matrices ("\ " → "\\")
 *  - headings missing a leading newline (only when preceded by non-# chars)
 */
export function normalizeMath(text: string): string {
  // ── 1. \[...\] → $$...$$ ─────────────────────────────────────────────────
  text = text.replace(/\\\[([\s\S]*?)\\\]/g, (_, inner) => `\n$$\n${inner}\n$$\n`);

  // ── 2. \(...\) → $...$ ───────────────────────────────────────────────────
  text = text.replace(/\\\(([\s\S]*?)\\\)/g, (_, inner) => `$${inner}$`);

  // ── 3. Ensure markdown headings start on their own line ───────────────────
  // Only insert \n when preceded by a NON-hash, NON-newline character
  // (avoids breaking "## heading" into "# \n# heading")
  text = text.replace(/([^\n#])(#{1,6} )/g, '$1\n$2');

  // ── 4. Bare \begin{env}...\end{env} → $$...$$ ────────────────────────────
  // Stash already-valid math so we don't double-wrap it.
  const stash: string[] = [];
  const mark = (s: string) => { stash.push(s); return `\x02${stash.length - 1}\x03`; };
  const restore = (s: string) => s.replace(/\x02(\d+)\x03/g, (_, i) => stash[+i]);

  text = text.replace(/\$\$[\s\S]*?\$\$/g, mark);           // stash $$...$$
  text = text.replace(/\$[^\n$]+\$/g, mark);                // stash $...$

  // Strip ** bold markers that wrap math environments — LLMs sometimes output
  // **A + B = \begin{bmatrix}...\end{bmatrix}**  which breaks KaTeX.
  // [^*]*? matches any non-asterisk chars (text before/after the environment).
  text = text.replace(
    /\*\*([^*]*?\\begin\{[^}]+\}[\s\S]*?\\end\{[^}]+\}[^*]*?)\*\*/g,
    '$1',
  );

  // Wrap bare \begin{env}...\end{env} — pre/post are included in the $$ block
  // so chained expressions like  = \begin{...}...\end{...}  in post also render.
  text = text.replace(
    /([^\n]*?)\\begin\{([^}]+)\}([\s\S]*?)\\end\{[^}]+\}([^\n]*)/g,
    (_, pre, env, inner, post) => {
      // Fix "\ " (lone backslash used as row-break) → "\\"
      const fixed = inner.replace(/\\(?![\\a-zA-Z{}\[\](])/g, '\\\\');
      // Defensively strip any ** that reached the boundary (e.g. pre ends with **)
      const cleanPre = pre.replace(/\*\*\s*$/, '');
      const cleanPost = post.replace(/^\s*\*\*/, '');
      const body = `${cleanPre}\\begin{${env}}${fixed}\\end{${env}}${cleanPost}`;
      return `\n$$\n${body}\n$$\n`;
    },
  );

  return restore(text);
}
