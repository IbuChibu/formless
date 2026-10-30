import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const appSource = await readFile(
  new URL("../src/App.tsx", import.meta.url),
  "utf8",
);
const styles = await readFile(
  new URL("../src/index.css", import.meta.url),
  "utf8",
);
const documentWorkspaceSource = await readFile(
  new URL("../src/components/DocumentWorkspace.tsx", import.meta.url),
  "utf8",
);
const manualDrawerSource = await readFile(
  new URL("../src/components/ManualFieldsDrawer.tsx", import.meta.url),
  "utf8",
);

assert.match(
  appSource,
  /app-shell\$\{selectedFile \? " document-loaded"/,
  "a loaded document must activate the fixed workspace shell",
);
for (const region of [
  "assistant-session-region",
  "assistant-question-region",
  "assistant-conversation-region",
  "assistant-proposal-region",
]) {
  assert.match(
    appSource,
    new RegExp(`className="${region}"`),
    `${region} must remain a distinct layout owner`,
  );
}
assert.match(
  appSource,
  /assistant-session-region[\s\S]*assistant-question-region[\s\S]*assistant-conversation-region[\s\S]*assistant-proposal-region/,
  "session, question, conversation, and review must follow stable visual order",
);
assert.match(
  appSource,
  /assistant-conversation-region[\s\S]*<SupportPreferencesPanel/,
  "secondary assistance settings must live in the scrollable conversation region",
);
assert.match(
  appSource,
  /className="assistant-conversation-region"[\s\S]*role="region"[\s\S]*tabIndex=\{0\}/,
  "the conversation scroll owner must be keyboard reachable and labelled",
);
assert.match(
  appSource,
  /<\/section>[\s\S]*className="ai-question-form agent-message-form"/,
  "the typed composer must remain outside the internally scrolling assistant panel",
);
assert.equal(
  count(appSource, 'id="assistant-workspace"'),
  1,
  "responsive switching must reuse one mounted assistant workspace",
);
assert.equal(
  count(documentWorkspaceSource, 'id="document-workspace"'),
  1,
  "responsive switching must reuse one mounted PDF workspace",
);

assert.match(
  styles,
  /\.app-shell\.document-loaded \{[\s\S]*height: 100dvh;[\s\S]*overflow: hidden;/,
  "the loaded application shell must fit and clip to the usable viewport",
);
assert.match(
  manualDrawerSource,
  /event\.key === "Escape"[\s\S]*onToggle\(\)/,
  "Escape must close the manual editor overlay",
);
assert.match(
  manualDrawerSource,
  /toggleRef\.current\?\.focus\(\)/,
  "closing the manual editor must restore focus to its toggle",
);
assert.match(
  styles,
  /\.document-loaded \.workspace \{[\s\S]*grid-template-columns: minmax\(0, 58fr\) minmax\(390px, 42fr\)/,
  "desktop must use the planned approximately 58/42 document-assistant split",
);
assert.match(
  styles,
  /\.assistant-conversation-region \{[\s\S]*overflow-y: auto;[\s\S]*overscroll-behavior: contain;/,
  "conversation history must own its internal scrolling",
);
assert.match(
  styles,
  /\.pdf-page-stage \{[\s\S]*overflow: auto;/,
  "the PDF stage must retain independent internal scrolling",
);
assert.match(
  styles,
  /\.assistant-proposal-region \{[\s\S]*max-height:[\s\S]*overflow-y: auto;/,
  "proposal actions must remain in a bounded pinned review region",
);
assert.match(
  styles,
  /\.document-loaded \.manual-fields-content \{[\s\S]*position: absolute;/,
  "the expanded manual fallback must overlay rather than displace primary controls",
);
assert.match(
  styles,
  /\.document-loaded \.form-review-panel \{[\s\S]*position: absolute;/,
  "final review must have a bounded closeable overlay",
);
assert.match(
  styles,
  /@media \(max-width: 820px\)[\s\S]*\.document-loaded \.workspace \{[\s\S]*min-height: 0;/,
  "the selected mobile pane must shrink with mobile toolbars and keyboards",
);
assert.match(
  styles,
  /@media \(prefers-reduced-motion: reduce\)[\s\S]*animation: none;/,
  "the fixed workspace must preserve reduced-motion behavior",
);

console.log("fixed conversational workspace checks passed");

function count(value, search) {
  return value.split(search).length - 1;
}
