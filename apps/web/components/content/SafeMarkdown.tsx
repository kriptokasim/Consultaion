"use client";

import { useMemo } from "react";
import { sanitizeMarkdown } from "@/lib/sanitize";

interface SafeMarkdownProps {
  content: string;
  className?: string;
}

export function SafeMarkdown({ content, className }: SafeMarkdownProps) {
  const sanitizedHtml = useMemo(() => {
    return sanitizeMarkdown(content ?? "");
  }, [content]);

  return (
    <div
      className={`prose prose-sm dark:prose-invert max-w-none ${className ?? ""}`}
      dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
    />
  );
}

export default SafeMarkdown;
