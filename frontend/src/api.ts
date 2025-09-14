const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export type Service = {
  id: string;
  name: string;
  display_name: string;
  environment: string;
  owner_team: string | null;
};

export type Incident = {
  id: string;
  title: string;
  status: string;
  severity: string;
  summary: string | null;
  detection_rule: string | null;
  started_at: string;
  affected_services: Service[];
};

export type Analysis = {
  id: string;
  provider: string;
  model: string | null;
  summary: string;
  root_cause: string;
  affected_services: string[];
  recommendations: string[];
  confidence: string;
  created_at: string;
};

export const api = {
  getServices: () => request<Service[]>("/api/v1/services"),
  getIncidents: () => request<Incident[]>("/api/v1/incidents"),
  getIncident: (id: string) => request<Incident>(`/api/v1/incidents/${id}`),
  analyzeIncident: (id: string) =>
    request<Analysis>(`/api/v1/incidents/${id}/analyze`, { method: "POST" }),
  getAnalysis: async (id: string): Promise<Analysis | null> => {
    const response = await fetch(`${API_BASE}/api/v1/incidents/${id}/analysis`);
    if (response.status === 404) return null;
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json();
  },
  runDetection: () => request<unknown>("/api/v1/detection/run", { method: "POST" }),
  health: () => request<{ status: string }>("/health"),
};
