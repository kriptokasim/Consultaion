/**
 * Error mapping layer for normalizing API errors into UI-friendly shape.
 * Patchset 65.A1
 */

export interface NormalizedError {
    code: string;
    message: string;
    httpStatus?: number;
    details?: Record<string, unknown>;
}

/**
 * Normalize any error object from API/fetch into a consistent shape.
 */
export function normalizeError(error: unknown): NormalizedError {
    // Handle fetch Response or ApiError with status
    if (error && typeof error === "object") {
        const errObj = error as Record<string, unknown>;

        // ApiError from lib/api
        if ("status" in errObj && typeof errObj.status === "number") {
            const status = errObj.status as number;
            const body = errObj.body as Record<string, unknown> | undefined;

            // 403 account disabled
            if (status === 403) {
                const detail = body?.detail as Record<string, unknown> | undefined;
                if (detail?.error === "account_disabled") {
                    return {
                        code: "account_disabled",
                        message: (detail?.message as string) || "Your account has been disabled.",
                        httpStatus: 403,
                        details: detail,
                    };
                }
                return {
                    code: "permission_denied",
                    message: "You do not have permission to perform this action.",
                    httpStatus: 403,
                };
            }

            // 429 quota/rate limit
            if (status === 429) {
                const detail = body?.detail as Record<string, unknown> | undefined;
                const errPayload = body?.error as Record<string, unknown> | undefined;

                // Check for quota exceeded patterns
                const code = (detail?.error as string) ||
                    (errPayload?.code as string) ||
                    (detail?.code as string) ||
                    "quota_exceeded";

                return {
                    code,
                    message: (errPayload?.message as string) ||
                        (detail?.message as string) ||
                        "Rate limit or quota exceeded. Please try again later.",
                    httpStatus: 429,
                    details: detail || errPayload,
                };
            }

            // Generic AppError format: { error: { code, message, details } }
            const appError = body?.error as Record<string, unknown> | undefined;
            if (appError && typeof appError.code === "string") {
                return {
                    code: appError.code as string,
                    message: (appError.message as string) || "An error occurred.",
                    httpStatus: status,
                    details: appError.details as Record<string, unknown> | undefined,
                };
            }

            // Fallback for body.detail string
            if (typeof body?.detail === "string") {
                return {
                    code: `http_${status}`,
                    message: body.detail,
                    httpStatus: status,
                };
            }

            // Fallback for body.message string
            if (typeof body?.message === "string") {
                return {
                    code: `http_${status}`,
                    message: body.message,
                    httpStatus: status,
                };
            }

            return {
                code: `http_${status}`,
                message: getDefaultMessage(status),
                httpStatus: status,
            };
        }

        // Standard Error object
        if (error instanceof Error) {
            return {
                code: "client_error",
                message: error.message || "An unexpected error occurred.",
            };
        }

        // Object with message property
        if ("message" in errObj && typeof errObj.message === "string") {
            return {
                code: (errObj.code as string) || "unknown",
                message: errObj.message,
                httpStatus: errObj.status as number | undefined,
            };
        }
    }

    // String error
    if (typeof error === "string") {
        return {
            code: "unknown",
            message: error,
        };
    }

    return {
        code: "unknown",
        message: "An unexpected error occurred. Please try again.",
    };
}

function getDefaultMessage(status: number): string {
    const messages: Record<number, string> = {
        400: "Invalid request. Please check your input.",
        401: "Please sign in to continue.",
        403: "You do not have permission to perform this action.",
        404: "The requested resource was not found.",
        429: "Rate limit exceeded. Please try again later.",
        500: "Server error. Please try again later.",
        502: "Service temporarily unavailable.",
        503: "Service temporarily unavailable.",
    };
    return messages[status] || "An error occurred. Please try again.";
}

/**
 * Check if error indicates account is disabled.
 */
export function isAccountDisabled(error: NormalizedError): boolean {
    return error.code === "account_disabled" || error.httpStatus === 403;
}

/**
 * Check if error indicates quota exceeded.
 */
export function isQuotaExceeded(error: NormalizedError): boolean {
    return (
        error.httpStatus === 429 ||
        error.code.includes("quota") ||
        error.code.includes("rate_limit")
    );
}
