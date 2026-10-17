import PdfViewer from "../PdfViewer";
import type { PdfViewerField } from "../PdfViewer";
import { FieldControl } from "../FieldControls";
import { humanizeFieldId, isDirectlyEditableField } from "../formFieldState";
import type {
  FieldValue,
  PdfField,
  PreviewStatus,
} from "../formTypes";

type DocumentWorkspaceProps = {
  activeFieldId: string | null;
  canSaveDirectEdit: boolean;
  directEditField: PdfField | undefined;
  directEditFieldId: string | null;
  directEditValue: FieldValue;
  fields: PdfViewerField[];
  isMobileActive: boolean;
  originalUrlKey: string;
  previewCopy: string;
  previewError: string | null;
  previewStatus: PreviewStatus;
  previewUrl: string | null;
  selectedFileName: string;
  onChangeDirectEditValue: (value: FieldValue) => void;
  onClearDirectEdit: () => void;
  onCloseDirectEditor: () => void;
  onSaveDirectEdit: () => void;
  onSelectField: (fieldId: string) => void;
};

export default function DocumentWorkspace({
  activeFieldId,
  canSaveDirectEdit,
  directEditField,
  directEditFieldId,
  directEditValue,
  fields,
  isMobileActive,
  originalUrlKey,
  previewCopy,
  previewError,
  previewStatus,
  previewUrl,
  selectedFileName,
  onChangeDirectEditValue,
  onClearDirectEdit,
  onCloseDirectEditor,
  onSaveDirectEdit,
  onSelectField,
}: DocumentWorkspaceProps) {
  return (
    <article
      className={`panel preview-panel mobile-workspace-view${
        isMobileActive ? " mobile-view-active" : ""
      }`}
      id="document-workspace"
    >
      <div className="panel-header">
        <div>
          <p className="panel-kicker">Document</p>
          <h2>PDF preview</h2>
        </div>
        <div className={`preview-status ${previewStatus}`} aria-live="polite">
          <span className="status-dot" aria-hidden="true" />
          <span>{previewCopy}</span>
        </div>
      </div>

      {previewUrl ? (
        <PdfViewer
          key={originalUrlKey}
          activeFieldId={activeFieldId}
          fields={fields}
          fileName={selectedFileName}
          isUpdating={previewStatus === "updating"}
          onSelectField={onSelectField}
          selectedFieldId={directEditFieldId}
          url={previewUrl}
        />
      ) : null}

      {directEditField && isDirectlyEditableField(directEditField) ? (
        <form
          className="pdf-direct-editor"
          aria-labelledby="pdf-direct-editor-heading"
          onSubmit={(event) => {
            event.preventDefault();
            onSaveDirectEdit();
          }}
        >
          <div className="pdf-direct-editor-heading">
            <div>
              <span>Edit field on page {directEditField.page ?? "—"}</span>
              <strong id="pdf-direct-editor-heading">
                {directEditField.question ||
                  directEditField.label ||
                  humanizeFieldId(directEditField.id)}
              </strong>
            </div>
            <button
              type="button"
              aria-label="Close field editor"
              onClick={onCloseDirectEditor}
            >
              ×
            </button>
          </div>
          <FieldControl
            autoFocus
            field={directEditField}
            inputId="pdf-direct-field-input"
            value={directEditValue}
            onChange={onChangeDirectEditValue}
          />
          <div className="pdf-direct-editor-actions">
            <button
              className="primary"
              type="submit"
              disabled={!canSaveDirectEdit}
            >
              Save to form
            </button>
            <button type="button" onClick={onClearDirectEdit}>
              {directEditField.type === "checkbox"
                ? "Set to no"
                : "Clear answer"}
            </button>
            <button type="button" onClick={onCloseDirectEditor}>
              Cancel
            </button>
          </div>
          <small>
            Saving uses the same reviewed form state as the assistant and manual
            editor.
          </small>
        </form>
      ) : null}

      {previewError ? (
        <p className="inline-error" role="alert">
          {previewError} Your last successful preview is still shown.
        </p>
      ) : null}
    </article>
  );
}
