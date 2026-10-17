import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const appSource = await readFile(
  new URL("../src/App.tsx", import.meta.url),
  "utf8",
);
const viewerSource = await readFile(
  new URL("../src/PdfViewer.tsx", import.meta.url),
  "utf8",
);
const documentWorkspaceSource = await readFile(
  new URL("../src/components/DocumentWorkspace.tsx", import.meta.url),
  "utf8",
);
const reviewSource = await readFile(
  new URL("../src/components/FormReviewPanel.tsx", import.meta.url),
  "utf8",
);

assert.match(
  appSource,
  /const \[manualDrawerOpen, setManualDrawerOpen\] = useState\(false\)/,
  "the full manual editor must remain closed by default",
);
assert.match(
  appSource,
  /<DocumentWorkspace[\s\S]*activeFieldId=\{pdfNavigationFieldId\}[\s\S]*fields=\{pdfViewerFields\}[\s\S]*onSelectField=\{openDirectEditor\}/,
  "App must give the document workspace canonical geometry, navigation, and selection state",
);
assert.match(
  documentWorkspaceSource,
  /<PdfViewer[\s\S]*activeFieldId=\{activeFieldId\}[\s\S]*fields=\{fields\}[\s\S]*onSelectField=\{onSelectField\}/,
  "the document workspace must pass canonical geometry and selection callbacks to the PDF viewer",
);
assert.match(
  viewerSource,
  /activeField\?\.widgets\?\.\[0\]\?\.page \?\? activeField\?\.page/,
  "an active field must navigate to its widget page when geometry is available",
);
assert.match(
  viewerSource,
  /className="pdf-field-layer"[\s\S]*className=\{\[[\s\S]*"pdf-field-target"[\s\S]*onClick=\{\(\) => onSelectField\(field\.id\)\}/,
  "extracted widgets must render as clickable field targets",
);
assert.match(
  documentWorkspaceSource,
  /className="pdf-direct-editor"[\s\S]*<FieldControl[\s\S]*value=\{directEditValue\}[\s\S]*Save to form/,
  "clicking a PDF field must expose a focused editor",
);
assert.match(
  appSource,
  /function writeFieldValue\([\s\S]*if \(isConfirmed\) \{[\s\S]*next\[fieldId\] = value;[\s\S]*else \{[\s\S]*delete next\[fieldId\]/,
  "only confirmed direct, manual, or agent values may enter the fill payload",
);
assert.match(
  reviewSource,
  /className="form-review-panel"[\s\S]*counts\.confirmed[\s\S]*counts\.proposed[\s\S]*counts\.skipped[\s\S]*counts\.unanswered/,
  "final review must expose every required field status",
);

console.log("PDF workflow checks passed");
