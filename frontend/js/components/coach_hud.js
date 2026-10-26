const byId = (id) => document.getElementById(id);

const assessmentCopy = {
  profitable: { label: "Estimate above the call price", state: "profitable" },
  unprofitable: { label: "Estimate below the call price", state: "unprofitable" },
  break_even: { label: "Estimate near break-even", state: "break_even" },
  no_call: { label: "No call to price", state: "no_call" },
};

let lessonSteps = [];
let lessonIndex = 0;
let lessonSignature = "";

export function renderCoachSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return;
  byId("coach-empty").hidden = true;
  byId("coach-snapshot").hidden = false;

  const assessment = assessmentCopy[snapshot.call_assessment] ?? assessmentCopy.no_call;
  const assessmentNode = byId("call-assessment");
  assessmentNode.textContent = assessment.label;
  assessmentNode.dataset.assessment = assessment.state;
  const nextSteps = Array.isArray(snapshot.learning_steps) ? snapshot.learning_steps : [];
  const nextSignature = JSON.stringify([nextSteps, snapshot.seed ?? null]);
  if (nextSignature !== lessonSignature) {
    lessonSignature = nextSignature;
    lessonIndex = 0;
  }
  lessonSteps = nextSteps;
  renderLessonStep();
  byId("coach-pot-odds").textContent = formatPercent(snapshot.pot_odds_percentage);
  byId("coach-equity").textContent = formatPercent(snapshot.equity_share_percentage ?? snapshot.equity_percentage);
  byId("coach-ev").textContent = formatChips(snapshot.ev_call);
  byId("coach-spr").textContent = snapshot.spr_value == null ? "—" : Number(snapshot.spr_value).toFixed(1);
  byId("coach-hand").textContent = snapshot.hand_description || "—";
  byId("coach-advice").textContent = snapshot.advice || "";

  const drawNode = byId("coach-draws");
  const draw = snapshot.draw_analysis;
  if (draw && typeof draw === "object") {
    const straightOuts = Array.isArray(draw.straight_outs) ? draw.straight_outs : [];
    const nutOuts = Array.isArray(draw.nut_outs) ? draw.nut_outs : [];
    const nonNutOuts = Array.isArray(draw.non_nut_outs) ? draw.non_nut_outs : [];
    const parts = [];
    if (straightOuts.length) {
      parts.push(`${draw.is_wrap ? "Wrap" : "Straight draw"}: ${straightOuts.length} distinct cards (${formatCards(straightOuts)})`);
    }
    if (nutOuts.length || nonNutOuts.length) {
      parts.push(`${nutOuts.length} nut improvements · ${nonNutOuts.length} non-nut improvements`);
    }
    if (Array.isArray(draw.unverified_outs) && draw.unverified_outs.length) {
      parts.push("clean-out status unverified; opponents’ cards are hidden");
    }
    drawNode.textContent = parts.length
      ? `Omaha draw check · ${parts.join(" · ")}`
      : "No next-card draw detected. A made hand can still change as the board runs out.";
    drawNode.hidden = false;
  } else {
    drawNode.textContent = "";
    drawNode.hidden = true;
  }
  const limitations = byId("coach-limitations");
  limitations.replaceChildren(...(Array.isArray(snapshot.limitations) ? snapshot.limitations : []).map((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    return item;
  }));
  limitations.hidden = limitations.childElementCount === 0;
  byId("coach-limitations-title").hidden = limitations.hidden;

  const warning = byId("coach-spr-warning");
  warning.textContent = snapshot.spr_warning || "";
  warning.hidden = !snapshot.spr_warning;
  const method = [];
  if (snapshot.deterministic) method.push("Exact calculation · opponent cards known");
  else if (snapshot.iterations) method.push(`Estimate · ${Number(snapshot.iterations).toLocaleString()} simulated outcomes`);
  const sources = {
    "known opponent hand": "opponent cards known",
    "provided opponent range": "range supplied for analysis",
    "estimated opponent range": "estimated opponent range",
    "action-filtered opponent range": "range estimated from position and action",
    "uniform four-card combinations": "sampled four-card hands",
    "estimated multiway ranges": "estimated ranges for multiple opponents",
    "action-filtered multiway ranges": "estimated multiway ranges",
  };
  if (snapshot.equity_source) method.push(sources[snapshot.equity_source] || "modeled opponent range");
  if (snapshot.opponent_range_size != null) method.push(`${Number(snapshot.opponent_range_size).toLocaleString()} combinations considered`);
  if (snapshot.seed != null) method.push(`reproduction seed ${snapshot.seed}`);
  byId("coach-method").textContent = method.filter(Boolean).join(" · ");
  byId("coach-state").textContent = "Let’s work through this decision";
}

function renderLessonStep() {
  const lesson = byId("coach-lesson");
  const step = lessonSteps[lessonIndex];
  if (!step) {
    lesson.hidden = true;
    return;
  }
  lesson.hidden = false;
  byId("lesson-label").textContent = step.label || "DECISION LESSON";
  byId("lesson-count").textContent = `Step ${lessonIndex + 1} of ${lessonSteps.length}`;
  byId("lesson-title").textContent = step.title || "Think through the spot";
  byId("lesson-body").textContent = step.body || "Use the current action and its price to make a plan.";
  byId("lesson-previous").disabled = lessonIndex === 0;
  byId("lesson-next").disabled = lessonIndex >= lessonSteps.length - 1;
}

function moveLessonStep(offset) {
  lessonIndex = Math.max(0, Math.min(lessonSteps.length - 1, lessonIndex + offset));
  renderLessonStep();
}

export function renderBetPurpose(result) {
  if (!result || typeof result !== "object") return;
  const purpose = byId("bet-purpose");
  purpose.hidden = false;
  purpose.dataset.purpose = result.purpose || "pointless";
  byId("bet-purpose-label").textContent = {
    value: "Value",
    bluff: "Bluff",
    pointless: "Purpose unclear in this model",
    unmodeled: "Not modeled",
  }[result.purpose] || "Bet purpose";
  byId("bet-purpose-evidence").textContent = result.evidence || "No range evidence is available.";
}

export function renderGameCoach(snapshot, note, handComplete = false, context = null, feedback = null) {
  const feedbackNode = byId("coach-feedback");
  feedbackNode.textContent = feedback || "";
  feedbackNode.hidden = !feedback;
  if (snapshot) {
    if (context === "last_decision") lessonSignature = "";
    renderCoachSnapshot(snapshot);
    if (context === "last_decision") byId("coach-state").textContent = "Last decision · lesson from before the action";
    return;
  }
  lessonSteps = [];
  lessonIndex = 0;
  lessonSignature = "";
  byId("coach-snapshot").hidden = true;
  byId("coach-empty").hidden = false;
  byId("coach-lesson").hidden = true;
  byId("bet-purpose").hidden = true;
  byId("coach-draws").hidden = true;
  byId("coach-limitations").hidden = true;
  byId("coach-limitations-title").hidden = true;
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
    byId("coach-empty").querySelector("h3").textContent = "A guide for each decision";
    byId("coach-empty").querySelector("p").textContent = "When it is your turn, the coach walks through the spot, the poker idea, the numbers, and one question to carry forward.";
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
  summary.textContent = `${Number.isNaN(date.getTime()) ? "Hand" : date.toLocaleString()} · ${variantLabel(hand.variant)} · ${hand.hero_position || "Position unknown"} · Pot ${hand.final_pot ?? 0}${hand.tricky ? " · Review marked" : ""}`;
  details.append(summary);

  const facts = document.createElement("dl");
  addFact(facts, "Variant", variantLabel(hand.variant));
  if (hand.variant === "pot_limit_omaha") addFact(facts, "Showdown rule", "Exactly 2 hole cards + 3 board cards");
  addFact(facts, "Hero cards", formatCards(hand.hole_cards));
  addFact(facts, "Board", formatCards(hand.board));
  addFact(facts, "Starting stack", hand.starting_stack ?? "—");
  addFact(facts, "Payout", hand.payouts?.[hand.hero_id] ?? 0);
  addFact(facts, "Winners", Array.isArray(hand.winners) ? hand.winners.join(", ") || "—" : "—");
  addFact(facts, "Showdown ranks", Object.entries(hand.showdown_ranks || {}).map(([id, rank]) => `${id}: ${rank}`).join(" · ") || "—");
  details.append(facts);

  const playerNames = Object.fromEntries((hand.players || []).map((player) => [player.id, player.name || player.id]));
  if (Array.isArray(hand.players) && hand.players.length) {
    const players = document.createElement("ul");
    players.className = "review-players";
    hand.players.forEach((player) => {
      const row = document.createElement("li");
      const cards = Array.isArray(player.hole_cards) && player.hole_cards.length
        ? formatCards(player.hole_cards)
        : player.active_at_end ? "not recorded" : "hidden after fold";
      row.textContent = `${player.name || player.id} · ${player.position || "—"} · cards ${cards} · contributed ${player.total_contributed ?? hand.contributions?.[player.id] ?? 0} · stack ${player.final_stack ?? "—"}`;
      players.append(row);
    });
    details.append(players);
  }
  const winningHands = Object.entries(hand.winning_hands || {});
  if (winningHands.length) {
    const winners = document.createElement("p");
    winners.className = "review-evidence";
    winners.textContent = `Winning combinations · ${winningHands.map(([id, cards]) => `${playerNames[id] || id}: ${formatCards(cards)}`).join("; ")}`;
    details.append(winners);
  }
  const awards = Array.isArray(hand.pot_awards) ? hand.pot_awards : [];
  if (awards.length) {
    const awardSummary = document.createElement("p");
    awardSummary.className = "review-evidence";
    awardSummary.textContent = `Pot awards · ${awards.map((award) => `${award.label}: ${award.amount} to ${(award.winner_ids || []).map((id) => playerNames[id] || id).join(", ") || "refunded"}`).join("; ")}`;
    details.append(awardSummary);
  }

  const actions = document.createElement("ol");
  actions.className = "review-actions";
  (hand.actions || []).forEach((action) => {
    const row = document.createElement("li");
    row.textContent = `${variantLabel(action.variant || hand.variant)} · ${action.street || "Street"}: ${playerNames[action.player_id] || action.player_id || "Player"} ${action.action || "acted"} · ${action.chips ?? 0} chips · bet to ${action.bet_to ?? "—"}`;
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
      decision.range_description || decision.equity_source
        ? `range: ${decision.range_description || decision.equity_source}${decision.opponent_range_size == null ? "" : ` (${decision.opponent_range_size} combos)`}` : "",
      decision.deterministic ? "exact known-hand river" : decision.equity_iterations == null ? "" : `${decision.equity_iterations} trials${decision.estimation_seed == null ? "" : ` · seed ${decision.estimation_seed}`}`,
      decision.draw_analysis ? `nut outs ${formatCards(decision.draw_analysis.nut_outs)} · non-nut outs ${formatCards(decision.draw_analysis.non_nut_outs)}` : "",
      ...(Array.isArray(decision.limitations) ? decision.limitations : []),
      decision.process_feedback || "",
      decision.review_question || "",
    ].filter(Boolean);
    row.textContent = pieces.join(" · ");
    const teaching = createDecisionTeaching(decision.learning_steps);
    if (teaching) row.append(teaching);
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
  const groups = report?.by_variant;
  if (groups && typeof groups === "object") {
    Object.entries(groups).forEach(([variant, group]) => {
      const item = document.createElement("li");
      const title = document.createElement("strong");
      title.textContent = `${variantLabel(variant)} · ${group.hands_reviewed ?? 0} hands`;
      item.append(title);
      const nested = document.createElement("ul");
      nested.className = "variant-leak-flags";
      (group.flags || []).forEach((flag) => nested.append(createLeakFlag(flag)));
      (group.limitations || []).forEach((limitation) => {
        const note = document.createElement("li");
        note.className = "review-evidence";
        note.textContent = limitation;
        nested.append(note);
      });
      item.append(nested);
      flags.append(item);
    });
  } else {
    (report?.flags || []).forEach((flag) => flags.append(createLeakFlag(flag)));
  }
  const plan = byId("weekly-plan");
  plan.replaceChildren();
  (report?.weekly_plan || []).forEach((step) => {
    const item = document.createElement("li");
    item.textContent = step;
    plan.append(item);
  });
}

function createLeakFlag(flag) {
  const item = document.createElement("li");
  const title = document.createElement("strong");
  title.textContent = `${flag.title} · ${Number(flag.rate_percentage).toFixed(0)}%`;
  const description = document.createElement("span");
  description.textContent = `${flag.message} ${flag.lesson}`;
  item.append(title, description);
  return item;
}

function createDecisionTeaching(steps) {
  if (!Array.isArray(steps) || !steps.length) return null;
  const details = document.createElement("details");
  details.className = "decision-lesson-review";
  const summary = document.createElement("summary");
  summary.textContent = "Open the step-by-step coaching";
  details.append(summary);
  const list = document.createElement("ol");
  steps.forEach((step) => {
    const entry = document.createElement("li");
    const heading = document.createElement("strong");
    heading.textContent = step.title || step.label || "Coach step";
    const body = document.createElement("span");
    body.textContent = step.body || "";
    entry.append(heading, body);
    list.append(entry);
  });
  details.append(list);
  return details;
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

function variantLabel(variant) {
  return variant === "pot_limit_omaha" ? "PLO4 · Pot-limit" : "Texas Hold’em";
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
  byId("lesson-previous").addEventListener("click", () => moveLessonStep(-1));
  byId("lesson-next").addEventListener("click", () => moveLessonStep(1));
  window.addEventListener("poker:coach-snapshot", (event) => renderCoachSnapshot(event.detail));
  window.addEventListener("poker:bet-purpose", (event) => renderBetPurpose(event.detail));
  window.addEventListener("poker:hand-recorded", refreshSessionReview);
  refreshSessionReview();
}
