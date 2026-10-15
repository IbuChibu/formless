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

assert.match(
  appSource,
  /useState<MobileWorkspaceView>\("assistant"\)/,
  "the mobile interview must default to the assistant view",
);
assert.match(
  appSource,
  /data-mobile-view=\{mobileWorkspaceView\}/,
  "the workspace must expose its selected mobile view",
);
assert.equal(
  count(appSource, 'id="document-workspace"'),
  1,
  "the mounted PDF workspace must have one stable landmark",
);
assert.equal(
  count(appSource, 'id="assistant-workspace"'),
  1,
  "the mounted assistant workspace must have one stable landmark",
);
assert.equal(
  count(appSource, 'aria-controls="document-workspace"'),
  1,
  "the mobile Form control must target the PDF workspace",
);
assert.equal(
  count(appSource, 'aria-controls="assistant-workspace"'),
  1,
  "the mobile Assistant control must target the interview workspace",
);
assert.match(
  appSource,
  /className="ai-question-form agent-message-form"[\s\S]*className="manual-fields-drawer"/,
  "the permanent typed composer must remain outside and above the manual fallback",
);
assert.match(
  styles,
  /@media \(max-width: 820px\)[\s\S]*\.workspace \.mobile-workspace-view \{[\s\S]*display: none;[\s\S]*\.workspace \.mobile-workspace-view\.mobile-view-active \{[\s\S]*display: flex;/,
  "small screens must show only the selected mounted workspace pane",
);
assert.match(
  styles,
  /@media \(max-width: 640px\)[\s\S]*\.workspace \{[\s\S]*height: calc\(100dvh - 128px\)/,
  "the mobile workspace must be sized to the available viewport",
);

console.log("workspace layout checks passed");

function count(value, search) {
  return value.split(search).length - 1;
}
