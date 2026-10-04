import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";

type ConnectionStatus = "checking" | "connected" | "disconnected";
type ExtractionStatus = "idle" | "loading" | "ready" | "empty" | "error";
type PreviewStatus = "idle" | "pending" | "updating" | "ready" | "error";
type FieldValue = string | boolean;

type HealthResponse = {
  status: string;
  service: string;
};

type PdfField = {
  id: string;
  type: string;
  options?: string[];
};

type PdfExtractionResponse = {
  fields: PdfField[];
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const previewDebounceMs = 600;

function App() {
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("checking");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fields, setFields] = useState<PdfField[]>([]);
  const [formValues, setFormValues] = useState<Record<string, FieldValue>>({});
  const [changedValues, setChangedValues] = useState<
    Record<string, FieldValue>
  >({});
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [extractionStatus, setExtractionStatus] =
    useState<ExtractionStatus>("idle");
  const [previewStatus, setPreviewStatus] =
    useState<PreviewStatus>("idle");
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const originalUrlRef = useRef<string | null>(null);
  const filledUrlRef = useRef<string | null>(null);
  const extractionControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function checkBackend() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, {
          signal: controller.signal,
        });
        const health: HealthResponse = await response.json();

        if (!response.ok || health.status !== "ok") {
          throw new Error("Backend health check failed");
        }

        setConnectionStatus("connected");
      } catch (error) {
        if (isAbortError(error)) {
          return;
        }

        setConnectionStatus("disconnected");
      }
    }

    void checkBackend();

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (
      !selectedFile ||
      extractionStatus !== "ready" ||
      Object.keys(changedValues).length === 0
    ) {
      return;
    }

    const fileToFill = selectedFile;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
      async function refreshPreview() {
        setPreviewStatus("updating");
        setPreviewError(null);

        const formData = new FormData();
        formData.append("file", fileToFill);
        formData.append("values", JSON.stringify(changedValues));

        try {
          const response = await fetch(`${apiBaseUrl}/pdf/fill`, {
            method: "POST",
            body: formData,
            signal: controller.signal,
          });

          if (!response.ok) {
            throw new Error(await readApiError(response));
          }

          const filledPdf = await response.blob();
          if (controller.signal.aborted) {
            return;
          }

          const nextUrl = URL.createObjectURL(filledPdf);
          if (filledUrlRef.current) {
            URL.revokeObjectURL(filledUrlRef.current);
          }

          filledUrlRef.current = nextUrl;
          setPreviewUrl(nextUrl);
          setDownloadUrl(nextUrl);
          setPreviewStatus("ready");
        } catch (error) {
          if (isAbortError(error)) {
            return;
          }

          setPreviewError(getErrorMessage(error));
          setPreviewStatus("error");
        }
      }

      void refreshPreview();
    }, previewDebounceMs);

    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
  }, [changedValues, extractionStatus, selectedFile]);

  useEffect(() => {
    return () => {
      extractionControllerRef.current?.abort();
      if (originalUrlRef.current) {
        URL.revokeObjectURL(originalUrlRef.current);
      }
      if (filledUrlRef.current) {
        URL.revokeObjectURL(filledUrlRef.current);
      }
    };
  }, []);

  async function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    if (file.type !== "application/pdf") {
      setExtractionError("Choose a PDF file to continue.");
      setExtractionStatus("error");
      return;
    }

    extractionControllerRef.current?.abort();
    const controller = new AbortController();
    extractionControllerRef.current = controller;

    if (originalUrlRef.current) {
      URL.revokeObjectURL(originalUrlRef.current);
    }
    if (filledUrlRef.current) {
      URL.revokeObjectURL(filledUrlRef.current);
      filledUrlRef.current = null;
    }

    const originalUrl = URL.createObjectURL(file);
    originalUrlRef.current = originalUrl;

    setSelectedFile(file);
    setPreviewUrl(originalUrl);
    setDownloadUrl(null);
    setFields([]);
    setFormValues({});
    setChangedValues({});
    setExtractionError(null);
    setPreviewError(null);
    setExtractionStatus("loading");
    setPreviewStatus("idle");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${apiBaseUrl}/pdf/extract`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(await readApiError(response));
      }

      const extraction = (await response.json()) as PdfExtractionResponse;
      if (!Array.isArray(extraction.fields)) {
        throw new Error("The API returned an invalid field response.");
      }

      const initialValues = Object.fromEntries(
        extraction.fields.map((field) => [
          field.id,
          field.type === "checkbox" ? false : "",
        ]),
      );

      setFields(extraction.fields);
      setFormValues(initialValues);
      setExtractionStatus(extraction.fields.length > 0 ? "ready" : "empty");
    } catch (error) {
      if (isAbortError(error)) {
        return;
      }

      setExtractionError(getErrorMessage(error));
      setExtractionStatus("error");
    }
  }

  function updateField(fieldId: string, value: FieldValue) {
    setFormValues((current) => ({ ...current, [fieldId]: value }));
    setChangedValues((current) => ({ ...current, [fieldId]: value }));
    setPreviewError(null);
    setPreviewStatus("pending");
  }

  const connectionCopy = {
    checking: "Checking API",
    connected: "API connected",
    disconnected: "API unavailable",
  }[connectionStatus];

  const previewCopy = {
    idle: "Original document",
    pending: "Changes pending",
    updating: "Updating preview",
    ready: "Preview up to date",
    error: "Preview update failed",
  }[previewStatus];

  const completedFilename = selectedFile
    ? `completed-${selectedFile.name}`
    : "completed-form.pdf";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            F
          </span>
          <div>
            <p className="brand-name">Formless</p>
            <p className="brand-tagline">Manual PDF workspace</p>
          </div>
        </div>

        <div className={`connection-status ${connectionStatus}`}>
          <span className="status-dot" aria-hidden="true" />
          <span>{connectionCopy}</span>
        </div>
      </header>

      <main className="app-main">
        <section className="intro-panel">
          <div className="intro-copy">
            <p className="eyebrow">Fill with confidence</p>
            <h1>See your form update as you type.</h1>
            <p>
              Choose a fillable PDF, complete its fields, and download a new
              copy. Your original file stays unchanged.
            </p>
          </div>

          <div className="upload-area">
            <label className="file-button">
              {selectedFile ? "Choose another PDF" : "Choose a fillable PDF"}
              <input
                className="file-input"
                id="pdf-upload"
                type="file"
                accept="application/pdf,.pdf"
                onChange={handleFileSelection}
              />
            </label>
            {selectedFile ? (
              <div className="selected-file">
                <span className="file-icon" aria-hidden="true">
                  PDF
                </span>
                <span>
                  <strong>{selectedFile.name}</strong>
                  <small>{formatFileSize(selectedFile.size)}</small>
                </span>
              </div>
            ) : (
              <p>PDF files stay in this browser session.</p>
            )}
          </div>
        </section>

        {extractionError ? (
          <div className="error-banner" role="alert">
            <strong>Could not read this form.</strong>
            <span>{extractionError}</span>
          </div>
        ) : null}

        {!selectedFile ? (
          <section className="empty-workspace">
            <div className="empty-preview" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <div>
              <p className="eyebrow">Ready when you are</p>
              <h2>Your PDF workspace will appear here.</h2>
              <p>
                The document preview and its detected form fields will sit side
                by side.
              </p>
            </div>
          </section>
        ) : (
          <section className="workspace">
            <article className="panel preview-panel">
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

              <div className="pdf-frame">
                {previewUrl ? (
                  <object
                    key={previewUrl}
                    className="pdf-viewer"
                    data={previewUrl}
                    type="application/pdf"
                    aria-label={`Preview of ${selectedFile.name}`}
                  >
                    <div className="pdf-fallback">
                      <p>This browser could not display the PDF preview.</p>
                      <a href={previewUrl} target="_blank" rel="noreferrer">
                        Open the PDF in a new tab
                      </a>
                    </div>
                  </object>
                ) : null}
                {previewStatus === "updating" ? (
                  <div className="preview-overlay" aria-hidden="true">
                    <span className="spinner" />
                  </div>
                ) : null}
              </div>

              {previewError ? (
                <p className="inline-error" role="alert">
                  {previewError} Your last successful preview is still shown.
                </p>
              ) : null}
            </article>

            <aside className="panel fields-panel">
              <div className="panel-header fields-heading">
                <div>
                  <p className="panel-kicker">Form fields</p>
                  <h2>Complete the details</h2>
                </div>
                {fields.length > 0 ? (
                  <span className="field-count">{fields.length}</span>
                ) : null}
              </div>

              <div className="fields-content">
                {extractionStatus === "loading" ? (
                  <div className="loading-state" aria-live="polite">
                    <span className="spinner" />
                    <div>
                      <strong>Reading form fields</strong>
                      <p>This should only take a moment.</p>
                    </div>
                  </div>
                ) : null}

                {extractionStatus === "empty" ? (
                  <div className="message-state">
                    <strong>No fillable fields found</strong>
                    <p>Try another PDF that contains AcroForm fields.</p>
                  </div>
                ) : null}

                {extractionStatus === "error" ? (
                  <div className="message-state">
                    <strong>Fields unavailable</strong>
                    <p>The original PDF is still available in the preview.</p>
                  </div>
                ) : null}

                {extractionStatus === "ready" ? (
                  <form className="field-list" onSubmit={(event) => event.preventDefault()}>
                    {fields.map((field, index) => (
                      <FieldControl
                        key={field.id}
                        field={field}
                        inputId={`pdf-field-${index}`}
                        value={formValues[field.id]}
                        onChange={(value) => updateField(field.id, value)}
                      />
                    ))}
                  </form>
                ) : null}
              </div>

              <div className="fields-footer">
                <p>
                  {downloadUrl
                    ? "Your latest changes are ready to download."
                    : "Edit a field to create a completed copy."}
                </p>
                {downloadUrl ? (
                  <a
                    className="download-button"
                    href={downloadUrl}
                    download={completedFilename}
                  >
                    Download completed PDF
                  </a>
                ) : (
                  <span className="download-button disabled" aria-disabled="true">
                    Download completed PDF
                  </span>
                )}
              </div>
            </aside>
          </section>
        )}
      </main>
    </div>
  );
}

type FieldControlProps = {
  field: PdfField;
  inputId: string;
  value: FieldValue | undefined;
  onChange: (value: FieldValue) => void;
};

function FieldControl({ field, inputId, value, onChange }: FieldControlProps) {
  const label = humanizeFieldId(field.id);

  if (field.type === "text") {
    return (
      <label className="field-control" htmlFor={inputId}>
        <span className="field-label">{label}</span>
        <input
          id={inputId}
          type="text"
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
          autoComplete="off"
        />
        <code>{field.id}</code>
      </label>
    );
  }

  if (field.type === "dropdown") {
    return (
      <label className="field-control" htmlFor={inputId}>
        <span className="field-label">{label}</span>
        <select
          id={inputId}
          value={typeof value === "string" ? value : ""}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="" disabled>
            Select an option
          </option>
          {(field.options ?? []).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <code>{field.id}</code>
      </label>
    );
  }

  if (field.type === "checkbox") {
    return (
      <label className="checkbox-control" htmlFor={inputId}>
        <input
          id={inputId}
          type="checkbox"
          checked={typeof value === "boolean" ? value : false}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span>
          <span className="field-label">{label}</span>
          <code>{field.id}</code>
        </span>
      </label>
    );
  }

  return (
    <div className="unsupported-field">
      <span>
        <span className="field-label">{label}</span>
        <code>{field.id}</code>
      </span>
      <small>{field.type} is not supported in this milestone.</small>
    </div>
  );
}

async function readApiError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // Fall back to the status-based message below.
  }

  return `Request failed with status ${response.status}.`;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function humanizeFieldId(fieldId: string): string {
  const words = fieldId.replace(/[._-]+/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default App;
