import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Incident } from "../api";

function severityClass(severity: string): string {
  return `sev sev-${severity.toLowerCase()}`;
}

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setIncidents(await api.getIncidents());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function runDetection() {
    setDetecting(true);
    setError(null);
    try {
      await api.runDetection();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Detection failed");
    } finally {
      setDetecting(false);
    }
  }

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h1>Incidents</h1>
          <p>Open signals from rule detection across correlated services.</p>
        </div>
        <div className="actions">
          <button type="button" className="btn ghost" onClick={() => void load()} disabled={loading}>
            Refresh
          </button>
          <button type="button" className="btn" onClick={() => void runDetection()} disabled={detecting}>
            {detecting ? "Running…" : "Run detection"}
          </button>
        </div>
      </div>

      {error && <p className="banner error">{error}</p>}
      {loading && <p className="muted">Loading incidents…</p>}

      {!loading && incidents.length === 0 && (
        <p className="empty">
          No incidents yet. Start the synthetic generator, then run detection.
        </p>
      )}

      <ul className="incident-list">
        {incidents.map((incident) => (
          <li key={incident.id}>
            <Link to={`/incidents/${incident.id}`} className="incident-row">
              <div className="incident-main">
                <span className={severityClass(incident.severity)}>{incident.severity}</span>
                <strong>{incident.title}</strong>
                <span className="status">{incident.status}</span>
              </div>
              <div className="incident-meta">
                <span>{new Date(incident.started_at).toLocaleString()}</span>
                <span>
                  {incident.affected_services.map((s) => s.name).join(" · ") || "unscoped"}
                </span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
