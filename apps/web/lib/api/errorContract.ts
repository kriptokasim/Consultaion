export type ClientErrorKind =
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "rate_limited"
  | "timeout"
  | "network"
  | "server"
  | "validation"
  | "cancelled"
  | "unknown";

export interface ClientError {
  kind: ClientErrorKind;
  message: string;
  code?: string;
  hint?: string;
  retryable: boolean;
  resetAt?: string;
  requestId?: string;
  correlationId?: string;
  httpStatus: number;
  raw?: unknown;
}

interface BackendErrorBody {
  detail?: string;
  message?: string;
  error?: string;
  code?: string;
  hint?: string;
  retryable?: boolean;
  reset_at?: string;
  request_id?: string;
  correlation_id?: string;
}

function kindFromStatus(status: number, body: BackendErrorBody): ClientErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 429) return "rate_limited";
  if (status === 408) return "timeout";
  if (status >= 400 && status < 500) return "validation";
  if (status >= 500) return "server";
  return "unknown";
}

export function normalizeApiError(
  error: unknown,
  httpStatus?: number
): ClientError {
  if (
    error &&
    typeof error === "object" &&
    "kind" in error &&
    "message" in error &&
    "httpStatus" in error
  ) {
    return error as ClientError;
  }

  if (error instanceof DOMException && error.name === "AbortError") {
    return {
      kind: "cancelled",
      message: "Request was cancelled",
      retryable: false,
      httpStatus: 0,
    };
  }

  if (error instanceof TypeError && error.message.includes("fetch")) {
    return {
      kind: "network",
      message: "Network request failed",
      retryable: true,
      httpStatus: 0,
    };
  }

  if (error instanceof Error && error.name === "TimeoutError") {
    return {
      kind: "timeout",
      message: "Request timed out",
      retryable: true,
      httpStatus: 408,
    };
  }

  let body: BackendErrorBody = {};
  let status = httpStatus ?? 500;

  if (error && typeof error === "object") {
    const obj = error as Record<string, unknown>;
    if ("status" in obj && typeof obj.status === "number") {
      status = obj.status;
    }
    if ("body" in obj && typeof obj.body === "object" && obj.body !== null) {
      body = obj.body as BackendErrorBody;
    } else if ("data" in obj && typeof obj.data === "object" && obj.data !== null) {
      body = obj.data as BackendErrorBody;
    } else if ("detail" in obj) {
      body = { detail: String(obj.detail) };
    }
  }

  const kind = kindFromStatus(status, body);
  const message = body.detail ?? body.message ?? body.error ?? "An error occurred";

  return {
    kind,
    message,
    code: body.code,
    hint: body.hint,
    retryable: body.retryable ?? (status === 429 || status >= 500 || status === 408),
    resetAt: body.reset_at,
    requestId: body.request_id,
    correlationId: body.correlation_id,
    httpStatus: status,
    raw: error,
  };
}

export function isRetryable(error: ClientError): boolean {
  return error.retryable;
}

export function shouldRedirectToLogin(error: ClientError): boolean {
  return error.kind === "unauthorized" && error.httpStatus === 401;
}

export function getCorrelationId(error: ClientError): string | undefined {
  return error.correlationId ?? error.requestId;
}
