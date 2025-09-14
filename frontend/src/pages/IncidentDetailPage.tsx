import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Analysis, type Incident } from "../api";

export default function IncidentDetailPage() {
  const { id = "" } = useParams();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [inc, existing] = await Promise.all([
        api.getIncident(id),
        api.getAnalysis(id),
      ]);
      setIncident(inc);
      setAnalysis(existing);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incident");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runAnalyze() {
    if (!id) return;
    setAnalyzing(true);
    setError(null);
    try {
      setAnalysis(await api.analyzeIncident(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }

  if (loading) {
    return (
      <section className="page">
        <p className="muted">Loading incident…</p>
      </section>
    );
  }

  if (!incident) {
    return (
      <section className="page">
        <p className="banner error">{error ?? "Incident not found"}</p>
        <Link to="/">← Back to incidents</Link>
      </section>
    );
  }

  return (
    <section className="page">
      <p className="crumb">
        <Link to="/">Incidents</Link> / {incident.title}
      </p>

      <div className="page-head">
        <div>
          <h1>{incident.title}</h1>
          <p>{incident.summary ?? "No summary available."}</p>
        </div>
        <div className="actions">
          <button type="button" className="btn" onClick={() => void runAnalyze()} disabled={analyzing}>
            {analyzing ? "Analyzing…" : analysis ? "Re-analyze" : "Analyze with AI"}
          </button>
        </div>
      </div>

      {error && <p className="banner error">{error}</p>}

      <div className="detail-grid">
        <dl className="facts">
          <div>
            <dt>Status</dt>
            <dd>{incident.status}</dd>
          </div>
          <div>
            <dt>Severity</dt>
            <dd>{incident.severity}</dd>
          </div>
          <div>
            <dt>Detection rule</dt>
            <dd>{incident.detection_rule ?? "—"}</dd>
          </div>
          <div>
            <dt>Started</dt>
            <dd>{new Date(incident.started_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt>Affected services</dt>
            <dd>
              {incident.affected_services.length
                ? incident.affected_services.map((s) => s.display_name || s.name).join(", ")
                : "—"}
            </dd>
          </div>
        </dl>

        <article className="analysis-panel">
          <h2>AI analysis</h2>
          {!analysis && (
            <p className="muted">
              No analysis yet. Run Analyze to generate a root-cause hypothesis from correlated
              telemetry.
            </p>
          )}
          {analysis && (
            <>
              <p className="provider">
                {analysis.provider}
                {analysis.model ? ` · ${analysis.model}` : ""} · confidence {analysis.confidence}
              </p>
              <h3>Summary</h3>
              <p>{analysis.summary}</p>
              <h3>Root cause</h3>
              <p>{analysis.root_cause}</p>
              <h3>Recommendations</h3>
              <ul>
                {analysis.recommendations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          )}
        </article>
      </div>
    </section>
  );
}
