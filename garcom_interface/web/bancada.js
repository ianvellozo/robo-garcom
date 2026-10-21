// Tela da bancada: o funcionário vê o que colocar na bandeja, confirma e ajusta o estoque.

const $ = (id) => document.getElementById(id);

const station = new URLSearchParams(location.search).get("estacao");  // opcional: só uma estação
let state = null;
let names = {};
let shownTicket = "";     // evita redesenhar a mesma comanda a cada segundo
const confirming = new Set();

$("brandMark").innerHTML = ROBOT_SVG;

const FLOOR_STATUS = {
  recebido: "Recebido",
  validado: "Esperando a próxima viagem",
  em_coleta: "Robô na bancada",
  em_entrega: "Robô indo para esta mesa",
  entregue: "Entregue",
  recusado: "Recusado (faltou item)",
};

// ------------------------------------------------------------ comanda
function pendingPickups() {
  return state.coletas.filter((c) => (!station || c.estacao === station) && !confirming.has(keyOf(c)));
}

const keyOf = (c) => `${c.viagem}:${c.estacao}`;

function renderTickets() {
  const area = $("ticketArea");
  const list = pendingPickups();
  if (!list.length) {
    if (shownTicket !== "none") {
      area.innerHTML = `
        <div class="empty">
          <strong>Nenhum robô na bancada</strong>
          Quando o robô chegar, a lista do que colocar na bandeja aparece aqui.
        </div>`;
      shownTicket = "none";
    }
    return;
  }
  const c = list[0];
  const key = `${keyOf(c)}|${list.length}`;
  if (key !== shownTicket) {
    const more = list.length - 1;
    const tables = [...new Set(c.linhas.map((l) => l.mesa))];
    const lines = c.linhas.length > 1 ? `
          <p class="ticket-split-title">Separe na bandeja:</p>
          <ul class="ticket-split">
            ${c.linhas.map((l) => `<li><span>Mesa ${l.mesa}</span><span>${l.itens.map((i) => `${i.qtd} × ${names[i.item] || i.item}`).join(", ")}</span></li>`).join("")}
          </ul>` : "";
    area.innerHTML = `
      <div class="ticket-wrap ${more ? "has-more" : ""}">
        <article class="ticket">
          <div class="ticket-head"><span>Viagem ${c.viagem}</span><span>${tables.length === 1 ? `Mesa ${tables[0]}` : `${tables.length} mesas`}</span></div>
          <p class="ticket-station">${c.estacao_nome}</p>
          <ul class="ticket-items">
            ${c.itens.map((i) => `<li><span class="qty">${i.qtd}</span><span>× ${names[i.item] || i.item}</span></li>`).join("")}
          </ul>
          ${lines}
          <p class="ticket-wait" id="ticketWait"></p>
          <button class="btn-main" id="readyBtn">Bandeja pronta</button>
          <p class="ticket-hint">ou aperte Enter</p>
        </article>
      </div>
      ${more ? `<p class="more-waiting">${more === 1 ? "Mais 1 bandeja para montar" : `Mais ${more} bandejas para montar`}</p>` : ""}`;
    $("readyBtn").addEventListener("click", () => confirmPickup(c));
    shownTicket = key;
  }
  $("ticketWait").textContent = `Robô esperando há ${clockText(c.esperando_s)}`;
}

async function confirmPickup(c) {
  const k = keyOf(c);
  if (confirming.has(k)) return;
  confirming.add(k);
  shownTicket = "";
  renderTickets();
  try {
    await api.post("/api/bandeja_pronta", { viagem: c.viagem, estacao: c.estacao });
    toast(`Bandeja da viagem ${c.viagem} liberada`);
  } catch (e) {
    toast(e.message);
  } finally {
    setTimeout(() => confirming.delete(k), 3000);
  }
}

document.addEventListener("keydown", (ev) => {
  if (ev.key !== "Enter" || $("stockDialog").open) return;
  if (ev.target.closest && ev.target.closest("button, input")) return;
  const list = state ? pendingPickups() : [];
  if (list.length) confirmPickup(list[0]);
});

function floorStatus(o) {
  if (o.status === "em_entrega" && o.paradas_antes > 0) {
    return `Na bandeja, ${o.paradas_antes === 1 ? "1 mesa" : `${o.paradas_antes} mesas`} antes desta`;
  }
  if (o.status === "em_coleta" && o.viagem) return `Viagem ${o.viagem}, robô nas bancadas`;
  return FLOOR_STATUS[o.status] || o.status;
}

// ----------------------------------------------------------- viagem
// aviso quando o laser vê algo no caminho do robô
const NAV_ALERTS = {
  obstaculo: { cls: "", text: "Robô parado: tem algo no caminho." },
  sem_caminho: { cls: "", text: "Robô esperando: o caminho está bloqueado." },
  desviando: { cls: "is-soft", text: "Robô desviando de um obstáculo." },
};

function navAlert() {
  const a = state.robo && NAV_ALERTS[state.robo.estado];
  if (!a) return "";
  const time = state.robo.estado === "desviando" ? "" : ` <span>(${clockText(state.robo.ha_s)})</span>`;
  return `<p class="trip-alert ${a.cls}" role="status">${a.text}${time}</p>`;
}

function renderTrip() {
  const t = state.viagem;
  const panel = $("tripPanel");
  if (!t || t.terminou) {
    const waiting = state.pedidos.some((o) => o.status === "validado");
    panel.innerHTML = `<h2>Robô</h2><p class="trip-idle">${waiting ? "Juntando os pedidos para a próxima viagem." : "Na base, esperando pedidos."}</p>${navAlert()}`;
    return;
  }
  panel.innerHTML = `
    <h2>Viagem ${t.id}</h2>
    <p class="trip-meta">${t.pedidos.length === 1 ? "1 pedido" : `${t.pedidos.length} pedidos`}, cerca de ${clockText(t.estimado_s)}</p>
    ${navAlert()}
    <ol class="trip-stops">
      ${t.paradas.map((p, i) => `<li class="${i < t.atual ? "is-past" : i === t.atual ? "is-now" : ""}">${p.nome}</li>`).join("")}
    </ol>`;
}

// ------------------------------------------------------ pedidos do salão
function renderFloor() {
  const orders = state.pedidos.slice(0, 14);
  const list = $("floorList");
  if (!orders.length) {
    list.innerHTML = `<li class="floor-empty">Nenhum pedido ainda.</li>`;
    return;
  }
  // os mais antigos (mais perto de atrasar) primeiro
  const active = orders.filter((o) => o.status !== "entregue" && o.status !== "recusado")
    .sort((a, b) => b.decorrido_s - a.decorrido_s);
  const finished = orders.filter((o) => o.status === "entregue" || o.status === "recusado");
  list.innerHTML = [...active, ...finished].map((o) => {
    let cls = "";
    let time = `${clockText(o.decorrido_s)} de ${clockText(o.prazo_s)}`;
    if (o.status === "entregue") { cls = "is-done"; time = clockText(o.decorrido_s); }
    else if (o.status === "recusado") { cls = "is-refused"; time = ""; }
    else if (o.atrasado) { cls = "is-late"; time = `Atrasado ${clockText(o.decorrido_s)}`; }
    else if (o.alerta) { cls = "is-warn"; }
    return `
      <li class="floor-row ${cls}">
        <span class="who">Mesa ${o.mesa}, pedido ${o.id}</span>
        <span class="time">${time}</span>
        <span class="what">${floorStatus(o)}: ${itemsText(o.itens, names)}</span>
      </li>`;
  }).join("");
}

// ------------------------------------------------------------- estoque
function openStock() {
  const list = $("stockList");
  list.innerHTML = "";
  state.cardapio.forEach((m) => {
    const li = document.createElement("li");
    li.className = "stock-row";
    li.dataset.item = m.item;
    li.dataset.original = m.estoque ?? 0;
    li.innerHTML = `
      <div>
        <span class="stock-name">${m.icone} ${m.nome}</span>
        <span class="stock-low"></span>
      </div>
      <div class="stepper">
        <button type="button" aria-label="Tirar um ${m.nome}">−</button>
        <input type="number" min="0" max="999" inputmode="numeric" value="${m.estoque ?? 0}" aria-label="Quantidade de ${m.nome}">
        <button type="button" aria-label="Adicionar um ${m.nome}">+</button>
      </div>`;
    const [minus, plus] = li.querySelectorAll("button");
    const input = li.querySelector("input");
    const update = () => {
      const v = Math.max(0, parseInt(input.value, 10) || 0);
      li.classList.toggle("is-changed", String(v) !== li.dataset.original);
      li.querySelector(".stock-low").textContent = v === 0 ? "Esgotado" : v <= 2 ? "Acabando" : "";
    };
    minus.addEventListener("click", () => { input.value = Math.max(0, (parseInt(input.value, 10) || 0) - 1); update(); });
    plus.addEventListener("click", () => { input.value = (parseInt(input.value, 10) || 0) + 1; update(); });
    input.addEventListener("input", update);
    update();
    list.appendChild(li);
  });
  $("stockDialog").showModal();
}

$("stockBtn").addEventListener("click", () => { if (state) openStock(); });

$("stockForm").addEventListener("submit", async (ev) => {
  if (ev.submitter && ev.submitter.value !== "save") return;
  ev.preventDefault();
  const changed = [...document.querySelectorAll(".stock-row.is-changed")];
  try {
    for (const li of changed) {
      const quantidade = Math.max(0, parseInt(li.querySelector("input").value, 10) || 0);
      await api.post("/api/estoque", { item: li.dataset.item, quantidade });
    }
    $("stockDialog").close();
    toast(changed.length ? "Estoque atualizado" : "Nada foi alterado");
  } catch (e) {
    toast(e.message);
  }
});

// -------------------------------------------------------------- início
function tickClock() {
  $("clock").textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}
tickClock();
setInterval(tickClock, 10000);

poll((s) => {
  state = s;
  names = Object.fromEntries(s.cardapio.map((m) => [m.item, m.nome]));
  if (station) $("benchTitle").textContent = s.estacoes[station] || "Bancada";
  renderTickets();
  renderTrip();
  renderFloor();
});
