import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

type AssistantSideDrawerProps = {
  children: ReactNode;
  eyebrow: string;
  returnFocusId: string;
  title: string;
  onClose: () => void;
};

export default function AssistantSideDrawer({
  children,
  eyebrow,
  returnFocusId,
  title,
  onClose,
}: AssistantSideDrawerProps) {
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    panelRef.current?.focus();
    return () => {
      window.requestAnimationFrame(() => {
        document.getElementById(returnFocusId)?.focus();
      });
    };
  }, [returnFocusId]);

  return (
    <div className="assistant-side-drawer-layer">
      <button
        className="assistant-side-drawer-backdrop"
        type="button"
        aria-label={`Close ${title}`}
        onClick={onClose}
      />
      <section
        ref={panelRef}
        className="assistant-side-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="assistant-side-drawer-heading"
        tabIndex={-1}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            onClose();
          }
        }}
      >
        <div className="assistant-side-drawer-heading">
          <div>
            <span>{eyebrow}</span>
            <h3 id="assistant-side-drawer-heading">{title}</h3>
          </div>
          <button type="button" aria-label={`Close ${title}`} onClick={onClose}>
            ×
          </button>
        </div>
        <div className="assistant-side-drawer-content">{children}</div>
      </section>
    </div>
  );
}
