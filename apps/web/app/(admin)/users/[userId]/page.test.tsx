import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminUserDetailPage from "./page";

const mockFetchWithAuth = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ userId: "user-123" }),
}));

vi.mock("@/lib/auth", () => ({
  fetchWithAuth: (...args: unknown[]) => mockFetchWithAuth(...args),
}));

function response(payload: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => payload,
  } as Response;
}

const summaryPayload = {
  user: {
    id: "user-123",
    email: "user@example.com",
    display_name: null,
    plan: "pro", // intentionally stale legacy marker
    created_at: "2026-08-01T00:00:00Z",
    is_active: true,
  },
  quota: {
    tokens_used_today: 0,
    daily_token_limit: 1,
    token_usage_pct: 0,
    exports_used_today: 0,
    daily_export_limit: 1,
    export_usage_pct: 0,
  },
  recent_debates: [],
  feedback_summary: { total: 0, helpful: 0, not_helpful: 0 },
  recent_errors: [],
};

const freeDetail = {
  user: {
    id: "user-123",
    email: "user@example.com",
    display_name: null,
    plan: "pro",
    created_at: "2026-08-01T00:00:00Z",
    is_active: true,
  },
  plan: {
    slug: "free",
    name: "Free",
    price_monthly: 0,
    currency: "USD",
    is_default_free: true,
  },
  subscriptions: [],
};

const freeQuota = {
  users: [
    {
      user_id: "user-123",
      email: "user@example.com",
      plan: "free",
      legacy_plan_marker: "pro",
      tokens_used_today: 10,
      daily_token_limit: 100000,
      token_usage_pct: 0.01,
      exports_used_today: 0,
      daily_export_limit: 5,
      export_usage_pct: 0,
      created_at: "2026-08-01T00:00:00Z",
    },
  ],
};

function mockInitialLoad() {
  mockFetchWithAuth
    .mockResolvedValueOnce(response(summaryPayload))
    .mockResolvedValueOnce(response(freeDetail))
    .mockResolvedValueOnce(response(freeQuota))
    .mockResolvedValueOnce(response({ notes: [] }));
}

describe("AdminUserDetailPage canonical entitlement controls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows the effective Free plan instead of a stale legacy Pro marker", async () => {
    mockInitialLoad();
    render(<AdminUserDetailPage />);

    expect(await screen.findByText("Effective Plan")).toBeInTheDocument();
    expect(screen.getByText("free")).toBeInTheDocument();
    expect(screen.getByText(/Legacy marker: pro/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Grant Pro for 30 days" })).toBeInTheDocument();
  });

  it("grants Pro through the canonical manual-entitlement endpoint", async () => {
    mockInitialLoad();
    render(<AdminUserDetailPage />);

    const button = await screen.findByRole("button", { name: "Grant Pro for 30 days" });

    mockFetchWithAuth.mockResolvedValueOnce(
      response({ entitlement_updated: true, plan: "pro", source: "admin_manual_grant" }),
    );
    // Refetch after mutation.
    mockInitialLoad();

    fireEvent.click(button);

    await waitFor(() => {
      expect(mockFetchWithAuth).toHaveBeenCalledWith(
        "/admin/users/user-123/entitlement",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    const grantCall = mockFetchWithAuth.mock.calls.find(
      ([path, init]) => path === "/admin/users/user-123/entitlement" && init?.method === "POST",
    );
    expect(grantCall).toBeTruthy();
    const body = JSON.parse(grantCall?.[1]?.body as string);
    expect(body.plan).toBe("pro");
    expect(body.reason).toBe("Admin console 30-day Pro access grant");
    expect(new Date(body.expires_at).getTime()).toBeGreaterThan(Date.now());
  });
});
