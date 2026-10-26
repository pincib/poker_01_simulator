import {
  initializeCoachHud,
  refreshSessionReview,
  renderBetPurpose,
  renderCoachSnapshot,
} from "./components/coach_hud.js";
import { initializeActionBar, renderActionBar, setActionPending, showActionError } from "./components/action_bar.js";
import { renderGameState } from "./components/table_view.js";

const status = document.querySelector("#service-status");

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

    document.title = config.name;
    status.dataset.state = "online";
    status.lastElementChild.textContent = health.status === "ok" ? "Local server ready" : "Service unavailable";
  } catch {
    status.dataset.state = "offline";
    status.lastElementChild.textContent = "Server unavailable";
  }
}

loadServiceStatus();
initializeCoachHud();
initializeActionBar({ onAction: submitGameAction });
document.getElementById("deal-button").addEventListener("click", startHand);
loadGameState();

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
    const state = await postCoachRequest("/api/game/start", {});
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
    const state = await postCoachRequest("/api/game/action", { action, amount });
    applyGameState(state);
    if (state.hand_complete) await refreshSessionReview();
  } catch (error) {
    setActionPending(false);
    showActionError(error.message || "That action could not be applied.");
  }
}

function applyGameState(state) {
  renderGameState(state);
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

function clearActionMessage() {
  const status = document.getElementById("action-status");
  status.textContent = "";
  status.dataset.state = "";
}
