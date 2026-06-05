/**
 * XSS sanitization utilities for LLM-generated content.
 * 
 * Patchset 36.0
 */

import DOMPurify from 'dompurify';

/**
 * Sanitize HTML content to prevent XSS attacks.
 * 
 * This function removes potentially dangerous HTML tags and attributes
 * while preserving safe formatting (bold, italic, links, etc.).
 * 
 * @param dirty - Potentially unsafe HTML string
 * @returns Sanitized HTML string safe for rendering
 * 
 * @example
 * ```ts
 * const userInput = '<script>alert("XSS")</script><p>Safe content</p>';
 * const safe = sanitizeHTML(userInput);
 * // Returns: '<p>Safe content</p>'
 * ```
 */
export function sanitizeHTML(dirty: string): string {
    if (!dirty || typeof dirty !== 'string') {
        return '';
    }

    return DOMPurify.sanitize(dirty, {
        ALLOWED_TAGS: [
            'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'a', 'span', 'div',
        ],
        ALLOWED_ATTR: ['href', 'title', 'class', 'target', 'rel'],
        ALLOW_DATA_ATTR: false,
    });
}

/**
 * Custom zero-dependency compiler converting markdown to safe HTML structure.
 */
function parseMarkdownToHTML(markdown: string): string {
    if (!markdown || typeof markdown !== 'string') {
        return '';
    }

    let html = markdown;

    // Handle code blocks (e.g. ```javascript ... ```)
    const codeBlockRegex = /```(\w*)\n([\s\S]*?)\n```/g;
    html = html.replace(codeBlockRegex, (match, lang, code) => {
        const escapedCode = code
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        return `<pre><code class="language-${lang}">${escapedCode}</code></pre>`;
    });

    // Handle inline code: `code`
    html = html.replace(/`([^`]+)`/g, (match, code) => {
        const escapedCode = code
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        return `<code>${escapedCode}</code>`;
    });

    const lines = html.split('\n');
    let inList = false;
    let listType: 'ul' | 'ol' | null = null;
    let inBlockquote = false;
    const processedLines: string[] = [];

    const closeListIfNeeded = () => {
        if (inList && listType) {
            processedLines.push(`</${listType}>`);
            inList = false;
            listType = null;
        }
    };

    const closeBlockquoteIfNeeded = () => {
        if (inBlockquote) {
            processedLines.push('</blockquote>');
            inBlockquote = false;
        }
    };

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        // 1. Blockquote
        if (trimmed.startsWith('>')) {
            closeListIfNeeded();
            if (!inBlockquote) {
                processedLines.push('<blockquote>');
                inBlockquote = true;
            }
            const quoteContent = trimmed.slice(1).replace(/^\s/, '');
            processedLines.push(`<p>${quoteContent}</p>`);
            continue;
        } else {
            closeBlockquoteIfNeeded();
        }

        // 2. Headings
        const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
        if (headingMatch) {
            closeListIfNeeded();
            const level = headingMatch[1].length;
            const content = headingMatch[2];
            processedLines.push(`<h${level}>${content}</h${level}>`);
            continue;
        }

        // 3. Unordered list items: * or - or +
        const ulMatch = trimmed.match(/^([\*\-\+])\s+(.+)$/);
        if (ulMatch) {
            if (!inList || listType !== 'ul') {
                closeListIfNeeded();
                processedLines.push('<ul>');
                inList = true;
                listType = 'ul';
            }
            processedLines.push(`<li>${ulMatch[2]}</li>`);
            continue;
        }

        // 4. Ordered list items: 1. or 2. etc
        const olMatch = trimmed.match(/^(\d+)\.\s+(.+)$/);
        if (olMatch) {
            if (!inList || listType !== 'ol') {
                closeListIfNeeded();
                processedLines.push('<ol>');
                inList = true;
                listType = 'ol';
            }
            processedLines.push(`<li>${olMatch[2]}</li>`);
            continue;
        }

        // 5. Blank line
        if (trimmed === '') {
            closeListIfNeeded();
            processedLines.push('');
            continue;
        }

        // 6. Regular paragraph line
        closeListIfNeeded();
        processedLines.push(`<p>${line}</p>`);
    }

    closeListIfNeeded();
    closeBlockquoteIfNeeded();

    html = processedLines.join('\n');

    // Bold: **text** or __text__
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');

    // Italics: *text* or _text_
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/_([^_]+)_/g, '<em>$1</em>');

    // Links: [text](url)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-amber-800 hover:text-amber-700 underline font-medium">$1</a>');

    // Remove empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, '');

    return html;
}

/**
 * Sanitize Markdown content by converting to HTML and sanitizing.
 * 
 * @param markdown - Markdown string (may contain unsafe HTML)
 * @returns Sanitized HTML string
 */
export function sanitizeMarkdown(markdown: string): string {
    if (!markdown || typeof markdown !== 'string') {
        return '';
    }

    const htmlContent = parseMarkdownToHTML(markdown);
    return sanitizeHTML(htmlContent);
}

/**
 * Sanitize plain text by escaping HTML entities (SSR compatible).
 * 
 * @param text - Plain text that may contain HTML-like characters
 * @returns Escaped text safe for rendering in HTML
 */
export function sanitizeText(text: string): string {
    if (!text || typeof text !== 'string') {
        return '';
    }

    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
}
