import type {
  AssistanceNeed,
  AssistancePreferences,
} from "./formTypes";

export const assistanceNeedOptions: Array<{
  value: AssistanceNeed;
  label: string;
  description: string;
}> = [
  {
    value: "plain_language",
    label: "Use simpler language",
    description: "I’ll use shorter sentences and everyday words.",
  },
  {
    value: "slower_pace",
    label: "Go slowly",
    description: "I’ll keep this to one question or decision at a time.",
  },
  {
    value: "organise_details",
    label: "Help organise my details",
    description: "I’ll help separate what you tell me into the right fields.",
  },
  {
    value: "reassurance",
    label: "Make review points clear",
    description: "I’ll remind you when nothing changes until you confirm it.",
  },
  {
    value: "explain_bureaucracy",
    label: "Explain official wording",
    description: "I’ll unpack unfamiliar form language when the form supports it.",
  },
  {
    value: "other",
    label: "Something else",
    description: "Add one short note about how you would like help.",
  },
];

export function createDefaultAssistancePreferences(): AssistancePreferences {
  return {
    support_needs: [],
    interaction_mode: "no_preference",
    other_note: null,
    assistance_language: "en",
  };
}

export function hasAssistancePreferences(
  preferences: AssistancePreferences,
): boolean {
  return Boolean(
    preferences.support_needs.length ||
      preferences.interaction_mode !== "no_preference" ||
      preferences.other_note,
  );
}

export function assistancePreferenceLabels(
  preferences: AssistancePreferences,
): string[] {
  const labels = preferences.support_needs.map(
    (need) =>
      assistanceNeedOptions.find((option) => option.value === need)?.label ??
      need,
  );
  if (preferences.interaction_mode === "voice") {
    labels.push("Prefer speaking");
  } else if (preferences.interaction_mode === "typing") {
    labels.push("Prefer typing");
  }
  return labels;
}
