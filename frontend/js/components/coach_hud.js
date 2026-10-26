const byId = (id) => document.getElementById(id);

const assessmentCopy = {
  profitable: { label: "+EV call at this price", state: "profitable" },
  unprofitable: { label: "−EV call at this price", state: "unprofitable" },
  break_even: { label: "At break-even before rake", state: "break_even" },
  no_call: { label: "No call to price", state: "no_call" },
};

export function renderCoachSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return;
  byId("coach-empty").hidden = true;
  byId("coach-snapshot").hidden = false;

  const assessment = assessmentCopy[snapshot.call_assessment] ?? assessmentCopy.no_call;
  const assessmentNode = byId("call-assessment");
  assessmentNode.textContent = assessment.label;
  assessmentNode.dataset.assessment = assessment.state;
  byId("coach-pot-odds").textContent = formatPercent(snapshot.pot_odds_percentage);
  byId("coach-equity").textContent = formatPercent(snapshot.equity_share_percentage ?? snapshot.equity_percentage);
  byId("coach-ev").textContent = formatChips(snapshot.ev_call);
  byId("coach-spr").textContent = snapshot.spr_value == null ? "—" : Number(snapshot.spr_value).toFixed(1);
  byId("coach-hand").textContent = snapshot.hand_description || "—";
  byId("coach-advice").textContent = snapshot.advice || "";

  const warning = byId("coach-spr-warning");
  warning.textContent = snapshot.spr_warning || "";
  warning.hidden = !snapshot.spr_warning;
  byId("coach-method").textContent = snapshot.iterations
    ? `Estimated from ${Number(snapshot.iterations).toLocaleString()} runouts · ${snapshot.equity_source || "modeled range"}`
    : "";
  byId("coach-state").textContent = "Decision analyzed";
}

export function renderBetPurpose(result) {
  if (!result || typeof result !== "object") return;
  const purpose = byId("bet-purpose");
  purpose.hidden = false;
  purpose.dataset.purpose = result.purpose || "pointless";
  byId("bet-purpose-label").textContent = {
    value: "Value",
    bluff: "Bluff",
    pointless: "Pointless bet",
  }[result.purpose] || "Bet purpose";
  byId("bet-purpose-evidence").textContent = result.evidence || "No range evidence is available.";
}

export function renderGameCoach(snapshot, note, handComplete = false, context = null) {
  if (snapshot) {
    renderCoachSnapshot(snapshot);
    if (context === "last_decision") byId("coach-state").textContent = "Last decision · pre-action analysis";
    return;
  }
  byId("coach-snapshot").hidden = true;
  byId("coach-empty").hidden = false;
  byId("bet-purpose").hidden = true;
  if (note) {
    byId("coach-state").textContent = handComplete ? "Hand complete" : "Multiway decision";
    byId("coach-empty").querySelector("h3").textContent = handComplete ? "Review the completed hand" : "Heads-up estimate unavailable";
    byId("coach-empty").querySelector("p").textContent = note;
  } else if (handComplete) {
    byId("coach-state").textContent = "Hand complete";
    byId("coach-empty").querySelector("h3").textContent = "Review your last decision";
    byId("coach-empty").querySelector("p").textContent = "The coach analyzes decisions while you have an action to make. Recorded actions and notes are in Session review.";
  } else {
    byId("coach-state").textContent = handComplete ? "Hand complete" : "Ready when you play";
    byId("coach-empty").querySelector("h3").textContent = "Numbers at the decision";
    byId("coach-empty").querySelector("p").textContent = "Pot odds, estimated equity, and SPR appear here when a hand is connected.";
  }
}

export function setCoachMode(enabled) {
  const toggle = byId("coach-mode-toggle");
  toggle.setAttribute("aria-pressed", String(enabled));
  toggle.textContent = enabled ? "Coach on" : "Coach off";
  byId("coach-panel").hidden = !enabled;
  document.querySelector(".practice-grid").classList.toggle("coach-hidden", !enabled);
}

export async function refreshSessionReview() {
  const status = byId("review-status");
  const list = byId("hand-review-list");
  status.textContent = "Loading hand review…";
  list.replaceChildren();

  try {
    const [handsResponse, leaksResponse] = await Promise.all([
      fetch("/api/session/hands", { headers: { Accept: "application/json" } }),
      fetch("/api/session/leaks", { headers: { Accept: "application/json" } }),
    ]);
    if (!handsResponse.ok || !leaksResponse.ok) throw new Error("Review data is unavailable.");
    const { hands } = await handsResponse.json();
    const report = await leaksResponse.json();
    renderHandReviews(Array.isArray(hands) ? hands : []);
    renderLeakReport(report);
  } catch {
    status.textContent = "Session review is unavailable while the local server is disconnected.";
  }
}

function renderHandReviews(hands) {
  const status = byId("review-status");
  const list = byId("hand-review-list");
  list.replaceChildren();
  if (hands.length === 0) {
    status.hidden = false;
    status.textContent = "Completed hands will appear here with cards, actions, and decision notes.";
    return;
  }
  status.hidden = true;
  hands.forEach((hand) => list.append(createHandReview(hand)));
}

function createHandReview(hand) {
  const item = document.createElement("li");
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  const date = new Date(hand.recorded_at);
  summary.textContent = `${Number.isNaN(date.getTime()) ? "Hand" : date.toLocaleString()} · ${hand.hero_position || "Position unknown"} · Pot ${hand.final_pot ?? 0}${hand.tricky ? " · Review marked" : ""}`;
  details.append(summary);

  const facts = document.createElement("dl");
  addFact(facts, "Hero cards", formatCards(hand.hole_cards));
  addFact(facts, "Board", formatCards(hand.board));
  addFact(facts, "Starting stack", hand.starting_stack ?? "—");
  addFact(facts, "Payout", hand.payouts?.[hand.hero_id] ?? 0);
  details.append(facts);

  const actions = document.createElement("ol");
  actions.className = "review-actions";
  (hand.actions || []).forEach((action) => {
    const row = document.createElement("li");
    row.textContent = `${action.street || "Street"}: ${action.player_id || "Player"} ${action.action || "acted"} · ${action.chips ?? 0} chips`;
    actions.append(row);
  });
  if (actions.childElementCount) details.append(actions);

  const decisions = document.createElement("ul");
  decisions.className = "decision-notes";
  (hand.decisions || []).forEach((decision) => {
    const row = document.createElement("li");
    const pieces = [
      `${decision.street}: ${decision.action}`,
      decision.pot_odds_percentage == null ? "" : `price ${formatPercent(decision.pot_odds_percentage)}`,
      decision.equity_percentage == null ? "" : `equity ${formatPercent(decision.equity_percentage)}`,
      decision.bet_purpose ? `purpose: ${decision.bet_purpose}` : "",
      decision.review_question || "",
    ].filter(Boolean);
    row.textContent = pieces.join(" · ");
    decisions.append(row);
  });
  if (decisions.childElementCount) details.append(decisions);
  item.append(details);
  return item;
}

function renderLeakReport(report) {
  byId("leak-study-target").textContent = report?.study_target || "No study target available yet.";
  const flags = byId("leak-flag-list");
  flags.replaceChildren();
  (report?.flags || []).forEach((flag) => {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = `${flag.title} · ${Number(flag.rate_percentage).toFixed(0)}%`;
    const description = document.createElement("span");
    description.textContent = `${flag.message} ${flag.lesson}`;
    item.append(title, description);
    flags.append(item);
  });
  const plan = byId("weekly-plan");
  plan.replaceChildren();
  (report?.weekly_plan || []).forEach((step) => {
    const item = document.createElement("li");
    item.textContent = step;
    plan.append(item);
  });
}

function addFact(list, label, value) {
  const row = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = String(value);
  row.append(term, description);
  list.append(row);
}

function formatCards(cards) {
  return Array.isArray(cards) && cards.length ? cards.join("  ") : "—";
}

function formatPercent(value) {
  return value == null || !Number.isFinite(Number(value)) ? "—" : `${Number(value).toFixed(1)}%`;
}

function formatChips(value) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const amount = Number(value);
  return `${amount > 0 ? "+" : ""}${amount.toFixed(1)} chips`;
}

export function initializeCoachHud() {
  const toggle = byId("coach-mode-toggle");
  toggle.addEventListener("click", () => {
    const enabled = toggle.getAttribute("aria-pressed") !== "true";
    setCoachMode(enabled);
  });
  byId("refresh-review").addEventListener("click", refreshSessionReview);
  window.addEventListener("poker:coach-snapshot", (event) => renderCoachSnapshot(event.detail));
  window.addEventListener("poker:bet-purpose", (event) => renderBetPurpose(event.detail));
  window.addEventListener("poker:hand-recorded", refreshSessionReview);
  refreshSessionReview();
}
