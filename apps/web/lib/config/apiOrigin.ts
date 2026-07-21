export interface ApiOriginEnvironment {
  [key: string]: string | undefined;
  API_INTERNAL_URL?: string;
  NEXT_PUBLIC_API_URL?: string;
}

export function resolveServerApiOrigin(
  environment: ApiOriginEnvironment = process.env,
): string {
  return (
    environment.API_INTERNAL_URL ??
    environment.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000"
  );
}
