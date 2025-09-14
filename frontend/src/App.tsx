import { Link, NavLink, Route, Routes } from "react-router-dom";
import IncidentsPage from "./pages/IncidentsPage";
import IncidentDetailPage from "./pages/IncidentDetailPage";
import ServicesPage from "./pages/ServicesPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">AO</span>
          <span className="brand-text">
            <strong>Observability</strong>
            <em>AI Debug Console</em>
          </span>
        </Link>
        <nav>
          <NavLink to="/" end>
            Incidents
          </NavLink>
          <NavLink to="/services">Services</NavLink>
        </nav>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<IncidentsPage />} />
          <Route path="/incidents/:id" element={<IncidentDetailPage />} />
          <Route path="/services" element={<ServicesPage />} />
        </Routes>
      </main>
    </div>
  );
}
