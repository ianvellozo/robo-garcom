// Funções usadas pelas duas telas.

const ROBOT_SVG = `
<svg viewBox="0 0 64 64" aria-hidden="true">
  <line x1="32" y1="6" x2="32" y2="14" stroke="#0f2e2d" stroke-width="3" stroke-linecap="round"/>
  <circle cx="32" cy="5" r="3.5" fill="#f2b01e" stroke="#0f2e2d" stroke-width="2"/>
  <rect x="12" y="14" width="40" height="26" rx="10" fill="#ffffff" stroke="#0f2e2d" stroke-width="3"/>
  <circle cx="25" cy="27" r="3.5" fill="#0f2e2d"/>
  <circle cx="39" cy="27" r="3.5" fill="#0f2e2d"/>
  <rect x="18" y="42" width="28" height="12" rx="4" fill="#f2b01e" stroke="#0f2e2d" stroke-width="3"/>
  <line x1="8" y1="44" x2="56" y2="44" stroke="#0f2e2d" stroke-width="3" stroke-linecap="round"/>
  <circle cx="23" cy="58" r="4" fill="#0f2e2d"/>
  <circle cx="41" cy="58" r="4" fill="#0f2e2d"/>
</svg>`;

const api = {
  async estado() {
    const r = await fetch("/api/estado", { cache: "no-store" });
    if (!r.ok) throw new Error("sem resposta");
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.erro || "O sistema não respondeu. Confira se ele está rodando.");
    return data;
  },
};

const money = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function clockText(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function itemsText(list, names) {
  // ["cafe","cafe","suco"] -> "2 × Café, 1 × Suco"
  const counts = new Map();
  list.forEach((i) => counts.set(i, (counts.get(i) || 0) + 1));
  return [...counts].map(([i, q]) => `${q} × ${names[i] || i}`).join(", ");
}

let toastTimer;
function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.add("is-on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("is-on"), 3200);
}

// Busca o estado a cada segundo e avisa se o sistema cair.
function poll(onState) {
  const banner = document.getElementById("offline");
  async function tick() {
    try {
      const state = await api.estado();
      banner.hidden = true;
      onState(state);
    } catch (e) {
      banner.hidden = false;
    }
    setTimeout(tick, 1000);
  }
  tick();
}

function readStore(key) {
  try { return localStorage.getItem(key); } catch (e) { return null; }
}

function writeStore(key, value) {
  try { localStorage.setItem(key, value); } catch (e) { /* sem armazenamento: tudo bem */ }
}
