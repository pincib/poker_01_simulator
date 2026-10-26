import { renderGameCoach } from "./coach_hud.js";

const SUITS = {
  s: { symbol: "♠", name: "spades", color: "#202a23" },
  h: { symbol: "♥", name: "hearts", color: "#c34352" },
  d: { symbol: "♦", name: "diamonds", color: "#287da8" },
  c: { symbol: "♣", name: "clubs", color: "#27784d" },
};
const SEAT_LAYOUT = ["seat--hero", "seat--top", "seat--top-left", "seat--top-right", "seat--bottom-left", "seat--bottom-right"];
const DEFAULT_SEATS = ["You", "Aggro Alex", "Nitty Norman", "Calling Kevin", "Solver Sam", "Aggro Alex"];

export function renderGameState(state) {
  if (!state?.started) {
    renderIdleTable();
    renderGameCoach(null, null);
    return;
  }

  const seats = document.getElementById("table-seats");
  seats.replaceChildren(...state.seats.map((seat, index) => createSeat(seat, SEAT_LAYOUT[index])));
  document.getElementById("table-meta").textContent = state.table_label;
  document.getElementById("table-pot").textContent = formatMoney(state.pot);
  document.getElementById("table-street").textContent = state.street.toUpperCase();
  document.getElementById("table-spr").textContent = state.spr_value == null ? "—" : Number(state.spr_value).toFixed(1);
  document.getElementById("community-cards").replaceChildren(...renderBoard(state.board));
  document.getElementById("community-cards").setAttribute(
    "aria-label",
    state.board.length ? `Community cards: ${state.board.map(readableCard).join(", ")}` : "No community cards dealt",
  );
  document.getElementById("hero-stack").textContent = formatMoney(state.hero_stack);
  const turnLabel = state.hand_complete ? "Hand complete" : state.current_player_id === "hero" ? "Your turn" : "Opponent action";
  document.getElementById("table-hand-label").textContent = turnLabel;
  const message = state.outcome || (state.current_player_id === "hero"
    ? `Your action · ${state.hero_position}`
    : state.hand_complete ? "Hand complete" : "Opponent action");
  document.getElementById("table-message").textContent = message;
  document.getElementById("poker-table").setAttribute("aria-label", `Texas Hold’em table, ${state.street}, pot ${formatMoney(state.pot)}`);
  renderGameCoach(state.coach, state.coach_note, state.hand_complete, state.coach_context);
}

function renderIdleTable() {
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
    profile: index ? "Training opponent" : "You",
  }, SEAT_LAYOUT[index])));
  document.getElementById("table-pot").textContent = "$0.00";
  document.getElementById("table-street").textContent = "Waiting";
  document.getElementById("table-spr").textContent = "—";
  document.getElementById("community-cards").replaceChildren(...renderBoard([]));
  document.getElementById("hero-stack").textContent = "$200.00";
  document.getElementById("table-hand-label").textContent = "Waiting for a hand";
  document.getElementById("table-message").textContent = "Deal a hand to begin. Your cards stay private.";
  document.getElementById("poker-table").setAttribute("aria-label", "Six-handed Texas Hold’em table. Waiting to deal.");
}

function createSeat(player, layout) {
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
    dealer.setAttribute("aria-label", "Dealer button");
    identity.append(dealer);
  }

  const stack = document.createElement("span");
  stack.className = "seat-stack";
  stack.textContent = formatMoney(player.stack);
  const status = document.createElement("span");
  status.className = "seat-status";
  status.textContent = !player.active ? "Folded" : player.is_all_in ? "All-in" : player.is_turn ? "To act" : player.street_bet ? `Bet ${formatMoney(player.street_bet)}` : "";

  const cards = document.createElement("div");
  cards.className = "seat-cards";
  cards.setAttribute("aria-label", player.hole_cards?.length
    ? `${player.name} cards: ${player.hole_cards.map(readableCard).join(", ")}`
    : player.cards_hidden ? `${player.name} cards face down` : "No cards dealt");
  cards.append(...(player.hole_cards?.length
    ? player.hole_cards.map(createPlayingCard)
    : player.cards_hidden ? [createCardBack(), createCardBack()] : []));
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
  const labelRank = ({ T: "Ten", J: "Jack", Q: "Queen", K: "King", A: "Ace" })[rankCode] || rankCode;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("playing-card");
  svg.setAttribute("viewBox", "0 0 64 88");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${labelRank} of ${suit.name}`);
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
  const rank = ({ T: "10", J: "Jack", Q: "Queen", K: "King", A: "Ace" })[code[0].toUpperCase()] || code[0];
  return `${rank} of ${SUITS[code[1].toLowerCase()].name}`;
}

export function formatMoney(amount) {
  return `$${Number(amount || 0).toFixed(2)}`;
}
