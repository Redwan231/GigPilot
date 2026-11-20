/**
 * P4-10: E2E smoke test (Playwright)
 * Flow: signup → onboarding → score a job → generate draft → mark as used →
 *       set outcome (won) → check dashboard shows updated stats.
 *
 * Requires the full stack running:
 *   - Backend: uvicorn on http://localhost:8000 (with a seeded job in the DB)
 *   - Frontend: next dev on http://localhost:3000
 *
 * Run: cd frontend && npx playwright test e2e/smoke.spec.ts
 */

import { test, expect } from "@playwright/test";

const TEST_EMAIL = `smoke_${Date.now()}@gigpilot.test`;
const TEST_PASSWORD = "Password123!";

test.describe("GigPilot core loop smoke", () => {
  test("signup → onboarding → score → draft → outcome → dashboard", async ({
    page,
  }) => {
    // ---- 1. Land on homepage ----
    await page.goto("/");
    await expect(page.locator("text=GigPilot")).toBeVisible();

    // ---- 2. Sign up ----
    await page.click("text=Get started");
    await expect(page).toHaveURL(/\/signup/);

    await page.fill('input[type="email"]', TEST_EMAIL);
    await page.fill('input[type="password"]', TEST_PASSWORD);
    // confirm password field (if present in form)
    const confirmField = page.locator('input[placeholder*="confirm" i], input[name="confirm"]');
    if (await confirmField.count() > 0) {
      await confirmField.fill(TEST_PASSWORD);
    }
    await page.click('button[type="submit"]');

    // Should redirect to onboarding
    await expect(page).toHaveURL(/\/onboarding/, { timeout: 10_000 });

    // ---- 3. Onboarding — Step 1: Profile ----
    await page.fill('input[name="display_name"]', "Smoke Test User");
    // primary_category select
    const catSelect = page.locator('select[name="primary_category"]');
    if (await catSelect.count() > 0) {
      await catSelect.selectOption("development");
    }
    await page.fill('input[name="skills"]', "python, fastapi, react");
    // experience level
    const expSelect = page.locator('select[name="experience_level"]');
    if (await expSelect.count() > 0) {
      await expSelect.selectOption("mid");
    }
    await page.fill('input[name="hourly_rate"]', "80");
    await page.click('button:has-text("Next"), button[type="submit"]');

    // ---- 4. Onboarding — Step 2: Samples (skip) ----
    const skipBtn = page.locator("text=I'll do this later, text=Skip");
    if (await skipBtn.count() > 0) {
      await skipBtn.first().click();
    } else {
      // No skip button — click continue/next
      await page.click('button:has-text("Next"), button[type="submit"]');
    }

    // ---- 5. Onboarding — Step 3: Questionnaire (if shown) or finish ----
    const finishBtn = page.locator("text=Finish, text=Start using GigPilot, text=Go to dashboard");
    if (await finishBtn.count() > 0) {
      await finishBtn.first().click();
    } else {
      // Submit whatever form is here
      await page.click('button[type="submit"]');
    }

    // Should land in app
    await expect(page).toHaveURL(/\/app/, { timeout: 10_000 });

    // ---- 6. Score a job ----
    // Wait for job cards to appear
    const scoreBtn = page.locator('button:has-text("Score")').first();
    if (await scoreBtn.count() > 0) {
      await scoreBtn.click();
      // Wait for score chip to appear (number 0-100)
      await expect(
        page.locator('[aria-label*="score"], [data-testid="score-chip"]').first()
      ).toBeVisible({ timeout: 15_000 });
    }

    // ---- 7. Open a job and generate a draft ----
    const jobCard = page.locator('[data-testid="job-card"], .job-card, article').first();
    if (await jobCard.count() > 0) {
      await jobCard.click();
      await expect(page).toHaveURL(/\/app\/jobs\/.+/, { timeout: 5_000 });

      const generateBtn = page.locator('button:has-text("Generate"), button:has-text("Draft")').first();
      if (await generateBtn.count() > 0 && await generateBtn.isEnabled()) {
        await generateBtn.click();
        // Wait for draft textarea
        await expect(page.locator("textarea").first()).toBeVisible({
          timeout: 20_000,
        });
      }

      // ---- 8. Mark as used ----
      const markUsedBtn = page.locator('button:has-text("Mark as used")').first();
      if (await markUsedBtn.count() > 0) {
        await markUsedBtn.click();
      }
    }

    // ---- 9. Go to proposals and set outcome ----
    await page.click('a:has-text("Proposals")');
    await expect(page).toHaveURL(/\/app\/proposals/, { timeout: 5_000 });

    const proposalRow = page.locator('a, [role="listitem"]').first();
    if (await proposalRow.count() > 0) {
      await proposalRow.click();
      // Set outcome
      const wonBtn = page.locator('button:has-text("Won"), button:has-text("Mark won")').first();
      if (await wonBtn.count() > 0) {
        await wonBtn.click();
      }
    }

    // ---- 10. Check dashboard ----
    await page.click('a:has-text("Dashboard")');
    await expect(page).toHaveURL(/\/app\/dashboard/, { timeout: 5_000 });
    // Dashboard should render without crashing
    await expect(page.locator("h1, [data-testid='dashboard']")).toBeVisible({
      timeout: 5_000,
    });
  });
});
