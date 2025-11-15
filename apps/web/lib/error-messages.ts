import { ApiError } from "@/lib/api";

const STATUS_MESSAGES: Record<number, string> = {
  400: "Something was wrong with the request.",
  401: "Please sign in to continue.",
  403: "You do not have access to this resource.",
  404: "This resource is no longer available.",
  429: "Rate limit reached. Please try again soon.",
  500: "The service encountered an error. Try again shortly.",
};

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    const statusMessage = error.status ? STATUS_MESSAGES[error.status] : null;
    if (error.body && typeof error.body === "object" && typeof error.body.detail === "string") {
      return error.body.detail;
    }
    if (typeof error.body === "string" && error.body.trim()) {
      return error.body;
    }
    if (statusMessage) {
      return statusMessage;
    }
  }
  return "Unexpected error. Please try again.";
}
