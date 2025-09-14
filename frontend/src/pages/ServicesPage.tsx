import { useEffect, useState } from "react";
import { api, type Service } from "../api";

export default function ServicesPage() {
  const [services, setServices] = useState<Service[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        setServices(await api.getServices());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load services");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h1>Services</h1>
          <p>Registered demo services the platform correlates against.</p>
        </div>
      </div>

      {error && <p className="banner error">{error}</p>}
      {loading && <p className="muted">Loading services…</p>}

      {!loading && services.length === 0 && (
        <p className="empty">No services registered. Run the synthetic generator once.</p>
      )}

      <ul className="service-list">
        {services.map((service) => (
          <li key={service.id} className="service-row">
            <div>
              <strong>{service.display_name || service.name}</strong>
              <span className="mono">{service.name}</span>
            </div>
            <div className="service-meta">
              <span>{service.environment}</span>
              <span>{service.owner_team ?? "unassigned"}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
