"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { cn } from "@/lib/utils";
import { sanitizeMarkdown } from "@/lib/sanitize";

interface Props {
  text: string;
  isStreaming?: boolean;
  className?: string;
}

interface State {
  hasError: boolean;
}

class SafeMarkdownRenderer extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(_: Error): State {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("SafeMarkdownRenderer caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <div className="text-rose-400 font-mono text-sm">Error rendering content fallback: {this.props.text}</div>;
    }

    const html = sanitizeMarkdown(this.props.text);

    return (
      <div
        className={cn(
          "prose prose-sm dark:prose-invert max-w-none prose-headings:font-bold prose-headings:tracking-tight",
          "prose-p:leading-relaxed prose-pre:bg-slate-900 prose-pre:border prose-pre:border-white/10 prose-code:text-amber-500 prose-code:bg-slate-100 dark:prose-code:bg-slate-900 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:font-mono prose-code:text-xs",
          this.props.className
        )}
      >
        <div dangerouslySetInnerHTML={{ __html: html }} className="inline" />
        {this.props.isStreaming && (
          <span className="inline-block w-2 h-4 ml-1 bg-amber-500 animate-pulse rounded-sm align-middle" />
        )}
      </div>
    );
  }
}

export default function StreamingText({ text, isStreaming = false, className }: Props) {
  return <SafeMarkdownRenderer text={text} isStreaming={isStreaming} className={className} />;
}
