import React, { useState } from 'react';
import { LucideIcon } from '@/components/LucideIcon';

interface MarkdownMessageProps {
  content: string;
  isUser?: boolean;
  className?: string;
}

/**
 * Custom High-Performance Zero-Dependency Markdown Renderer for Chat Messages.
 * Eliminates raw markdown syntax artifacts (like '**' for bold) and renders
 * clean HTML typography: real bold (<strong>), headers, bullet lists, code blocks,
 * and inline badges.
 */
export const MarkdownMessage: React.FC<MarkdownMessageProps> = ({
  content,
  isUser = false,
  className = '',
}) => {
  if (!content) return null;

  // Split into code block chunks and regular text chunks
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  const chunks: Array<{ type: 'code' | 'text'; lang?: string; text: string }> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      chunks.push({
        type: 'text',
        text: content.slice(lastIndex, match.index),
      });
    }
    chunks.push({
      type: 'code',
      lang: match[1] || 'text',
      text: match[2],
    });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    chunks.push({
      type: 'text',
      text: content.slice(lastIndex),
    });
  }

  return (
    <div className={`space-y-2 text-xs sm:text-[13px] leading-relaxed break-words font-sans ${className}`}>
      {chunks.map((chunk, idx) => {
        if (chunk.type === 'code') {
          return <CodeBlock key={idx} code={chunk.text} lang={chunk.lang} />;
        }
        return <TextBlock key={idx} text={chunk.text} isUser={isUser} />;
      })}
    </div>
  );
};

// ==============================================================================
// CODE BLOCK COMPONENT WITH COPY BUTTON
// ==============================================================================

const CodeBlock: React.FC<{ code: string; lang?: string }> = ({ code, lang }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="my-2.5 rounded-xl bg-obsidian-950 border border-obsidian-800 overflow-hidden shadow-inner font-mono text-[11px]">
      <div className="flex items-center justify-between px-3 py-1.5 bg-obsidian-900/90 border-b border-obsidian-800 text-[10px] text-slate-400">
        <span className="font-semibold uppercase text-cyan-400">{lang || 'CODE'}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-obsidian-800 hover:text-slate-200 transition text-slate-400"
          title="Salin kode"
        >
          <LucideIcon name={copied ? 'check' : 'copy'} className="w-3 h-3 text-emerald-400" />
          <span>{copied ? 'Tersalin!' : 'Salin'}</span>
        </button>
      </div>
      <pre className="p-3 overflow-x-auto text-emerald-300 leading-normal">
        <code>{code.trim()}</code>
      </pre>
    </div>
  );
};

// ==============================================================================
// TEXT BLOCK RENDERER (LINES, LISTS, HEADERS, PARAGRAPHS)
// ==============================================================================

const TextBlock: React.FC<{ text: string; isUser: boolean }> = ({ text, isUser }) => {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // 1. Empty line
    if (!trimmed) {
      elements.push(<div key={`empty-${i}`} className="h-1.5" />);
      i++;
      continue;
    }

    // 2. Horizontal divider
    if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
      elements.push(
        <hr key={`hr-${i}`} className="my-3 border-obsidian-750 border-t" />
      );
      i++;
      continue;
    }

    // 3. Headers (H1, H2, H3)
    if (trimmed.startsWith('### ')) {
      elements.push(
        <h3
          key={`h3-${i}`}
          className={`text-sm font-bold mt-2.5 mb-1.5 flex items-center gap-1.5 ${
            isUser ? 'text-white font-extrabold' : 'text-emerald-400'
          }`}
        >
          {renderInlineFormatting(trimmed.slice(4), isUser)}
        </h3>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith('## ')) {
      elements.push(
        <h2
          key={`h2-${i}`}
          className={`text-base font-bold mt-3 mb-1.5 ${
            isUser ? 'text-white' : 'text-emerald-300'
          }`}
        >
          {renderInlineFormatting(trimmed.slice(3), isUser)}
        </h2>
      );
      i++;
      continue;
    }

    if (trimmed.startsWith('# ')) {
      elements.push(
        <h1
          key={`h1-${i}`}
          className={`text-lg font-bold mt-3.5 mb-2 ${
            isUser ? 'text-white' : 'text-emerald-200'
          }`}
        >
          {renderInlineFormatting(trimmed.slice(2), isUser)}
        </h1>
      );
      i++;
      continue;
    }

    // 4. Blockquotes
    if (trimmed.startsWith('> ')) {
      elements.push(
        <blockquote
          key={`quote-${i}`}
          className="border-l-2 border-emerald-500 pl-3 py-1 my-1.5 bg-obsidian-950/40 rounded-r text-slate-300 italic"
        >
          {renderInlineFormatting(trimmed.slice(2), isUser)}
        </blockquote>
      );
      i++;
      continue;
    }

    // 5. Unordered List Items (- or *)
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      elements.push(
        <div key={`li-${i}`} className="flex items-start gap-2 my-1 pl-1">
          <span className="text-emerald-400 font-bold shrink-0 mt-0.5">•</span>
          <div className="flex-1 leading-relaxed">
            {renderInlineFormatting(trimmed.slice(2), isUser)}
          </div>
        </div>
      );
      i++;
      continue;
    }

    // 6. Ordered List Items (1. , 2. , etc.)
    const orderedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (orderedMatch) {
      elements.push(
        <div key={`oli-${i}`} className="flex items-start gap-2 my-1 pl-1">
          <span className="text-cyan-400 font-bold shrink-0 font-mono text-[11px] mt-0.5">
            {orderedMatch[1]}.
          </span>
          <div className="flex-1 leading-relaxed">
            {renderInlineFormatting(orderedMatch[2], isUser)}
          </div>
        </div>
      );
      i++;
      continue;
    }

    // 7. Regular paragraph line
    elements.push(
      <p key={`p-${i}`} className="leading-relaxed my-0.5">
        {renderInlineFormatting(rawLine, isUser)}
      </p>
    );
    i++;
  }

  return <>{elements}</>;
};

// ==============================================================================
// INLINE FORMATTING PARSER (ELIMINATES '**' AND RENDERS <strong>)
// ==============================================================================

/**
 * Parses inline formatting tags:
 * - **bold text** -> <strong>bold text</strong> (Asterisks completely removed!)
 * - `code` -> <code>code</code>
 * - [label](url) -> <a>label</a>
 * - *italic* -> <em>italic</em>
 */
function renderInlineFormatting(text: string, isUser: boolean): React.ReactNode {
  if (!text) return null;

  // Regex tokens:
  // 1. `inline code`
  // 2. **bold text**
  // 3. [link text](url)
  // 4. *italic text*
  const tokenRegex = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\)|\*[^*]+\*)/g;
  const parts = text.split(tokenRegex);

  return parts.map((part, index) => {
    if (!part) return null;

    // A. Inline Code: `...`
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      const codeContent = part.slice(1, -1);
      return (
        <code
          key={index}
          className="px-1.5 py-0.5 mx-0.5 rounded bg-obsidian-950 border border-obsidian-800 text-cyan-300 font-mono text-[11px]"
        >
          {codeContent}
        </code>
      );
    }

    // B. Bold text: **...** -> RENDER AS REAL BOLD, REMOVE ASTERISKS!
    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      const boldContent = part.slice(2, -2);
      return (
        <strong
          key={index}
          className={`font-bold tracking-tight ${
            isUser ? 'text-white' : 'text-slate-100 font-extrabold'
          }`}
        >
          {boldContent}
        </strong>
      );
    }

    // C. Markdown Link: [label](url)
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      const [, label, url] = linkMatch;
      return (
        <a
          key={index}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-emerald-400 hover:text-emerald-300 underline font-medium"
        >
          {label}
        </a>
      );
    }

    // D. Italic text: *...*
    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      const italicContent = part.slice(1, -1);
      return (
        <em key={index} className="italic text-slate-300">
          {italicContent}
        </em>
      );
    }

    // E. Plain text fallback: Clean up any stray dangling '**' if present
    const cleanedText = part.replace(/\*\*/g, '');
    return <span key={index}>{cleanedText}</span>;
  });
}
