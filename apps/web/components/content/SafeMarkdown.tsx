"use client";

import { useMemo, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import type { Root } from "hast";
import type { Element, Text as HText } from "hast";

const SANITIZE_SCHEMA = {
  tagNames: [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "ul", "ol", "li",
    "blockquote",
    "pre", "code",
    "em", "strong", "b", "i", "u", "s", "del", "mark",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "sup", "sub",
    "dl", "dt", "dd",
  ],
  attributes: {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "code": ["className"],
    "pre": [],
    "td": ["colSpan", "rowSpan"],
    "th": ["colSpan", "rowSpan", "scope"],
    "*": ["className"],
  },
  protocols: {
    "href": ["http", "https", "mailto"],
    "src": ["http", "https", "data"],
  },
  strip: ["script", "style", "iframe", "object", "embed", "form", "input", "textarea", "select", "button"],
} as const;

const URL_BLACKLIST = /javascript:|data:(?!image\/)|vbscript:|blob:/i;

function isSafeUrl(url: string): boolean {
  const trimmed = url.trim();
  if (URL_BLACKLIST.test(trimmed)) return false;
  if (trimmed.startsWith("//")) return false;
  return true;
}

function sanitizeTree(node: Root): Root {
  function walk(n: Element | HText): Element | HText | null {
    if ("children" in n) {
      const filtered = n.children
        .map((c) => walk(c))
        .filter((c): c is Element | HText => c !== null);
      return { ...n, children: filtered } as Element;
    }
    return n;
  }

  for (let i = node.children.length - 1; i >= 0; i--) {
    const result = walk(node.children[i] as Element);
    if (result === null) {
      node.children.splice(i, 1);
    } else {
      node.children[i] = result as Element;
    }
  }

  for (const child of node.children) {
    if ("tagName" in child) {
      if (child.tagName === "a") {
        const href = child.properties?.href;
        if (typeof href === "string" && !isSafeUrl(href)) {
          child.tagName = "span";
          child.properties = {};
        }
        if (child.properties?.target === "_blank") {
          child.properties.rel = "noopener noreferrer";
        }
      }
    }
  }

  return node;
}

interface SafeMarkdownProps {
  content: string;
  className?: string;
  /** Allow inline HTML in markdown. Default: false */
  allowHtml?: boolean;
  /** Additional rehype plugins */
  rehypePlugins?: unknown[];
  /** Additional remark plugins */
  remarkPlugins?: unknown[];
}

export function SafeMarkdown({
  content,
  className,
  allowHtml = false,
  rehypePlugins = [],
  remarkPlugins = [],
}: SafeMarkdownProps) {
  const safeContent = useMemo(() => {
    if (!content) return "";
    return content
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
      .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, "")
      .replace(/javascript:/gi, "")
      .replace(/on\w+\s*=\s*["'][^"']*["']/gi, "");
  }, [content]);

  const plugins = useMemo(
    () => [
      remarkGfm,
      ...remarkPlugins,
      [rehypeSanitize, SANITIZE_SCHEMA],
      ...rehypePlugins,
    ],
    [remarkPlugins, rehypePlugins]
  );

  return (
    <div className={`prose prose-sm dark:prose-invert max-w-none ${className ?? ""}`}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins.length > 0 ? [remarkGfm, ...remarkPlugins] : [remarkGfm]}
        rehypePlugins={[
          [rehypeSanitize, SANITIZE_SCHEMA],
          ...rehypePlugins,
        ]}
      >
        {safeContent}
      </ReactMarkdown>
    </div>
  );
}

export default SafeMarkdown;
