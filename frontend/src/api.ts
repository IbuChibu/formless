import type { FormContext } from "./formTypes";

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function readApiError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // Fall back to the status-based message below.
  }

  return `Request failed with status ${response.status}.`;
}

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function isValidFormContext(value: unknown): value is FormContext {
  if (!isRecord(value) || !Array.isArray(value.instructions)) {
    return false;
  }
  if (
    value.title !== undefined &&
    value.title !== null &&
    typeof value.title !== "string"
  ) {
    return false;
  }
  if (
    value.form_id !== undefined &&
    value.form_id !== null &&
    typeof value.form_id !== "string"
  ) {
    return false;
  }
  if (
    value.form_version !== undefined &&
    value.form_version !== null &&
    typeof value.form_version !== "string"
  ) {
    return false;
  }
  const hasFormId = typeof value.form_id === "string";
  const hasFormVersion = typeof value.form_version === "string";
  if (hasFormId !== hasFormVersion) {
    return false;
  }
  return value.instructions.every(
    (instruction) => typeof instruction === "string",
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
