import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const [
  appSource,
  apiSource,
  headerSource,
  workspaceSource,
  reviewSource,
  proposalSource,
  manualDrawerSource,
  viewerSource,
  styles,
] = await Promise.all([
  read("../src/App.tsx"),
  read("../src/api.ts"),
  read("../src/components/AppHeader.tsx"),
  read("../src/components/DocumentWorkspace.tsx"),
  read("../src/components/FormReviewPanel.tsx"),
  read("../src/components/ProposalReview.tsx"),
  read("../src/components/ManualFieldsDrawer.tsx"),
  read("../src/PdfViewer.tsx"),
  read("../src/index.css"),
]);

assert.match(
  appSource,
  /connectionCheckNonce[\s\S]*setConnectionStatus\("checking"\)[\s\S]*\[connectionCheckNonce\]/,
  "the backend health check must expose a repeatable retry path",
);
assert.match(
  appSource,
  /function retryExtraction\(\)[\s\S]*extractPdfFile\(selectedFile\)/,
  "field extraction must be retryable without asking for the PDF again",
);
assert.match(
  appSource,
  /previewRetryNonce[\s\S]*\/pdf\/fill[\s\S]*\[changedValues, extractionStatus, previewRetryNonce, selectedFile\]/,
  "PDF filling must be retryable from retained form state",
);
assert.match(
  appSource,
  /function writeFieldValue\([\s\S]*next\.add\(fieldId\)[\s\S]*next\.delete\(fieldId\)/,
  "manual corrections and clearing must update canonical confirmation state",
);
assert.match(
  appSource,
  /function closeDirectEditor\([\s\S]*document\.getElementById\("document-workspace"\)\?\.focus\(\)/,
  "closing the direct editor must return keyboard focus to the PDF workspace",
);
assert.match(
  appSource,
  /className="ai-question-form agent-message-form"[\s\S]*<label htmlFor="agent-message"[\s\S]*id="agent-message"[\s\S]*type="submit"/,
  "the conversation composer must have a named input and keyboard submit control",
);
assert.match(
  appSource,
  /className="ai-explanation-state"[\s\S]*aria-live="polite"[\s\S]*role="status"/,
  "model loading state must be announced without taking focus",
);
assert.match(
  apiSource,
  /Could not reach the backend[\s\S]*available retry control/,
  "offline requests must explain how to recover",
);

assert.match(
  headerSource,
  /aria-label=\{connectionCopy\}[\s\S]*role="status"[\s\S]*Retry connection/,
  "connection state and recovery must be announced and operable",
);
assert.match(
  headerSource,
  /id="open-form-review"[\s\S]*disabled=\{extractionStatus !== "ready"/,
  "the final review control must be a real state-aware button",
);
assert.match(
  headerSource,
  /className="header-download-button disabled"[\s\S]*disabled[\s\S]*aria-disabled="true"/,
  "unavailable download state must be exposed semantically",
);
assert.match(
  workspaceSource,
  /id="document-workspace"[\s\S]*tabIndex=\{-1\}/,
  "the PDF workspace must be a programmatic focus return target",
);
assert.match(
  workspaceSource,
  /event\.key === "Escape"[\s\S]*onCloseDirectEditor\(\)/,
  "the direct PDF editor must close from the keyboard",
);
assert.match(
  workspaceSource,
  /preview-recovery[\s\S]*Retry completed preview/,
  "a failed fill preview must retain its last preview and expose retry",
);
assert.match(
  reviewSource,
  /panelRef\.current\?\.focus\(\)[\s\S]*tabIndex=\{-1\}[\s\S]*event\.key === "Escape"/,
  "final review must receive focus and support Escape",
);
assert.match(
  proposalSource,
  /aria-label="Review proposed answer"[\s\S]*Confirm[\s\S]*Edit[\s\S]*Reject/,
  "proposal confirmation must remain a named, keyboard-operable review region",
);
assert.match(
  manualDrawerSource,
  /aria-label="Manual field editor"[\s\S]*aria-controls="manual-fields-panel"[\s\S]*aria-expanded=\{isOpen\}/,
  "the manual drawer must expose its label, controlled region, and state",
);
assert.match(
  viewerSource,
  /aria-label="PDF page navigation"[\s\S]*aria-label="Previous PDF page"[\s\S]*aria-label="Next PDF page"/,
  "PDF page controls must have screen-reader navigation labels",
);
assert.match(
  viewerSource,
  /type="button"[\s\S]*className=\{\[[\s\S]*"pdf-field-target"[\s\S]*aria-label=\{`Edit \$\{fieldName\}/,
  "fillable PDF overlays must be keyboard-operable named buttons",
);

assert.match(
  styles,
  /@media \(max-width: 820px\)[\s\S]*\.workspace \.mobile-workspace-view\.mobile-view-active/,
  "mobile screens must expose one selected workspace pane",
);
assert.match(
  styles,
  /@media \(max-width: 640px\)[\s\S]*\.error-banner[\s\S]*flex-direction: column/,
  "recovery controls must stack at phone sizes",
);
assert.match(
  styles,
  /@media \(max-width: 640px\)[\s\S]*\.workspace-header \.brand-name[\s\S]*display: none[\s\S]*\.workspace-header-actions[\s\S]*gap: 4px/,
  "the loaded-document header must remain compact at phone sizes",
);
assert.match(
  styles,
  /@media \(prefers-reduced-motion: reduce\)/,
  "motion-sensitive users must receive reduced animation",
);
assert.match(
  styles,
  /\.pdf-field-target:focus-visible[\s\S]*\.form-review-panel:focus-visible/,
  "PDF fields and final review must have visible keyboard focus",
);

console.log("Milestone 9 reliability checks passed");

function read(relativePath) {
  return readFile(new URL(relativePath, import.meta.url), "utf8");
}
