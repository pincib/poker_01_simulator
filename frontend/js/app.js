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
  status.lastElementChild.textContent = "Conectando";

  try {
    const response = await fetch("/api/health", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`O servidor respondeu com o código ${response.status}`);
    const health = await response.json();
    const configResponse = await fetch("/api/config", { headers: { Accept: "application/json" } });
    if (!configResponse.ok) throw new Error(`A configuração respondeu com o código ${configResponse.status}`);
    const config = await configResponse.json();
    apiConfig = config;
    configureVariantSelector(config);

    document.title = config.name;
    status.dataset.state = "online";
    status.lastElementChild.textContent = health.status === "ok" ? "Servidor local pronto" : "Serviço indisponível";
  } catch {
    status.dataset.state = "offline";
    status.lastElementChild.textContent = "Servidor indisponível";
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
  if (!response.ok) throw new Error(result.error || `A solicitação ao coach falhou (código ${response.status}).`);
  return result;
}

async function loadGameState() {
  try {
    const response = await fetch("/api/game/state", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("Não foi possível carregar o estado da mesa.");
    applyGameState(await response.json());
  } catch (error) {
    showActionError(error.message || "O servidor local do jogo está indisponível.");
  }
}

async function startHand() {
  const button = document.getElementById("deal-button");
  button.disabled = true;
  button.textContent = "Distribuindo…";
  clearActionMessage();
  try {
    const state = await postCoachRequest("/api/game/start", { variant: gameVariantSelect.value });
    applyGameState(state);
  } catch (error) {
    button.disabled = false;
    button.textContent = "Distribuir mão";
    showActionError(error.message || "Não foi possível distribuir a mão.");
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
    showActionError(error.message || "Não foi possível executar essa ação.");
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
    dealButton.textContent = "Distribuir mão";
  } else if (state.hand_complete && state.hero_stack <= 0) {
    dealButton.textContent = "Recomprar e distribuir";
  } else if (state.hand_complete) {
    dealButton.textContent = "Próxima mão";
  } else {
    dealButton.textContent = "Mão em andamento";
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
    ? "PLO4 high · 6 jogadores · blinds de $1/$2 · stacks de $200 · sem rake. Os adversários usam heurísticas; a equity do coach é estimada. A revisão fica na memória até o servidor ser encerrado."
    : "Hold’em · 6 jogadores · blinds de $1/$2 · stacks de $200. Os adversários usam heurísticas; a revisão da sessão fica na memória até o servidor ser encerrado.";
  document.getElementById("table-title").textContent = nextHand
    ? `Próxima mão · ${selected.label}`
    : selected.label;
  document.getElementById("poker-table").setAttribute(
    "aria-label", `${nextHand ? "Próxima mão" : "Mesa com seis jogadores"} · mesa de ${selected.label}. Aguardando distribuição.`,
  );
  document.getElementById("table-meta").textContent =
    `6-max · ${selected.betting_structure === "pot_limit" ? "Pot-limit" : "No-Limit"} · $1/$2`;
}

function clearActionMessage() {
  const status = document.getElementById("action-status");
  status.textContent = "";
  status.dataset.state = "";
}
