const BASE = import.meta.env.VITE_API_URL || "";
const KEY = import.meta.env.VITE_API_KEY || "";

async function request(path) {
  const res = await fetch(BASE + path, {
    headers: KEY ? { "X-API-Key": KEY } : {},
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

export const api = {
  recent: () => request("/api/recent"),
};
