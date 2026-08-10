export type SseResultStatus = "completed" | "running" | "failed";

const RECOVERY_DELAYS_MS = [1000, 3000] as const;

export function nextSseRecoveryDelay(attempt: number): number | null {
  return RECOVERY_DELAYS_MS[attempt] ?? null;
}

export function classifySseResultStatus(status: number): SseResultStatus {
  if (status === 200) return "completed";
  if (status === 409) return "running";
  return "failed";
}
