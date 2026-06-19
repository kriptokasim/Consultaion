import { test, expect } from "@playwright/test";

test.describe("Landing Page", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/");
    });

    test("should display the navbar with logo and navigation", async ({ page }) => {
        // Check logo is visible
        await expect(page.locator('a[href="/"]').first()).toBeVisible();
        await expect(page.getByText("Consultaion")).toBeVisible();

        // Check navigation links
        await expect(page.getByRole("link", { name: /Pricing/i })).toBeVisible();
        await expect(page.getByRole("link", { name: /Leaderboard/i })).toBeVisible();
        await expect(page.getByRole("link", { name: /Models/i })).toBeVisible();
    });

    test("should display hero section with CTA", async ({ page }) => {
        // Check hero title is present
        await expect(page.getByRole("heading", { name: /Wisdom Through/i })).toBeVisible();
        await expect(page.getByRole("heading", { name: /Multi-Agent Debate/i })).toBeVisible();

        // Check tagline (who it's for)
        await expect(page.getByText(/For strategy, research, and decision teams/i)).toBeVisible();

        // Check primary CTA exists
        const primaryCta = page.getByRole("button", { name: /Start a Consultaion debate/i });
        await expect(primaryCta).toBeVisible();
    });

    test("should display 'How it Works' section with 4 steps", async ({ page }) => {
        // Check section title
        await expect(page.getByRole("heading", { name: /How a debate works/i })).toBeVisible();

        // Check all 4 steps are visible
        await expect(page.getByText(/Ask your question/i)).toBeVisible();
        await expect(page.getByText(/Agents debate in rounds/i)).toBeVisible();
        await expect(page.getByText(/Judges score arguments/i)).toBeVisible();
        await expect(page.getByText(/Champion answer delivered/i)).toBeVisible();

        // Check step numbers are visible
        await expect(page.locator("text=1").first()).toBeVisible();
        await expect(page.locator("text=2").nth(0)).toBeVisible();
        await expect(page.locator("text=3").nth(0)).toBeVisible();
        await expect(page.locator("text=4").nth(0)).toBeVisible();
    });

    test("should display demo CTA", async ({ page }) => {
        await expect(page.getByRole("link", { name: /Try a sample debate/i })).toBeVisible();
        await expect(page.getByText(/No sign-up required/i)).toBeVisible();
    });

    test("should display feature cards", async ({ page }) => {
        await expect(page.getByText(/Multi-Agent Debate/i).first()).toBeVisible();
        await expect(page.getByText(/Expert Judging/i)).toBeVisible();
        await expect(page.getByText(/Synthesized Wisdom/i)).toBeVisible();
    });

    test("should display multi-LLM section with benefits", async ({ page }) => {
        // Scroll to LLM section
        await page.locator("text=Multi-LLM Chamber").scrollIntoViewIfNeeded();

        // Check section is visible
        await expect(page.getByText(/Multi-LLM Chamber/i)).toBeVisible();
        await expect(page.getByText(/Choose models that work together/i)).toBeVisible();

        // Check benefit bullets
        await expect(page.getByText(/Avoid single-model blind spots/i)).toBeVisible();
        await expect(page.getByText(/Blend reasoning styles and perspectives/i)).toBeVisible();
        await expect(page.getByText(/Automatic routing/i)).toBeVisible();
    });

    test("should display footer with Terms and Privacy links", async ({ page }) => {
        // Scroll to footer
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

        // Check footer links
        await expect(page.getByRole("link", { name: "Terms" })).toBeVisible();
        await expect(page.getByRole("link", { name: "Privacy" })).toBeVisible();
    });

    test("Terms and Privacy links should be clickable", async ({ page }) => {
        // Click Terms link
        const termsLink = page.getByRole("link", { name: "Terms" }).last();
        await termsLink.scrollIntoViewIfNeeded();
        await expect(termsLink).toBeVisible();
        await termsLink.click();

        // Verify navigation to Terms page
        await expect(page).toHaveURL(/\/terms/);
        await expect(page.getByRole("heading", { name: /Terms of Service/i })).toBeVisible();

        // Go back
        await page.goBack();

        // Click Privacy link
        const privacyLink = page.getByRole("link", { name: "Privacy" }).last();
        await privacyLink.scrollIntoViewIfNeeded();
        await expect(privacyLink).toBeVisible();
        await privacyLink.click();

        // Verify navigation to Privacy page
        await expect(page).toHaveURL(/\/privacy/);
        await expect(page.getByRole("heading", { name: /Privacy Policy/i })).toBeVisible();
    });

    test("Contact link should work", async ({ page }) => {
        const contactLink = page.getByRole("link", { name: "Contact" }).last();
        await contactLink.scrollIntoViewIfNeeded();
        await expect(contactLink).toBeVisible();
        await contactLink.click();

        // Verify navigation to Contact page
        await expect(page).toHaveURL(/\/contact/);
        await expect(page.getByRole("heading", { name: /Contact Us/i })).toBeVisible();
    });

    test("Language switcher should be visible", async ({ page }) => {
        // Check language switcher exists
        await expect(page.getByRole("button", { name: "TR" }).or(page.getByRole("button", { name: "EN" }))).toBeVisible();
    });

    test("Navbar should become sticky on scroll", async ({ page }) => {
        // Get navbar initial state
        const navbar = page.locator("nav").first();
        await expect(navbar).toBeVisible();

        // Scroll down
        await page.evaluate(() => window.scrollTo(0, 100));

        // Wait for transition
        await page.waitForTimeout(500);

        // Navbar should still be visible (sticky)
        await expect(navbar).toBeVisible();
    });
});
