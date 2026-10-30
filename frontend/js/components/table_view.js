import { renderGameCoach } from "./coach_hud.js";

const SUITS = {
  s: { symbol: "♠", name: "espadas", color: "#202a23" },
  h: { symbol: "♥", name: "copas", color: "#c34352" },
  d: { symbol: "♦", name: "ouros", color: "#287da8" },
  c: { symbol: "♣", name: "paus", color: "#27784d" },
};
const SEAT_LAYOUT = ["seat--hero", "seat--top", "seat--top-left", "seat--top-right", "seat--bottom-left", "seat--bottom-right"];
const DEFAULT_SEATS = ["Você", "Alex agressivo", "Norman conservador", "Kevin pagador", "Blair equilibrado", "Alex agressivo"];

export function renderGameState(state) {
  if (!state?.started) {
    renderIdleTable();
    renderGameCoach(null, null);
    return;
  }

  const seats = document.getElementById("table-seats");
  seats.replaceChildren(...state.seats.map((seat, index) => createSeat(seat, SEAT_LAYOUT[index], state.hole_card_count || 2)));
  const variantLabel = state.variant_label || (state.variant_id === "pot_limit_omaha" ? "Omaha Pot-Limit" : "Texas Hold’em");
  document.getElementById("table-title").textContent = variantLabel;
  document.getElementById("table-meta").textContent = state.table_label;
  document.getElementById("table-pot").textContent = formatMoney(state.pot);
  document.getElementById("table-blinds").textContent = `${formatMoney(state.small_blind)}/${formatMoney(state.big_blind)}`;
  document.getElementById("table-street").textContent = displayStreet(state.street);
  document.getElementById("table-spr").textContent = state.spr_value == null ? "—" : Number(state.spr_value).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  document.getElementById("community-cards").replaceChildren(...renderBoard(state.board));
  document.getElementById("community-cards").setAttribute(
    "aria-label",
    state.board.length ? `Cartas comunitárias: ${state.board.map(readableCard).join(", ")}` : "Ainda não há cartas comunitárias",
  );
  document.getElementById("hero-stack").textContent = formatMoney(state.hero_stack);
  const turnLabel = state.hand_complete ? "Mão concluída" : state.current_player_id === "hero" ? "Sua vez" : "Ação do adversário";
  document.getElementById("table-hand-label").textContent = turnLabel;
  const message = state.outcome || (state.current_player_id === "hero"
    ? `Sua ação · ${state.hero_position}`
    : state.hand_complete ? "Mão concluída" : "Ação do adversário");
  document.getElementById("table-message").textContent = message;
  renderHandResult(state);
  updateTableReading(state);
  document.getElementById("table-message").dataset.state = "";
  document.getElementById("poker-table").setAttribute(
    "aria-label", `Mesa de ${variantLabel}, ${displayStreet(state.street)}, blinds ${formatMoney(state.small_blind)}/${formatMoney(state.big_blind)}, pote ${formatMoney(state.pot)}`,
  );
  renderGameCoach(state.coach, state.coach_note, state.hand_complete, state.coach_context, state.coach_feedback);
}

function renderIdleTable() {
  const selectedVariant = document.getElementById("game-variant");
  const variantId = selectedVariant?.value || "texas_holdem";
  const variantLabel = selectedVariant?.selectedOptions?.[0]?.textContent || "Texas Hold’em";
  document.getElementById("table-title").textContent = variantLabel;
  document.getElementById("table-meta").textContent = `6-max · ${variantId === "pot_limit_omaha" ? "Pot-limit" : "No-Limit"} · $1/$2`;
  const seats = document.getElementById("table-seats");
  seats.replaceChildren(...DEFAULT_SEATS.map((name, index) => createSeat({
    id: index ? `seat-${index}` : "hero",
    name,
    position: index ? "SEAT" : "BTN",
    stack: 200,
    active: true,
    is_hero: index === 0,
    is_turn: false,
    is_button: index === 0,
    cards_hidden: true,
    hole_cards: [],
    profile: index ? "Adversário de treino" : "Você",
  }, SEAT_LAYOUT[index], variantId === "pot_limit_omaha" ? 4 : 2)));
  document.getElementById("table-pot").textContent = "$0.00";
  document.getElementById("table-blinds").textContent = "$1.00/$2.00";
  document.getElementById("table-street").textContent = "Aguardando";
  document.getElementById("table-spr").textContent = "—";
  document.getElementById("community-cards").replaceChildren(...renderBoard([]));
  document.getElementById("hero-stack").textContent = "$200.00";
  document.getElementById("table-hand-label").textContent = "Aguardando uma mão";
  document.getElementById("table-message").textContent = "Distribua uma mão para começar. Suas cartas ficam privadas.";
  renderHandResult(null);
  updateTableReading(null);
  document.getElementById("poker-table").setAttribute("aria-label", `Mesa de ${variantLabel} com seis jogadores. Aguardando distribuição.`);
}

function updateTableReading(state) {
  const street = ({ preflop: "pré-flop", flop: "flop", turn: "turn", river: "river", showdown: "showdown" })[state?.street] || "pré-flop";
  const position = state?.hero_position || "sua posição";
  const facing = Number(state?.amount_to_call || 0);
  document.getElementById("reading-context").textContent = `Dica de pensamento · ${street}`;
  document.getElementById("reading-position").textContent = state
    ? `Você está em ${position}. Considere quantos adversários ainda podem agir e a informação que terá nas próximas streets.`
    : "Sua posição determina quantos jogadores ainda podem agir e quanta informação você terá nas próximas streets.";
  document.getElementById("reading-action").textContent = state
    ? facing > 0
      ? `Há ${formatMoney(facing)} para pagar. Repare em quem colocou fichas e se o preço compensa diante da faixa adversária.`
      : "Ninguém está cobrando para continuar agora. Observe quem ainda pode agir antes de escolher entre check e aposta."
    : "Repare em quem já colocou fichas e no preço para continuar. A força da faixa adversária muda com a posição e a ação.";
  document.getElementById("reading-question").textContent = facing > 0
    ? `com ${formatMoney(facing)} para pagar, minha equity estimada justifica continuar?`
    : "que cartas futuras podem mudar meu plano — e quem ainda pode agir?";
}

function displayStreet(street) {
  return ({ preflop: "Pré-flop", flop: "Flop", turn: "Turn", river: "River", showdown: "Showdown" })[street] || "Aguardando";
}

function renderHandResult(state) {
  const panel = document.getElementById("coach-hand-result");
  const summary = document.getElementById("coach-hand-result-summary");
  const detail = document.getElementById("coach-hand-result-detail");
  panel.hidden = true;
  summary.textContent = "";
  detail.textContent = "";
  if (!state?.hand_complete || !Array.isArray(state.winners) || !state.winners.length) return;

  const names = Object.fromEntries((state.seats || []).map((seat) => [seat.id, seat.name || seat.id]));
  const descriptions = state.showdown_descriptions || {};
  const winningHands = state.winning_hands || {};
  const awards = Array.isArray(state.pot_awards) ? state.pot_awards : [];
  const reasons = [];

  if (Object.keys(descriptions).length) {
    const relevantAwards = awards.length ? awards : [{ label: "Main Pot", winner_ids: state.winners }];
    relevantAwards.forEach((award) => {
      const winners = (award.winner_ids || []).map((id) => {
        const classification = descriptions[id];
        if (!classification) return null;
        const cards = Array.isArray(winningHands[id]) ? ` (${winningHands[id].join(" ")})` : "";
        return `${names[id] || id}: ${classification}${cards}`;
      }).filter(Boolean);
      if (winners.length) reasons.push(`${localizePotLabel(award.label)}: ${winners.join("; ")}`);
    });
  } else {
    const winnerNames = state.winners.map((id) => names[id] || id);
    const otherNames = (state.seats || []).filter((seat) => !state.winners.includes(seat.id)).map((seat) => seat.name || seat.id);
    const reason = `Mão encerrada por fold: ${winnerNames.join(" e ")} levou${winnerNames.length > 1 ? "ram" : ""} o pote porque ${otherNames.length ? otherNames.join(" e ") : "os demais jogadores"} desistiram antes do showdown.`;
    reasons.push(reason);
  }

  const winnerNames = state.winners.map((id) => names[id] || id);
  summary.textContent = `${winnerNames.join(" e ")} ganhou${winnerNames.length > 1 ? "ram" : ""} ${formatMoney(state.pot)}.`;
  detail.textContent = reasons.join(" · ");
  panel.hidden = false;
}

function localizePotLabel(label) {
  if (label === "Main Pot") return "Pote principal";
  if (label === "Uncalled return") return "Devolução de aposta não paga";
  const sidePot = /^Side Pot (\d+)$/.exec(label || "");
  return sidePot ? `Pote paralelo ${sidePot[1]}` : label || "Pote";
}

function createSeat(player, layout, holeCardCount) {
  const seat = document.createElement("div");
  seat.className = `seat ${layout}`;
  seat.dataset.folded = String(!player.active);
  seat.dataset.turn = String(Boolean(player.is_turn));
  const identity = document.createElement("div");
  identity.className = "seat-line";
  const name = document.createElement("span");
  name.className = "seat-name";
  name.textContent = player.name;
  identity.append(name);
  const position = document.createElement("span");
  position.className = "position-tag";
  position.textContent = player.position || "";
  identity.append(position);
  if (player.is_button) {
    const dealer = document.createElement("span");
    dealer.className = "dealer-tag";
    dealer.textContent = "D";
    dealer.setAttribute("aria-label", "Botão do dealer");
    identity.append(dealer);
  }

  const stack = document.createElement("span");
  stack.className = "seat-stack";
  stack.textContent = formatMoney(player.stack);
  const status = document.createElement("span");
  status.className = "seat-status";
  status.textContent = !player.active ? "Desistiu" : player.is_all_in ? "All-in" : player.is_turn ? "A agir" : player.street_bet ? `Aposta ${formatMoney(player.street_bet)}` : "";

  const cards = document.createElement("div");
  cards.className = "seat-cards";
  cards.dataset.count = String(player.hole_cards?.length || (player.cards_hidden ? holeCardCount : 0));
  cards.setAttribute("aria-label", player.hole_cards?.length
    ? `Cartas de ${player.name}: ${player.hole_cards.map(readableCard).join(", ")}`
    : player.cards_hidden ? `Cartas de ${player.name} viradas para baixo` : "Nenhuma carta distribuída");
  cards.append(...(player.hole_cards?.length
    ? player.hole_cards.map(createPlayingCard)
    : player.cards_hidden ? Array.from({ length: holeCardCount }, createCardBack) : []));
  seat.append(identity, stack, status, cards);
  return seat;
}

function renderBoard(board) {
  const cards = Array.isArray(board) ? board : [];
  return Array.from({ length: 5 }, (_, index) => cards[index] ? createPlayingCard(cards[index]) : createEmptyCard());
}

function createPlayingCard(code) {
  const rankCode = code[0].toUpperCase();
  const suit = SUITS[code[1].toLowerCase()];
  const rank = ({ T: "10", J: "J", Q: "Q", K: "K", A: "A" })[rankCode] || rankCode;
  const labelRank = ({ T: "Dez", J: "Valete", Q: "Dama", K: "Rei", A: "Ás" })[rankCode] || rankCode;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("playing-card");
  svg.setAttribute("viewBox", "0 0 64 88");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${labelRank} de ${suit.name}`);
  const rect = svgElement("rect", { x: 1, y: 1, width: 62, height: 86, rx: 6, fill: "#f3f2e8", stroke: "#d7e0d5", "stroke-width": 2 });
  const cornerRank = svgElement("text", { x: 7, y: 21, fill: suit.color, "font-size": 17, "font-family": "Barlow Semi Condensed, sans-serif" });
  cornerRank.textContent = rank;
  const cornerSuit = svgElement("text", { x: 8, y: 35, fill: suit.color, "font-size": 13 });
  cornerSuit.textContent = suit.symbol;
  const center = svgElement("text", { x: 32, y: 61, fill: suit.color, "font-size": 32, "text-anchor": "middle" });
  center.textContent = suit.symbol;
  svg.append(rect, cornerRank, cornerSuit, center);
  return svg;
}

function createEmptyCard() {
  const slot = document.createElement("span");
  slot.className = "card-empty";
  slot.setAttribute("aria-hidden", "true");
  return slot;
}

function createCardBack() {
  const card = document.createElement("span");
  card.className = "card-back";
  card.setAttribute("aria-hidden", "true");
  return card;
}

function svgElement(name, attributes) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function readableCard(code) {
  const rank = ({ T: "10", J: "Valete", Q: "Dama", K: "Rei", A: "Ás" })[code[0].toUpperCase()] || code[0];
  return `${rank} de ${SUITS[code[1].toLowerCase()].name}`;
}

export function formatMoney(amount) {
  return `$${Number(amount || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
