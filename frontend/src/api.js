const BASE = import.meta.env.VITE_API_URL || "";
const KEY = import.meta.env.VITE_API_KEY || "";

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(KEY ? { "X-API-Key": KEY } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* لا يوجد جسم JSON */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

const qs = (params) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== "" && v !== null && v !== undefined && v !== false && v !== 0) p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  projects: (filters) => request(`/api/projects${qs(filters)}`),
  project: (id) => request(`/api/projects/${id}`),
  setProjectStatus: (id, status) =>
    request(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  categories: () => request("/api/categories"),
  draft: (id) => request(`/api/projects/${id}/draft`, { method: "POST" }),
  proposals: (status = "") => request(`/api/proposals${qs({ status })}`),
  patchProposal: (id, body) =>
    request(`/api/proposals/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  proposalToTelegram: (id) => request(`/api/proposals/${id}/telegram`, { method: "POST" }),
  refresh: () => request("/api/refresh", { method: "POST" }),
  refreshStatus: () => request("/api/refresh/status"),
};
