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
        ALLOWED_ATTR: ['href', 'title', 'class'],
        ALLOW_DATA_ATTR: false,
    });
}

/**
 * Sanitize Markdown content by converting to HTML and sanitizing.
 * 
 * Note: This is a simple implementation. For full Markdown support,
 * integrate a Markdown parser (e.g., marked, remark) before sanitizing.
 * 
 * @param markdown - Markdown string (may contain unsafe HTML)
 * @returns Sanitized HTML string
 */
export function sanitizeMarkdown(markdown: string): string {
    if (!markdown || typeof markdown !== 'string') {
        return '';
    }

    // For now, treat as HTML and sanitize
    // TODO: Integrate a Markdown parser if needed
    return sanitizeHTML(markdown);
}

/**
 * Sanitize plain text by escaping HTML entities.
 * 
 * @param text - Plain text that may contain HTML-like characters
 * @returns Escaped text safe for rendering in HTML
 */
export function sanitizeText(text: string): string {
    if (!text || typeof text !== 'string') {
        return '';
    }

    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
