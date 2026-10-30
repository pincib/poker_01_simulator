import { formatMoney } from "./table_view.js";

let gameState = null;
let submitAction = async () => {};
let requestPending = false;
let selectedFraction = 0.5;
let selectedMax = false;

export function initializeActionBar({ onAction }) {
  submitAction = onAction;
  document.getElementById("fold-button").addEventListener("click", () => submitAction("fold"));
  document.getElementById("call-check-button").addEventListener("click", (event) => {
    submitAction(event.currentTarget.dataset.action);
  });
  document.getElementById("bet-button").addEventListener("click", () => {
    const action = document.getElementById("bet-button").dataset.action;
    const amount = Number.parseInt(document.getElementById("raise-to-input").value, 10);
    submitAction(action, amount);
  });
  document.getElementById("all-in-button").addEventListener("click", () => submitAction("all_in"));
  document.getElementById("size-presets").addEventListener("click", (event) => {
    const button = event.target.closest("[data-pot-fraction]");
    if (!button || !gameState) return;
    selectedFraction = Number(button.dataset.potFraction);
    selectedMax = false;
    document.querySelectorAll("#size-presets .size-button").forEach((item) => item.classList.toggle("selected", item === button));
    setPresetAmount();
  });
  document.getElementById("max-bet-button").addEventListener("click", () => {
    if (!gameState) return;
    selectedMax = true;
    document.querySelectorAll("#size-presets .size-button").forEach((item) => item.classList.toggle("selected", item.id === "max-bet-button"));
    setPresetAmount();
  });
  document.getElementById("raise-to-input").addEventListener("input", () => {
    selectedMax = false;
    document.querySelectorAll("#size-presets .size-button").forEach((item) => item.classList.remove("selected"));
    updateBetLabel();
  });
  document.getElementById("raise-to-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      document.getElementById("bet-button").click();
    }
  });
  window.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey || isTypingTarget(event.target) || !gameState) return;
    const key = event.key.toLowerCase();
    if (event.code === "Space") {
      event.preventDefault();
      document.getElementById("call-check-button").click();
    } else if (key === "f") {
      document.getElementById("fold-button").click();
    } else if (key === "c" && gameState.legal_actions.includes("call")) {
      document.getElementById("call-check-button").click();
    } else if (key === "b") {
      document.getElementById("bet-button").click();
    }
  });
}

export function renderActionBar(state) {
  gameState = state?.started && !state.hand_complete ? state : null;
  const bar = document.getElementById("action-bar");
  bar.hidden = !state?.started || Boolean(state.hand_complete);
  if (bar.hidden) return;

  const legal = new Set(state.legal_actions || []);
  const isHeroTurn = state.current_player_id === "hero";
  const foldButton = document.getElementById("fold-button");
  const callButton = document.getElementById("call-check-button");
  const sizing = document.getElementById("size-presets");
  const inputWrap = document.querySelector(".size-input-wrap");
  const betButton = document.getElementById("bet-button");
  const allIn = document.getElementById("all-in-button");
  const maxBet = document.getElementById("max-bet-button");
  const canBet = legal.has("bet") || legal.has("raise");
  const canCall = legal.has("call");
  const canCheck = legal.has("check");

  document.getElementById("action-prompt").textContent = isHeroTurn ? `Sua ação · ${state.hero_position}` : "Ação do adversário";
  document.getElementById("action-hint").textContent = isHeroTurn
    ? `Espaço check · F fold · C call · B ${legal.has("raise") ? "raise" : "bet"} até o total`
    : "Os perfis dos adversários estão escolhendo uma ação.";
  foldButton.disabled = requestPending || !isHeroTurn || !legal.has("fold");
  foldButton.hidden = !legal.has("fold");
  callButton.dataset.action = canCall ? "call" : "check";
  callButton.textContent = canCall ? `Call ${formatMoney(state.hero_to_call)}` : "Check";
  callButton.disabled = requestPending || !isHeroTurn || (!canCall && !canCheck);
  callButton.hidden = !canCall && !canCheck;
  callButton.classList.toggle("call-button", canCall);
  callButton.classList.toggle("check-button", !canCall);
  callButton.append(makeShortcut(canCall ? "C" : "Espaço"));

  sizing.hidden = !canBet;
  inputWrap.hidden = !canBet;
  betButton.hidden = !canBet;
  betButton.disabled = requestPending || !isHeroTurn || !canBet;
  allIn.hidden = !legal.has("all_in");
  allIn.disabled = requestPending || !isHeroTurn || !legal.has("all_in");
  maxBet.disabled = requestPending || !isHeroTurn || !canBet;
  maxBet.textContent = state.betting_structure === "pot_limit" ? "Pote máx." : "Máx.";
  maxBet.setAttribute(
    "aria-label",
    `${state.betting_structure === "pot_limit" ? "Máximo no Pot-limit" : "Máximo permitido"} de aposta ou raise até ${formatMoney(state.raise_max)}`,
  );
  betButton.dataset.action = legal.has("raise") ? "raise" : "bet";
  document.getElementById("raise-to-label").textContent = legal.has("raise") ? "Raise até o total" : "Aposta até o total";
  const limitNote = document.getElementById("bet-limit-note");
  limitNote.textContent = state.betting_structure === "pot_limit"
    ? `Pot-limit · ${legal.has("raise") ? "raise" : "bet"} máximo de ${formatMoney(state.raise_max)} no total`
    : `Total máximo nesta street: ${formatMoney(state.raise_max)}`;
  limitNote.hidden = !canBet;

  const input = document.getElementById("raise-to-input");
  input.min = String(state.raise_min);
  input.max = String(state.raise_max);
  input.disabled = requestPending || !isHeroTurn;
  setPresetAmount();
  setPending(requestPending);
}

export function setActionPending(pending, message = "") {
  requestPending = pending;
  const status = document.getElementById("action-status");
  status.textContent = message;
  status.dataset.state = message ? (pending ? "loading" : "success") : "";
  if (gameState) renderActionBar(gameState);
}

export function showActionError(message) {
  const status = document.getElementById("action-status");
  status.textContent = message;
  status.dataset.state = "error";
  const tableMessage = document.getElementById("table-message");
  tableMessage.textContent = message;
  tableMessage.dataset.state = "error";
}

function setPresetAmount() {
  if (!gameState) return;
  const potToSize = gameState.pot + gameState.hero_to_call;
  const minRaise = Number(gameState.raise_min);
  const maxRaise = Number(gameState.raise_max);
  const increment = Math.max(gameState.big_blind, Math.round(potToSize * selectedFraction));
  const potPresetTarget = gameState.current_bet + gameState.hero_to_call + increment;
  const target = selectedMax ? maxRaise : Math.min(maxRaise, Math.max(minRaise, potPresetTarget));
  const input = document.getElementById("raise-to-input");
  input.value = String(target);
  updateBetLabel();
}

function updateBetLabel() {
  const input = document.getElementById("raise-to-input");
  const button = document.getElementById("bet-button");
  const value = Number.parseInt(input.value, 10);
  const target = Number.isFinite(value) ? formatMoney(value) : "—";
  button.textContent = `${gameState?.legal_actions.includes("raise") ? "Raise" : "Apostar"} até ${target}`;
  button.append(makeShortcut("B"));
  button.disabled = requestPending || !gameState || !Number.isFinite(value)
    || value < Number(input.min) || value > Number(input.max);
}

function setPending(pending) {
  if (!pending) return;
  document.getElementById("action-status").textContent = "A mesa está processando sua ação…";
  document.getElementById("action-status").dataset.state = "loading";
}

function makeShortcut(key) {
  const shortcut = document.createElement("kbd");
  shortcut.textContent = key;
  return shortcut;
}

function isTypingTarget(target) {
  return target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
}
