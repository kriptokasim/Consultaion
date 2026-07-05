/**
 * Patchset 148 E4: Canonical user-friendly error mapper.
 *
 * Consolidates error presentation logic from:
 *  - describeError / getFriendlyMessage (errorContract.ts)
 *  - normalizeError (errors.ts)
 *  - toUserMessage (apiClient.ts)
 *  - ad-hoc rate-limit strings
 *
 * Returns a structured UI-ready error object for all error scenarios.
 */

export interface UserFriendlyError {
  title: string;
  message: string;
  hint?: string;
  severity: "info" | "warning" | "error";
  retryable: boolean;
  retryAfterSeconds?: number;
  escalationHref?: string;
}

/**
 * Extract a body object from an unknown error, normalizing multiple shapes.
 */
function extractBody(error: unknown): Record<string, any> | null {
  if (!error || typeof error !== "object") return null;
  const obj = error as Record<string, unknown>;

  // ApiError / ApiClientError shape
  if ("body" in obj && typeof obj.body === "object" && obj.body !== null) {
    return obj.body as Record<string, any>;
  }

  // Direct detail/error shape
  if ("detail" in obj || "error" in obj) {
    return obj as Record<string, any>;
  }

  return null;
}

function extractStatus(error: unknown): number | undefined {
  if (!error || typeof error !== "object") return undefined;
  const obj = error as Record<string, unknown>;
  if (typeof obj.status === "number") return obj.status;
  if (typeof obj.httpStatus === "number") return obj.httpStatus;
  return undefined;
}

function extractCode(error: unknown): string | undefined {
  if (!error || typeof error !== "object") return undefined;
  const obj = error as Record<string, unknown>;
  if (typeof obj.code === "string") return obj.code;
  const body = extractBody(error);
  if (body) {
    if (typeof body.code === "string") return body.code;
    if (body.error && typeof body.error === "object" && typeof body.error.code === "string") {
      return body.error.code;
    }
  }
  return undefined;
}

function extractRetryAfter(error: unknown): number | undefined {
  const body = extractBody(error);
  if (!body) return undefined;
  if (typeof body.retry_after === "number") return body.retry_after;
  if (typeof body.reset_at === "string") {
    const resetMs = new Date(body.reset_at).getTime() - Date.now();
    if (resetMs > 0) return Math.ceil(resetMs / 1000);
  }
  if (body.error && typeof body.error === "object") {
    if (typeof body.error.retry_after === "number") return body.error.retry_after;
  }
  return undefined;
}

function extractMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  const body = extractBody(error);
  if (body) {
    if (typeof body.detail === "string") return body.detail;
    if (typeof body.message === "string") return body.message;
    if (body.error && typeof body.error === "object" && typeof body.error.message === "string") {
      return body.error.message;
    }
  }
  const obj = error as Record<string, unknown> | null;
  if (obj && typeof obj.message === "string") return obj.message;
  return "An unexpected error occurred.";
}

function extractHint(error: unknown): string | undefined {
  const body = extractBody(error);
  if (!body) return undefined;
  if (typeof body.hint === "string") return body.hint;
  if (body.error && typeof body.error === "object" && typeof body.error.hint === "string") {
    return body.error.hint;
  }
  return undefined;
}

/**
 * Convert any error into a user-friendly error object suitable for UI display.
 */
export function getUserFriendlyError(error: unknown): UserFriendlyError {
  const status = extractStatus(error);
  const code = extractCode(error);
  const message = extractMessage(error);
  const hint = extractHint(error);
  const retryAfter = extractRetryAfter(error);

  // ── Timeout ──
  if (
    (error instanceof Error && error.name === "TimeoutError") ||
    status === 408
  ) {
    return {
      title: "Request timed out",
      message: "The request took too long. Please try again.",
      severity: "warning",
      retryable: true,
    };
  }

  // ── Network error ──
  if (
    (error instanceof TypeError && error.message.includes("fetch")) ||
    (error instanceof Error && error.message.includes("NetworkError")) ||
    (status === 0 || status === undefined) && error instanceof Error
  ) {
    return {
      title: "Connection failed",
      message: "Could not reach the server. Check your connection and try again.",
      severity: "warning",
      retryable: true,
    };
  }

  // ── Abort ──
  if (error instanceof DOMException && error.name === "AbortError") {
    return {
      title: "Cancelled",
      message: "The request was cancelled.",
      severity: "info",
      retryable: false,
    };
  }

  // ── 401 Unauthorized ──
  if (status === 401) {
    return {
      title: "Session expired",
      message: "Your session has expired. Please sign in again.",
      severity: "warning",
      retryable: false,
    };
  }

  // ── 403 Forbidden ──
  if (status === 403) {
    if (code === "account_disabled") {
      return {
        title: "Account disabled",
        message: message || "Your account has been disabled.",
        severity: "error",
        retryable: false,
        escalationHref: "/support",
      };
    }
    return {
      title: "Access denied",
      message: "You do not have permission to perform this action.",
      hint,
      severity: "error",
      retryable: false,
    };
  }

  // ── 429 Rate limited ──
  if (status === 429) {
    const seconds = retryAfter ?? 30;
    return {
      title: "Rate limited",
      message: `Too many requests — try again in ${seconds}s.`,
      hint: hint || message,
      severity: "warning",
      retryable: true,
      retryAfterSeconds: seconds,
    };
  }

  // ── 502/503 Provider unavailable ──
  if (status === 502 || status === 503) {
    return {
      title: "Service unavailable",
      message: "The service is temporarily unavailable. Please try again shortly.",
      severity: "warning",
      retryable: true,
    };
  }

  // ── 5xx Server error ──
  if (status && status >= 500) {
    return {
      title: "Server error",
      message: message || "An unexpected server error occurred. Please try again.",
      severity: "error",
      retryable: true,
    };
  }

  // ── Auth config errors ──
  if (code === "auth.configuration_error") {
    return {
      title: "Sign-in unavailable",
      message: "Sign-in is currently unavailable due to a server configuration issue. Please contact the administrator.",
      severity: "error",
      retryable: false,
      escalationHref: "/support",
    };
  }

  // ── 4xx Client errors ──
  if (status && status >= 400 && status < 500) {
    return {
      title: "Request error",
      message: message || "The request could not be completed.",
      hint,
      severity: "warning",
      retryable: false,
    };
  }

  // ── Fallback ──
  return {
    title: "Something went wrong",
    message: message || "An unexpected error occurred. Please try again.",
    hint,
    severity: "error",
    retryable: true,
  };
}
