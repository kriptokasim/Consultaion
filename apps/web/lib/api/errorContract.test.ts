import { describe, it, expect } from "vitest";
import {
  normalizeApiError,
  isRetryable,
  shouldRedirectToLogin,
  getCorrelationId,
} from "./errorContract";

describe("normalizeApiError", () => {
  it("normalizes 401 to unauthorized", () => {
    const error = normalizeApiError({ status: 401, detail: "Not authenticated" }, 401);
    expect(error.kind).toBe("unauthorized");
    expect(error.httpStatus).toBe(401);
    expect(error.retryable).toBe(false);
  });

  it("normalizes 403 to forbidden", () => {
    const error = normalizeApiError({ status: 403, detail: "Insufficient permissions" }, 403);
    expect(error.kind).toBe("forbidden");
    expect(error.httpStatus).toBe(403);
  });

  it("normalizes 404 to not_found", () => {
    const error = normalizeApiError({ detail: "Not found" }, 404);
    expect(error.kind).toBe("not_found");
    expect(error.httpStatus).toBe(404);
  });

  it("normalizes 429 to rate_limited with retryable", () => {
    const error = normalizeApiError({ detail: "Rate limited" }, 429);
    expect(error.kind).toBe("rate_limited");
    expect(error.retryable).toBe(true);
  });

  it("normalizes 500 to server error", () => {
    const error = normalizeApiError({ detail: "Internal error" }, 500);
    expect(error.kind).toBe("server");
    expect(error.retryable).toBe(true);
  });

  it("preserves code, hint, and retryable from backend", () => {
    const error = normalizeApiError(
      {
        detail: "Quota exceeded",
        code: "QUOTA_EXCEEDED",
        hint: "Upgrade plan",
        retryable: false,
      },
      402
    );
    expect(error.code).toBe("QUOTA_EXCEEDED");
    expect(error.hint).toBe("Upgrade plan");
    expect(error.retryable).toBe(false);
  });

  it("preserves request_id and correlation_id", () => {
    const error = normalizeApiError(
      { detail: "Error", request_id: "req-123", correlation_id: "corr-456" },
      500
    );
    expect(error.requestId).toBe("req-123");
    expect(error.correlationId).toBe("corr-456");
  });

  it("handles network error", () => {
    const error = normalizeApiError(new TypeError("fetch failed"));
    expect(error.kind).toBe("network");
    expect(error.retryable).toBe(true);
  });

  it("handles AbortError as cancelled", () => {
    const abortError = new DOMException("Aborted", "AbortError");
    const error = normalizeApiError(abortError);
    expect(error.kind).toBe("cancelled");
    expect(error.retryable).toBe(false);
  });

  it("returns existing ClientError unchanged", () => {
    const existing = {
      kind: "forbidden" as const,
      message: "Denied",
      retryable: false,
      httpStatus: 403,
    };
    const result = normalizeApiError(existing);
    expect(result).toBe(existing);
  });
});

describe("isRetryable", () => {
  it("returns true for retryable errors", () => {
    expect(isRetryable(normalizeApiError({ detail: "Rate limited" }, 429))).toBe(true);
  });

  it("returns false for non-retryable errors", () => {
    expect(isRetryable(normalizeApiError({ detail: "Forbidden" }, 403))).toBe(false);
  });
});

describe("shouldRedirectToLogin", () => {
  it("returns true for 401", () => {
    expect(shouldRedirectToLogin(normalizeApiError({ detail: "Unauthorized" }, 401))).toBe(true);
  });

  it("returns false for 403", () => {
    expect(shouldRedirectToLogin(normalizeApiError({ detail: "Forbidden" }, 403))).toBe(false);
  });
});

describe("getCorrelationId", () => {
  it("prefers correlationId over requestId", () => {
    const error = normalizeApiError(
      { detail: "Error", request_id: "req-1", correlation_id: "corr-1" },
      500
    );
    expect(getCorrelationId(error)).toBe("corr-1");
  });

  it("falls back to requestId", () => {
    const error = normalizeApiError(
      { detail: "Error", request_id: "req-1" },
      500
    );
    expect(getCorrelationId(error)).toBe("req-1");
  });

  it("returns undefined when neither present", () => {
    const error = normalizeApiError({ detail: "Error" }, 500);
    expect(getCorrelationId(error)).toBeUndefined();
  });
});
