import type { ChangeEventHandler } from "react";

import { formatFileSize } from "../formFieldState";
import type {
  ConnectionStatus,
  ExtractionStatus,
} from "../formTypes";

type AppHeaderProps = {
  completedFilename: string;
  connectionCopy: string;
  connectionStatus: ConnectionStatus;
  currentFieldCount: number;
  downloadUrl: string | null;
  extractionStatus: ExtractionStatus;
  onFileSelection: ChangeEventHandler<HTMLInputElement>;
  onOpenReview: () => void;
  reviewItemCount: number;
  reviewedFieldCount: number;
  selectedFile: File | null;
};

export default function AppHeader({
  completedFilename,
  connectionCopy,
  connectionStatus,
  currentFieldCount,
  downloadUrl,
  extractionStatus,
  onFileSelection,
  onOpenReview,
  reviewItemCount,
  reviewedFieldCount,
  selectedFile,
}: AppHeaderProps) {
  return (
    <header
      className={`app-header${selectedFile ? " workspace-header" : ""}`}
    >
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true">
          F
        </span>
        <div>
          <p className="brand-name">Formless</p>
          <p className="brand-tagline">Voice-first form companion</p>
        </div>
      </div>

      {selectedFile ? (
        <>
          <div className="workspace-document-summary">
            <span>Current form</span>
            <strong title={selectedFile.name}>{selectedFile.name}</strong>
            {currentFieldCount > 0 ? (
              <small>
                {reviewedFieldCount} of {currentFieldCount} questions reviewed
              </small>
            ) : (
              <small>{formatFileSize(selectedFile.size)}</small>
            )}
          </div>
          <div className="workspace-header-actions">
            <div
              className={`connection-status compact ${connectionStatus}`}
              aria-label={connectionCopy}
              title={connectionCopy}
            >
              <span className="status-dot" aria-hidden="true" />
              <span>API</span>
            </div>
            <label className="header-file-button">
              Change PDF
              <input
                className="file-input"
                type="file"
                accept="application/pdf,.pdf"
                onChange={onFileSelection}
              />
            </label>
            <button
              className="header-review-button"
              type="button"
              disabled={extractionStatus !== "ready" || reviewItemCount === 0}
              onClick={onOpenReview}
            >
              Review
            </button>
            {downloadUrl ? (
              <a
                className="header-download-button"
                href={downloadUrl}
                download={completedFilename}
              >
                Download
              </a>
            ) : (
              <span
                className="header-download-button disabled"
                aria-disabled="true"
                title="Confirm an answer to create a completed copy"
              >
                Download
              </span>
            )}
          </div>
        </>
      ) : (
        <div className={`connection-status ${connectionStatus}`}>
          <span className="status-dot" aria-hidden="true" />
          <span>{connectionCopy}</span>
        </div>
      )}
    </header>
  );
}
