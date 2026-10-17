import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const [appSource, componentSource, preferenceSource, voiceSource, styles] =
  await Promise.all([
    read("../src/App.tsx"),
    read("../src/components/SupportPreferencesPanel.tsx"),
    read("../src/assistancePreferences.ts"),
    read("../src/VoiceAssistantPanel.tsx"),
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
  "the loaded assistant must expose save and skip paths",
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
  componentSource,
  /How can I make this easier for you today\?/,
  "the introduction must ask a needs-based question",
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
  "the introduction must explain that voice preference is not consent",
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
