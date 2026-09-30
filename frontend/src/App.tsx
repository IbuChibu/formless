import { useEffect, useState } from "react";

type ConnectionStatus = "checking" | "connected" | "disconnected";

type HealthResponse = {
  status: string;
  service: string;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("checking");

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
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        setConnectionStatus("disconnected");
      }
    }

    void checkBackend();

    return () => controller.abort();
  }, []);

  const statusCopy = {
    checking: "Checking backend connection…",
    connected: "Backend connected",
    disconnected: "Backend unavailable",
  }[connectionStatus];

  return (
    <main className="page-shell">
      <section className="status-card" aria-live="polite">
        <p className="eyebrow">Formless</p>
        <h1>Foundation status</h1>
        <div className={`connection-status ${connectionStatus}`}>
          <span className="status-dot" aria-hidden="true" />
          <span>{statusCopy}</span>
        </div>
        <p className="endpoint">
          Health endpoint: <code>{apiBaseUrl}/health</code>
        </p>
      </section>
    </main>
  );
}

export default App;

