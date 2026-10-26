import {
  initializeCoachHud,
  refreshSessionReview,
  renderBetPurpose,
  renderCoachSnapshot,
} from "./components/coach_hud.js";
import { initializeActionBar, renderActionBar, setActionPending, showActionError } from "./components/action_bar.js";
import { renderGameState } from "./components/table_view.js";

const status = document.querySelector("#service-status");
const gameVariantSelect = document.getElementById("game-variant");
let activeVariantId = "texas_holdem";
let apiConfig = null;
let gameSnapshot = null;

async function loadServiceStatus() {
  status.dataset.state = "loading";
  status.lastElementChild.textContent = "Connecting";

  try {
    const response = await fetch("/api/health", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Server returned ${response.status}`);
    const health = await response.json();
    const configResponse = await fetch("/api/config", { headers: { Accept: "application/json" } });
    if (!configResponse.ok) throw new Error(`Configuration returned ${configResponse.status}`);
    const config = await configResponse.json();
    apiConfig = config;
    configureVariantSelector(config);

    document.title = config.name;
    status.dataset.state = "online";
    status.lastElementChild.textContent = health.status === "ok" ? "Local server ready" : "Service unavailable";
  } catch {
    status.dataset.state = "offline";
    status.lastElementChild.textContent = "Server unavailable";
  }
}

initializeCoachHud();
initializeActionBar({ onAction: submitGameAction });
document.getElementById("deal-button").addEventListener("click", startHand);
gameVariantSelect.addEventListener("change", updateVariantPreview);
loadServiceStatus().finally(loadGameState);

// Game integrations can submit decision context without depending on HUD markup.
window.pokerCoach = Object.freeze({
  async analyze(context) {
    const snapshot = await postCoachRequest("/api/coach/analyze", context);
    renderCoachSnapshot(snapshot);
    return snapshot;
  },
  async classifyBet(context) {
    const result = await postCoachRequest("/api/coach/action-purpose", context);
    renderBetPurpose(result);
    return result;
  },
  async recordHand(hand) {
    const result = await postCoachRequest("/api/session/hands", hand);
    window.dispatchEvent(new CustomEvent("poker:hand-recorded", { detail: result }));
    return result;
  },
});

async function postCoachRequest(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Coach request failed (${response.status}).`);
  return result;
}

async function loadGameState() {
  try {
    const response = await fetch("/api/game/state", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("The table state could not be loaded.");
    applyGameState(await response.json());
  } catch (error) {
    showActionError(error.message || "The local game server is unavailable.");
  }
}

async function startHand() {
  const button = document.getElementById("deal-button");
  button.disabled = true;
  button.textContent = "Dealing…";
  clearActionMessage();
  try {
    const state = await postCoachRequest("/api/game/start", { variant: gameVariantSelect.value });
    applyGameState(state);
  } catch (error) {
    button.disabled = false;
    button.textContent = "Deal hand";
    showActionError(error.message || "The hand could not be dealt.");
  }
}

async function submitGameAction(action, amount) {
  if (!action) return;
  setActionPending(true);
  try {
    const state = await postCoachRequest("/api/game/action", { action, amount, variant: activeVariantId });
    applyGameState(state);
    if (state.hand_complete) await refreshSessionReview();
  } catch (error) {
    setActionPending(false);
    showActionError(error.message || "That action could not be applied.");
  }
}

function applyGameState(state) {
  gameSnapshot = state;
  if (state.started && state.variant_id) activeVariantId = state.variant_id;
  gameVariantSelect.disabled = Boolean(state.started && !state.hand_complete);
  if (state.started && state.variant_id) gameVariantSelect.value = state.variant_id;
  renderGameState(state);
  updateVariantPreview();
  renderActionBar(state);
  const dealButton = document.getElementById("deal-button");
  dealButton.disabled = !state.started || !state.hand_complete;
  if (!state.started) {
    dealButton.disabled = false;
    dealButton.textContent = "Deal hand";
  } else if (state.hand_complete && state.hero_stack <= 0) {
    dealButton.textContent = "Rebuy and deal";
  } else if (state.hand_complete) {
    dealButton.textContent = "Next hand";
  } else {
    dealButton.textContent = "Hand in progress";
  }
  setActionPending(false);
  window.dispatchEvent(new CustomEvent("poker:game-state", { detail: state }));
}

function configureVariantSelector(config) {
  const variants = config.variants || {};
  const selected = gameVariantSelect.value || config.default_variant;
  gameVariantSelect.replaceChildren(...Object.entries(variants).map(([id, rules]) => {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = rules.label;
    return option;
  }));
  gameVariantSelect.value = variants[selected] ? selected : config.default_variant;
  gameVariantSelect.disabled = false;
  updateVariantPreview();
}

function updateVariantPreview() {
  const selected = apiConfig?.variants?.[gameVariantSelect.value];
  if (!selected) return;
  const handInProgress = Boolean(gameSnapshot?.started && !gameSnapshot.hand_complete);
  if (handInProgress) return;
  const nextHand = Boolean(gameSnapshot?.started && gameSnapshot.hand_complete);
  const variantId = gameVariantSelect.value;
  document.getElementById("variant-preview").textContent = variantId === "pot_limit_omaha"
    ? "PLO4 high · 6 seats · $1/$2 blinds · $200 stacks · no rake. Bots use heuristics; coach equity is estimated. Review stays in local memory until the server stops."
    : "Hold’em · 6 seats · $1/$2 blinds · $200 stacks. Bots use heuristics; session review stays in local memory until the server stops.";
  document.getElementById("table-title").textContent = nextHand
    ? `Next hand · ${selected.label}`
    : selected.label;
  document.getElementById("poker-table").setAttribute(
    "aria-label", `${nextHand ? "Next hand" : "Six-handed"} · ${selected.label} table. Waiting for a hand.`,
  );
  document.getElementById("table-meta").textContent =
    `6-max · ${selected.betting_structure === "pot_limit" ? "Pot-limit" : "No-limit"} · $1/$2`;
}

function clearActionMessage() {
  const status = document.getElementById("action-status");
  status.textContent = "";
  status.dataset.state = "";
}
