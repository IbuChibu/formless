export type VoiceSessionMode =
  | "inactive"
  | "active"
  | "paused"
  | "muted"
  | "ended";

export type VoiceSessionControlEvent =
  | "start"
  | "pause"
  | "mute"
  | "resume"
  | "end"
  | "reset";

export const VOICE_RECOVERY_DELAY_MS = 650;
export const VOICE_SILENCE_REOPEN_DELAY_MS = 250;
export const MAX_VOICE_SILENCE_REOPEN_DELAY_MS = 4000;
export const MAX_AUTOMATIC_VOICE_RECOVERIES = 1;

export function transitionVoiceSessionMode(
  current: VoiceSessionMode,
  event: VoiceSessionControlEvent,
): VoiceSessionMode {
  if (event === "reset") {
    return "inactive";
  }
  if (event === "end") {
    return "ended";
  }
  if (event === "pause") {
    return current === "active" ? "paused" : current;
  }
  if (event === "mute") {
    return current === "active" ? "muted" : current;
  }
  if (event === "start" || event === "resume") {
    return "active";
  }
  return current;
}

export function nextAutomaticRecoveryAttempt(
  completedAttempts: number,
): number | null {
  return completedAttempts < MAX_AUTOMATIC_VOICE_RECOVERIES
    ? completedAttempts + 1
    : null;
}

export function voiceSilenceReopenDelay(consecutiveSilences: number): number {
  const safeCount = Math.max(0, Math.min(consecutiveSilences, 8));
  return Math.min(
    VOICE_SILENCE_REOPEN_DELAY_MS * 2 ** safeCount,
    MAX_VOICE_SILENCE_REOPEN_DELAY_MS,
  );
}

export function isRecoverableVoiceInputError(message: string): boolean {
  const normalized = message.toLocaleLowerCase();
  if (
    /denied|not allowed|no working microphone|not configured|unsupported|compatible microphone capture/.test(
      normalized,
    )
  ) {
    return false;
  }
  return /disconnect|could not continue|connect in time|network|expired|temporary credential|token/.test(
    normalized,
  );
}
