// Tela da mesa: o cliente escolhe os itens, faz o pedido e acompanha o robô.

const $ = (id) => document.getElementById(id);

const params = new URLSearchParams(location.search);
let mesa = parseInt(params.get("mesa") || readStore("mesa") || "0", 10) || null;
let cart = {};            // item -> quantidade
let trackingId = null;    // pedido que está sendo acompanhado
let state = null;
let names = {};
const rows = {};          // item -> elementos da linha do cardápio

$("brandMark").innerHTML = ROBOT_SVG;
$("routeRobot").innerHTML = ROBOT_SVG;

// ------------------------------------------------------------- telas
function show(view) {
  $("pickView").hidden = view !== "pick";
  $("menuView").hidden = view !== "menu";
  $("trackView").hidden = view !== "track";
  $("cartBar").hidden = view !== "menu";
  $("tableChip").hidden = !mesa;
  if (mesa) {
    $("tableChip").textContent = `Mesa ${mesa}`;
    $("routeTable").textContent = `Mesa ${mesa}`;
  }
}

function currentView() {
  if (!$("pickView").hidden) return "pick";
  if (!$("trackView").hidden) return "track";
  return "menu";
}

function setTable(n) {
  mesa = n;
  writeStore("mesa", String(n));
  const url = new URL(location.href);
  url.searchParams.set("mesa", n);
  history.replaceState(null, "", url);
  show("menu");
}

function buildTablePicker(count) {
  const grid = $("tableGrid");
  if (grid.childElementCount === count) return;
  grid.innerHTML = "";
  for (let n = 1; n <= count; n++) {
    const b = document.createElement("button");
    b.textContent = `Mesa ${n}`;
    b.addEventListener("click", () => setTable(n));
    grid.appendChild(b);
  }
}

// ----------------------------------------------------------- cardápio
function buildMenu(cardapio) {
  const list = $("menuList");
  list.innerHTML = "";
  cardapio.forEach((m) => {
    const li = document.createElement("li");
    li.className = "menu-row";
    li.innerHTML = `
      <span class="menu-icon" aria-hidden="true">${m.icone}</span>
      <div>
        <p class="menu-name">${m.nome}</p>
        <span class="menu-price">${money(m.preco)}</span>
      </div>
      <div class="stepper">
        <button type="button" aria-label="Tirar um ${m.nome}">−</button>
        <output aria-live="polite">0</output>
        <button type="button" aria-label="Adicionar um ${m.nome}">+</button>
      </div>`;
    const [minus, plus] = li.querySelectorAll("button");
    minus.addEventListener("click", () => changeQty(m.item, -1));
    plus.addEventListener("click", () => changeQty(m.item, +1));
    rows[m.item] = { li, minus, plus, out: li.querySelector("output"), price: li.querySelector(".menu-price"), menu: m };
    list.appendChild(li);
  });
}

function stockOf(item) {
  const m = state && state.cardapio.find((c) => c.item === item);
  return m && m.estoque !== null && m.estoque !== undefined ? m.estoque : Infinity;
}

function changeQty(item, delta) {
  const q = Math.min(Math.max((cart[item] || 0) + delta, 0), stockOf(item));
  if (q) cart[item] = q; else delete cart[item];
  renderMenu();
}

function renderMenu() {
  let count = 0;
  let total = 0;
  state.cardapio.forEach((m) => {
    const r = rows[m.item];
    if (!r) return;
    const stock = stockOf(m.item);
    if ((cart[m.item] || 0) > stock) {
      if (stock > 0) cart[m.item] = stock; else delete cart[m.item];
    }
    const q = cart[m.item] || 0;
    const out = stock <= 0;
    r.li.classList.toggle("is-out", out);
    r.price.textContent = out ? "Esgotado" : money(m.preco);
    r.out.textContent = q;
    r.minus.disabled = q === 0;
    r.plus.disabled = q >= stock;
    count += q;
    total += q * m.preco;
  });
  $("cartCount").textContent = count === 0 ? "Nenhum item escolhido" : count === 1 ? "1 item" : `${count} itens`;
  $("cartTotal").textContent = money(total);
  $("orderBtn").disabled = count === 0;

  const active = myOrders().find((o) => o.status !== "entregue" && o.status !== "recusado");
  const link = $("trackLink");
  link.hidden = !active;
  if (active) {
    link.textContent = `Acompanhar o pedido ${active.id}`;
    link.onclick = () => openTrack(active.id);
  }
}

function myOrders() {
  return state ? state.pedidos.filter((o) => o.mesa === mesa) : [];
}

$("orderBtn").addEventListener("click", async () => {
  const btn = $("orderBtn");
  btn.disabled = true;
  btn.textContent = "Enviando…";
  try {
    const res = await api.post("/api/pedido", { mesa, itens: cart });
    cart = {};
    openTrack(res.pedido);
  } catch (e) {
    toast(e.message);
  } finally {
    btn.textContent = "Fazer pedido";
    if (state) renderMenu();
  }
});

// ------------------------------------------------------ acompanhamento
const STAGES = {
  recebido: { pos: 0, reached: 1, msg: "Pedido confirmado. O robô já vai buscar seus itens." },
  validado: { pos: 0, reached: 1, msg: "Pedido confirmado. O robô já vai buscar seus itens." },
  em_coleta: { pos: 50, reached: 2, msg: "O robô está na bancada pegando o seu pedido." },
  em_entrega: { pos: 82, reached: 2, msg: "O robô está indo até a sua mesa." },
  entregue: { pos: 100, reached: 3, msg: "Seu pedido chegou. Bom apetite!" },
  recusado: { pos: 0, reached: 0, msg: "Um dos itens acabou e o pedido não foi feito. Escolha outra opção no cardápio." },
};

function openTrack(id) {
  trackingId = id;
  show("track");
  renderTrack();
}

function renderTrack() {
  const order = state && state.pedidos.find((o) => o.id === trackingId);
  $("trackTitle").textContent = `Pedido ${trackingId}`;
  const view = $("trackView");
  if (!order) {
    $("trackMsg").textContent = "Pedido enviado. Esperando a confirmação…";
    $("trackTime").textContent = "";
    $("trackItems").innerHTML = "";
    $("trackNote").hidden = true;
    moveRobot(0, 1);
    return;
  }
  const stage = STAGES[order.status] || STAGES.recebido;
  view.classList.toggle("is-refused", order.status === "recusado");
  $("route").hidden = order.status === "recusado";
  $("trackMsg").textContent = stage.msg;
  moveRobot(stage.pos, stage.reached);

  const done = order.status === "entregue";
  $("trackTime").innerHTML = order.status === "recusado" ? "" :
    `${done ? "Entregue em" : "Esperando há"} <strong>${clockText(order.decorrido_s)}</strong>`;
  $("trackNote").hidden = !(order.atrasado && !done && order.status !== "recusado");

  const counts = {};
  order.itens.forEach((i) => { counts[i] = (counts[i] || 0) + 1; });
  $("trackItems").innerHTML = Object.entries(counts)
    .map(([i, q]) => `<li>${q} × ${names[i] || i}</li>`).join("");
  $("newOrderBtn").textContent = order.status === "recusado" ? "Voltar ao cardápio" : "Fazer outro pedido";
}

function moveRobot(pos, reached) {
  $("routeRobot").style.left = `${pos}%`;
  $("routeDone").style.width = `${pos}%`;
  [...$("routeStops").children].forEach((li, i) => li.classList.toggle("is-reached", i < reached));
}

$("newOrderBtn").addEventListener("click", () => { trackingId = null; show("menu"); renderMenu(); });
$("tableChip").addEventListener("click", () => show("pick"));

// -------------------------------------------------------------- início
let menuBuilt = false;
poll((s) => {
  state = s;
  names = Object.fromEntries(s.cardapio.map((m) => [m.item, m.nome]));
  buildTablePicker(s.mesas);
  if (!menuBuilt) {
    buildMenu(s.cardapio);
    menuBuilt = true;
    show(mesa ? "menu" : "pick");
  }
  if (mesa && mesa > s.mesas) { mesa = null; show("pick"); }
  renderMenu();
  if (currentView() === "track") renderTrack();
});
