import { describe, test, expect } from "vitest";
import { sanitizeMarkdown, sanitizeHTML } from "./sanitize";

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

describe("XSS regression tests", () => {
    test("strips <script> injection", () => {
        const result = sanitizeMarkdown('<script>alert(1)</script>');
        expect(result).not.toContain("<script>");
        expect(result).not.toContain("alert");
    });

    test("strips <img onerror> injection", () => {
        const result = sanitizeMarkdown('<img src=x onerror=alert(1)>');
        expect(result).not.toContain("onerror");
        expect(result).not.toContain("alert");
    });

    test("strips javascript: protocol in markdown links", () => {
        const result = sanitizeMarkdown('[click](javascript:alert(1))');
        expect(result).not.toContain("javascript:");
        expect(result).not.toContain("alert");
    });

    test("strips javascript: protocol in HTML links", () => {
        const result = sanitizeMarkdown('<a href="javascript:alert(1)">x</a>');
        expect(result).not.toContain("javascript:");
        expect(result).not.toContain("alert");
    });

    test("strips <svg onload> injection", () => {
        const result = sanitizeMarkdown('<svg onload=alert(1)></svg>');
        expect(result).not.toContain("<svg>");
        expect(result).not.toContain("onload");
        expect(result).not.toContain("alert");
    });

    test("strips data: URI scheme in links", () => {
        const result = sanitizeMarkdown('[data](data:text/html,<script>alert(1)</script>)');
        expect(result).not.toContain("data:");
        expect(result).not.toContain("<script>");
    });

    test("allows safe markdown formatting", () => {
        const result = sanitizeMarkdown("**bold** and *italic*");
        expect(result).toContain("<strong>bold</strong>");
        expect(result).toContain("<em>italic</em>");
    });

    test("allows safe links", () => {
        const result = sanitizeMarkdown('[click](https://example.com)');
        expect(result).toContain("https://example.com");
        expect(result).toContain("click");
    });

    test("allows code blocks", () => {
        const result = sanitizeMarkdown("`inline code`");
        expect(result).toContain("<code>inline code</code>");
    });

    test("sanitizeHTML strips malicious attributes directly", () => {
        const result = sanitizeHTML('<div onmouseover="alert(1)">hover</div>');
        expect(result).not.toContain("onmouseover");
        expect(result).toContain("hover");
    });
});
