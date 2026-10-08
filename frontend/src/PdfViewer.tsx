import { useEffect, useRef, useState } from "react";
import {
  AnnotationMode,
  GlobalWorkerOptions,
  getDocument,
} from "pdfjs-dist";
import type {
  PDFDocumentProxy,
  RenderTask,
} from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

type ViewerStatus = "loading" | "rendering" | "ready" | "error";

type PdfViewerProps = {
  fileName: string;
  isUpdating: boolean;
  url: string;
};

function PdfViewer({ fileName, isUpdating, url }: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pageSlotRef = useRef<HTMLDivElement | null>(null);
  const [pdfDocument, setPdfDocument] = useState<PDFDocumentProxy | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [pageWidth, setPageWidth] = useState(0);
  const [viewerStatus, setViewerStatus] =
    useState<ViewerStatus>("loading");
  const [viewerError, setViewerError] = useState<string | null>(null);

  useEffect(() => {
    const pageSlot = pageSlotRef.current;
    if (!pageSlot) {
      return;
    }
    const observedPageSlot = pageSlot;

    function updatePageWidth() {
      setPageWidth(Math.floor(observedPageSlot.clientWidth));
    }

    updatePageWidth();
    const observer = new ResizeObserver(updatePageWidth);
    observer.observe(observedPageSlot);

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let active = true;
    const loadingTask = getDocument(url);

    setPdfDocument(null);
    setViewerStatus("loading");
    setViewerError(null);

    void loadingTask.promise
      .then((document) => {
        if (!active) {
          return;
        }

        setPdfDocument(document);
        setPageCount(document.numPages);
        setPageNumber((current) => Math.min(current, document.numPages));
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }

        setPageCount(0);
        setViewerError(getViewerErrorMessage(error));
        setViewerStatus("error");
      });

    return () => {
      active = false;
      void loadingTask.destroy();
    };
  }, [url]);

  useEffect(() => {
    if (!pdfDocument || pageWidth <= 0) {
      return;
    }
    const documentToRender = pdfDocument;

    let active = true;
    let renderTask: RenderTask | null = null;

    async function renderPage() {
      const canvas = canvasRef.current;
      if (!canvas) {
        return;
      }

      setViewerStatus("rendering");
      setViewerError(null);

      try {
        const page = await documentToRender.getPage(pageNumber);
        if (!active) {
          return;
        }

        const baseViewport = page.getViewport({ scale: 1 });
        const cssScale = pageWidth / baseViewport.width;
        const outputScale = Math.min(window.devicePixelRatio || 1, 2);
        const renderViewport = page.getViewport({
          scale: cssScale * outputScale,
        });

        canvas.width = Math.floor(renderViewport.width);
        canvas.height = Math.floor(renderViewport.height);
        canvas.style.width = `${Math.floor(renderViewport.width / outputScale)}px`;
        canvas.style.height = `${Math.floor(renderViewport.height / outputScale)}px`;

        renderTask = page.render({
          annotationMode: AnnotationMode.ENABLE,
          canvas,
          viewport: renderViewport,
        });
        await renderTask.promise;

        if (active) {
          setViewerStatus("ready");
        }
      } catch (error) {
        if (!active) {
          return;
        }

        setViewerError(getViewerErrorMessage(error));
        setViewerStatus("error");
      }
    }

    void renderPage();

    return () => {
      active = false;
      renderTask?.cancel();
    };
  }, [pageNumber, pageWidth, pdfDocument]);

  const canGoPrevious = pageNumber > 1 && viewerStatus !== "loading";
  const canGoNext =
    pageCount > 0 && pageNumber < pageCount && viewerStatus !== "loading";

  return (
    <div className="custom-pdf-viewer">
      <div className="pdf-toolbar">
        <p className="pdf-toolbar-file" title={fileName}>
          {fileName}
        </p>
        <div className="pdf-page-controls" aria-label="PDF page navigation">
          <button
            type="button"
            className="pdf-page-button"
            onClick={() => setPageNumber((current) => Math.max(1, current - 1))}
            disabled={!canGoPrevious}
            aria-label="Previous PDF page"
          >
            <Chevron direction="left" />
            <span>Previous</span>
          </button>
          <p className="pdf-page-count" aria-live="polite">
            Page <strong>{pageCount > 0 ? pageNumber : "-"}</strong> of{" "}
            <strong>{pageCount > 0 ? pageCount : "-"}</strong>
          </p>
          <button
            type="button"
            className="pdf-page-button"
            onClick={() =>
              setPageNumber((current) => Math.min(pageCount, current + 1))
            }
            disabled={!canGoNext}
            aria-label="Next PDF page"
          >
            <span>Next</span>
            <Chevron direction="right" />
          </button>
        </div>
      </div>

      <div className="pdf-page-stage">
        <div className="pdf-page-slot" ref={pageSlotRef}>
          <canvas
            ref={canvasRef}
            className="pdf-page-canvas"
            role="img"
            aria-label={`Page ${pageNumber} of ${fileName}`}
          />

          {viewerStatus === "loading" || viewerStatus === "rendering" ? (
            <div className="pdf-viewer-state" aria-live="polite">
              <span className="spinner" aria-hidden="true" />
              <span>
                {viewerStatus === "loading"
                  ? "Opening document"
                  : `Rendering page ${pageNumber}`}
              </span>
            </div>
          ) : null}

          {viewerStatus === "error" ? (
            <div className="pdf-viewer-state pdf-viewer-error" role="alert">
              <strong>Could not render this PDF.</strong>
              <span>{viewerError}</span>
              <a href={url} target="_blank" rel="noreferrer">
                Open the PDF in a new tab
              </a>
            </div>
          ) : null}

          {isUpdating && viewerStatus === "ready" ? (
            <div className="pdf-update-overlay" aria-live="polite">
              <span className="spinner" aria-hidden="true" />
              <span>Updating preview</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

type ChevronProps = {
  direction: "left" | "right";
};

function Chevron({ direction }: ChevronProps) {
  return (
    <svg
      viewBox="0 0 20 20"
      width="16"
      height="16"
      aria-hidden="true"
      className={direction === "right" ? "chevron-right" : undefined}
    >
      <path
        d="m12.5 4-6 6 6 6"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function getViewerErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The document could not be displayed.";
}

export default PdfViewer;
