import { describe, test, expect } from "vitest";
import { sanitizeMarkdown } from "./sanitize";

describe("sanitizeMarkdown edge cases", () => {
    test("handles three asterisks (***) for bold italic and horizontal rules", () => {
        // Line-level horizontal rule *** (HTML5 standard <hr> is emitted by DOMPurify)
        expect(sanitizeMarkdown("***")).toBe("<hr>");
        expect(sanitizeMarkdown("  ***  ")).toBe("<hr>");
        
        // Inline bold italic
        expect(sanitizeMarkdown("***bold italic***")).toBe("<p><strong><em>bold italic</em></strong></p>");
        expect(sanitizeMarkdown("___bold italic___")).toBe("<p><strong><em>bold italic</em></strong></p>");
    });

    test("handles three hyphens (---) and underscores (___) for horizontal rules", () => {
        expect(sanitizeMarkdown("---")).toBe("<hr>");
        expect(sanitizeMarkdown("___")).toBe("<hr>");
    });

    test("strips script tags and executable content", () => {
        expect(sanitizeMarkdown("<script>alert('XSS')</script>Safe text"))
            .toBe("<p>Safe text</p>");
        expect(sanitizeMarkdown("Safe text <script src=\"http://malicious.com/payload.js\"></script>"))
            .toBe("<p>Safe text </p>");
    });

    test("strips inline event listeners like onclick", () => {
        // Since custom HTML is processed by line, DOMPurify cleans the tag and splits empty nodes
        const cleaned = sanitizeMarkdown('<div onclick="alert(1)" class="test">Hello</div>');
        expect(cleaned).toContain('class="test"');
        expect(cleaned).toContain('Hello');
        expect(cleaned).not.toContain('onclick');
        
        const cleanedA = sanitizeMarkdown('<a href="/home" onmouseover="malicious()">Home</a>');
        expect(cleanedA).toContain('href="/home"');
        expect(cleanedA).toContain('Home');
        expect(cleanedA).not.toContain('onmouseover');
    });

    test("strips javascript protocol in links", () => {
        // HTML links
        expect(sanitizeMarkdown('<a href="javascript:alert(1)">Click Me</a>'))
            .toBe('<p><a>Click Me</a></p>');
        
        // Markdown links - verify DOMPurify completely strips the malicious href attribute
        const cleanedMarkdownLink = sanitizeMarkdown('[Click Me](javascript:alert(1))');
        expect(cleanedMarkdownLink).toContain('Click Me');
        expect(cleanedMarkdownLink).not.toContain('href');
        expect(cleanedMarkdownLink).not.toContain('javascript');
    });

    test("handles broken/unclosed markdown gracefully without crashing", () => {
        // Unclosed bold
        expect(sanitizeMarkdown("**unclosed bold")).toBe("<p>**unclosed bold</p>");
        
        // Unclosed italic
        expect(sanitizeMarkdown("*unclosed italic")).toBe("<p>*unclosed italic</p>");
        
        // Unclosed link
        expect(sanitizeMarkdown("[unclosed link")).toBe("<p>[unclosed link</p>");
        expect(sanitizeMarkdown("[unclosed link(http://example.com)")).toBe("<p>[unclosed link(http://example.com)</p>");
        
        // Partially matched elements
        expect(sanitizeMarkdown("`partial inline code")).toBe("<p>`partial inline code</p>");
        expect(sanitizeMarkdown("```javascript\ncode without closing")).toBe("<p>```javascript</p>\n<p>code without closing</p>");
    });
});
