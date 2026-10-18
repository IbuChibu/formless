import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const [
  appSource,
  componentSource,
  preferenceSource,
  voiceSource,
  stateSource,
  responseSource,
  typeSource,
  styles,
] =
  await Promise.all([
    read("../src/App.tsx"),
    read("../src/components/SupportPreferencesPanel.tsx"),
    read("../src/assistancePreferences.ts"),
    read("../src/VoiceAssistantPanel.tsx"),
    read("../src/formFieldState.ts"),
    read("../src/agentResponse.ts"),
    read("../src/formTypes.ts"),
    read("../src/index.css"),
  ]);

assert.match(
  appSource,
  /useState<AssistancePreferences>\(createDefaultAssistancePreferences\(\)\)/,
  "App must own the session-only assistance preferences",
);
assert.match(
  appSource,
  /setAssistancePreferences\(createDefaultAssistancePreferences\(\)\)[\s\S]*setSupportIntroductionStatus\("pending"\)/,
  "selecting or retrying a PDF must clear support preferences",
);
assert.match(
  appSource,
  /assistance_preferences: assistancePreferences/,
  "every Form Agent request must carry the current bounded preferences",
);
assert.match(
  appSource,
  /<SupportPreferencesPanel[\s\S]*onSave=[\s\S]*onSkip=/,
  "the loaded assistant must retain the optional direct settings fallback",
);
assert.match(
  appSource,
  /voicePreferred=\{[\s\S]*interaction_mode === "voice"/,
  "voice preference should change emphasis without starting a session",
);

for (const preference of [
  "plain_language",
  "slower_pace",
  "organise_details",
  "reassurance",
  "explain_bureaucracy",
  "other",
]) {
  assert.match(
    preferenceSource,
    new RegExp(`value: "${preference}"`),
    `the ${preference} support choice must stay visible`,
  );
}

assert.match(
  stateSource,
  /phase: "support_setup"[\s\S]*support_setup_step: "needs"/,
  "a fresh form must begin in the explicit conversational support phase",
);
assert.match(
  typeSource,
  /"assistance_preferences_updated"/,
  "conversation preference changes must use a closed typed effect",
);
assert.match(
  responseSource,
  /parseAssistancePreferences[\s\S]*validAssistanceUpdate/,
  "the frontend must validate preference effects and their state transition",
);
assert.match(
  appSource,
  /effect\.effect === "assistance_preferences_updated"[\s\S]*setAssistancePreferences\(effect\.preferences\)[\s\S]*setSupportIntroductionStatus\(effect\.introduction_status\)/,
  "App must apply only the validated conversational preference effect",
);
assert.match(
  appSource,
  /phase === "support_setup"[\s\S]*Tell me what would make this form easier/,
  "the typed composer must support the conversational introduction",
);
assert.match(
  componentSource,
  /useState\(false\)[\s\S]*Adjust how I help/,
  "the checkbox controls must start collapsed behind Adjust how I help",
);
assert.match(
  componentSource,
  /adjustButtonRef[\s\S]*editHeadingRef[\s\S]*\.focus\(\)[\s\S]*adjustButtonRef\.current\?\.focus\(\)/,
  "opening and closing the optional settings must manage keyboard focus",
);
assert.doesNotMatch(
  componentSource,
  /How can I make this easier for you today\?/,
  "the checkbox fallback must not impersonate the conversational introduction",
);
assert.match(
  componentSource,
  /<fieldset className="support-needs-grid"[\s\S]*type="checkbox"/,
  "support needs must be grouped keyboard-operable controls",
);
assert.match(
  componentSource,
  /maxLength=\{200\}[\s\S]*required/,
  "the optional support note must be required when shown and bounded",
);
assert.match(
  componentSource,
  /\["no_preference", "No preference"\][\s\S]*\["voice", "I’d rather speak"\][\s\S]*\["typing", "I’d rather type"\][\s\S]*type="radio"/,
  "the interaction preference must be explicit rather than inferred",
);
assert.match(
  componentSource,
  /Choosing voice does not turn on your microphone/,
  "the adjustment fallback must explain that voice preference is not consent",
);
assert.doesNotMatch(
  componentSource,
  /startInterview|startListening|getUserMedia/,
  "the support introduction must not start microphone capture",
);
assert.match(
  voiceSource,
  /voicePreferred[\s\S]*Start conversation/,
  "voice stays behind the existing explicit start control",
);
assert.match(
  styles,
  /\.support-needs-grid label:has\(input:focus-visible\)[\s\S]*outline:/,
  "support controls must retain visible keyboard focus",
);
assert.match(
  styles,
  /@media \(max-width: 640px\)[\s\S]*\.support-input-choice[\s\S]*grid-template-columns: 1fr/,
  "support choices must stack on phone-sized screens",
);

console.log("Support preference checks passed");

function read(relativePath) {
  return readFile(new URL(relativePath, import.meta.url), "utf8");
}
