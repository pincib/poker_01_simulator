const byId = (id) => document.getElementById(id);

const assessmentCopy = {
  profitable: { label: "Estimativa acima do preço do call", state: "profitable" },
  unprofitable: { label: "Estimativa abaixo do preço do call", state: "unprofitable" },
  break_even: { label: "Estimativa próxima do zero a zero", state: "break_even" },
  no_call: { label: "Sem call para avaliar", state: "no_call" },
};

const equitySourceCopy = {
  "known opponent hand": "cartas do adversário conhecidas",
  "provided opponent range": "faixa fornecida para análise",
  "estimated opponent range": "faixa estimada do adversário",
  "action-filtered opponent range": "faixa estimada pela posição e ação",
  "uniform four-card combinations": "mãos de quatro cartas amostradas",
  "uniform sampled PLO4 combinations, position/action adjusted by a simple heuristic": "combinações aleatórias de PLO4, ajustadas por posição e ação com uma heurística simples",
  "position/action filtered Hold'em opening ranges": "faixas de abertura do Hold’em filtradas por posição e ação",
  "estimated multiway ranges": "faixas estimadas para vários adversários",
  "action-filtered multiway ranges": "faixas multiway estimadas",
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
  byId("coach-spr").textContent = snapshot.spr_value == null ? "—" : Number(snapshot.spr_value).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  byId("coach-hand").textContent = snapshot.hand_description || "—";
  byId("coach-advice").textContent = localizeDecimals(snapshot.advice || "");
  renderEquityCharts(snapshot);

  const drawNode = byId("coach-draws");
  const draw = snapshot.draw_analysis;
  if (draw && typeof draw === "object") {
    const straightOuts = Array.isArray(draw.straight_outs) ? draw.straight_outs : [];
    const nutOuts = Array.isArray(draw.nut_outs) ? draw.nut_outs : [];
    const nonNutOuts = Array.isArray(draw.non_nut_outs) ? draw.non_nut_outs : [];
    const parts = [];
    if (straightOuts.length) {
      parts.push(`${draw.is_wrap ? "Wrap" : "Draw de sequência"}: ${straightOuts.length} cartas distintas (${formatCards(straightOuts)})`);
    }
    if (nutOuts.length || nonNutOuts.length) {
      parts.push(`${nutOuts.length} melhorias para nuts · ${nonNutOuts.length} outras melhorias`);
    }
    if (Array.isArray(draw.unverified_outs) && draw.unverified_outs.length) {
      parts.push("não foi possível confirmar se os outs são limpos; as cartas dos adversários estão ocultas");
    }
    drawNode.textContent = parts.length
      ? `Análise de draws no Omaha · ${parts.join(" · ")}`
      : "Nenhum draw para a próxima carta foi identificado. Uma mão pronta ainda pode mudar conforme o board é completado.";
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
  warning.textContent = localizeDecimals(snapshot.spr_warning || "");
  warning.hidden = !snapshot.spr_warning;
  const method = [];
  if (snapshot.deterministic) method.push("Cálculo exato · cartas do adversário conhecidas");
  else if (snapshot.iterations) method.push(`Estimativa · ${Number(snapshot.iterations).toLocaleString()} resultados simulados`);
  if (snapshot.equity_source) method.push(localizeEquitySource(snapshot.equity_source));
  if (snapshot.opponent_range_size != null) method.push(`${Number(snapshot.opponent_range_size).toLocaleString("pt-BR")} combinações consideradas`);
  if (snapshot.seed != null) method.push(`semente para reproduzir o cálculo: ${snapshot.seed}`);
  byId("coach-method").textContent = method.filter(Boolean).join(" · ");
  byId("coach-state").textContent = "Vamos analisar esta decisão";
}

function renderEquityCharts(snapshot) {
  const outcomes = [
    ["win", snapshot.win_percentage],
    ["tie", snapshot.tie_percentage],
    ["loss", snapshot.loss_percentage],
  ];
  const outcomeLabel = { win: "vitória", tie: "empate", loss: "derrota" };
  const summary = [];
  for (const [key, value] of outcomes) {
    const percentage = clampPercentage(value);
    byId(`outcome-${key}`).style.width = `${percentage}%`;
    byId(`outcome-${key}-value`).textContent = formatPercent(percentage);
    summary.push(`${outcomeLabel[key]}: ${formatPercent(percentage)}`);
  }
  byId("outcome-chart").setAttribute("aria-label", `Resultados estimados: ${summary.join(", ")}`);

  const equity = clampPercentage(snapshot.equity_share_percentage ?? snapshot.equity_percentage);
  const odds = snapshot.pot_odds_percentage == null ? null : clampPercentage(snapshot.pot_odds_percentage);
  byId("equity-fill").style.width = `${equity}%`;
  byId("equity-marker").style.left = `${equity}%`;
  byId("chart-equity-value").textContent = formatPercent(equity);
  byId("pot-odds-legend").hidden = odds == null;
  byId("pot-odds-marker").hidden = odds == null;
  byId("chart-call-note").hidden = odds != null;
  if (odds != null) {
    byId("pot-odds-marker").style.left = `${odds}%`;
    byId("chart-pot-odds-value").textContent = formatPercent(odds);
    byId("equity-chart").setAttribute("aria-label", `Equity estimada ${formatPercent(equity)}; pot odds ${formatPercent(odds)}`);
  } else {
    byId("equity-chart").setAttribute("aria-label", `Equity estimada ${formatPercent(equity)}; não há call para pagar`);
  }
}

function clampPercentage(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(100, Math.max(0, number)) : 0;
}

function renderLessonStep() {
  const lesson = byId("coach-lesson");
  const step = lessonSteps[lessonIndex];
  if (!step) {
    lesson.hidden = true;
    return;
  }
  lesson.hidden = false;
  byId("lesson-label").textContent = step.label || "LIÇÃO SOBRE A DECISÃO";
  byId("lesson-count").textContent = `Etapa ${lessonIndex + 1} de ${lessonSteps.length}`;
  byId("lesson-title").textContent = step.title || "Analise esta situação";
  byId("lesson-body").textContent = localizeDecimals(step.body || "Considere a ação atual e o preço para definir seu plano.");
  renderLessonProgress();
  byId("lesson-previous").disabled = lessonIndex === 0;
  byId("lesson-next").disabled = lessonIndex >= lessonSteps.length - 1;
}

function renderLessonProgress() {
  const progress = byId("lesson-progress");
  progress.style.setProperty("--step-count", Math.max(lessonSteps.length, 1));
  progress.replaceChildren(...lessonSteps.map((step, index) => {
    const item = document.createElement("li");
    item.dataset.state = index < lessonIndex ? "complete" : index === lessonIndex ? "current" : "upcoming";
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-label", `Etapa ${index + 1} de ${lessonSteps.length}: ${step.label || step.title || "Análise"}`);
    if (index === lessonIndex) button.setAttribute("aria-current", "step");
    const marker = document.createElement("span");
    marker.className = "lesson-step-marker";
    marker.textContent = String(index + 1);
    const label = document.createElement("span");
    label.className = "lesson-step-label";
    label.textContent = shortStepLabel(step);
    button.append(marker, label);
    button.addEventListener("click", () => {
      lessonIndex = index;
      renderLessonStep();
    });
    item.append(button);
    return item;
  }));
}

function shortStepLabel(step) {
  return ({
    context: "Situação",
    concept: "Conceito",
    estimate: "Números",
    suggestion: "Sugestão",
    practice: "Prática",
  })[step.kind] || step.label || "Etapa";
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
    value: "Aposta por valor",
    bluff: "Bluff",
    pointless: "Propósito pouco claro neste modelo",
    unmodeled: "Não modelado",
  }[result.purpose] || "Propósito da aposta";
  byId("bet-purpose-evidence").textContent = result.evidence || "Não há dados da faixa para avaliar.";
}

export function renderGameCoach(snapshot, note, handComplete = false, context = null, feedback = null) {
  const feedbackNode = byId("coach-feedback");
  feedbackNode.textContent = feedback || "";
  feedbackNode.hidden = !feedback;
  if (snapshot) {
    if (context === "last_decision") lessonSignature = "";
    renderCoachSnapshot(snapshot);
    if (context === "last_decision") byId("coach-state").textContent = "Decisão anterior · análise feita antes da ação";
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
    byId("coach-state").textContent = handComplete ? "Mão concluída" : "Decisão multiway";
    byId("coach-empty").querySelector("h3").textContent = handComplete ? "Revise a mão concluída" : "Estimativa mano a mano indisponível";
    byId("coach-empty").querySelector("p").textContent = note;
  } else if (handComplete) {
    byId("coach-state").textContent = "Mão concluída";
    byId("coach-empty").querySelector("h3").textContent = "Revise sua última decisão";
    byId("coach-empty").querySelector("p").textContent = "O coach analisa as decisões quando é sua vez de agir. As ações e anotações ficam na revisão da sessão.";
  } else {
    byId("coach-state").textContent = handComplete ? "Mão concluída" : "Pronto para quando você jogar";
    byId("coach-empty").querySelector("h3").textContent = "Um guia para cada decisão";
    byId("coach-empty").querySelector("p").textContent = "Na sua vez, o coach explica a situação, o conceito de poker, os números e uma pergunta para levar adiante.";
  }
}

export function setCoachMode(enabled) {
  const toggle = byId("coach-mode-toggle");
  toggle.setAttribute("aria-pressed", String(enabled));
  toggle.textContent = enabled ? "Coach ligado" : "Coach desligado";
  byId("coach-panel").hidden = !enabled;
  document.querySelector(".practice-grid").classList.toggle("coach-hidden", !enabled);
}

export async function refreshSessionReview() {
  const status = byId("review-status");
  const list = byId("hand-review-list");
  status.textContent = "Carregando revisão das mãos…";
  list.replaceChildren();

  try {
    const [handsResponse, leaksResponse] = await Promise.all([
      fetch("/api/session/hands", { headers: { Accept: "application/json" } }),
      fetch("/api/session/leaks", { headers: { Accept: "application/json" } }),
    ]);
    if (!handsResponse.ok || !leaksResponse.ok) throw new Error("Os dados da revisão estão indisponíveis.");
    const { hands } = await handsResponse.json();
    const report = await leaksResponse.json();
    renderHandReviews(Array.isArray(hands) ? hands : []);
    renderLeakReport(report);
  } catch {
    status.textContent = "A revisão da sessão está indisponível enquanto o servidor local estiver desconectado.";
  }
}

function renderHandReviews(hands) {
  const status = byId("review-status");
  const list = byId("hand-review-list");
  list.replaceChildren();
  if (hands.length === 0) {
    status.hidden = false;
    status.textContent = "As mãos concluídas aparecerão aqui com cartas, ações e anotações sobre as decisões.";
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
  summary.textContent = `${Number.isNaN(date.getTime()) ? "Mão" : date.toLocaleString("pt-BR")} · ${variantLabel(hand.variant)} · ${hand.hero_position || "Posição desconhecida"} · Pote ${hand.final_pot ?? 0}${hand.tricky ? " · Marcada para revisão" : ""}`;
  details.append(summary);

  const facts = document.createElement("dl");
  addFact(facts, "Modalidade", variantLabel(hand.variant));
  if (hand.variant === "pot_limit_omaha") addFact(facts, "Regra do showdown", "Use exatamente 2 cartas da mão + 3 do board");
  addFact(facts, "Suas cartas", formatCards(hand.hole_cards));
  addFact(facts, "Board", formatCards(hand.board));
  addFact(facts, "Stack inicial", hand.starting_stack ?? "—");
  addFact(facts, "Pagamento", hand.payouts?.[hand.hero_id] ?? 0);
  addFact(facts, "Vencedores", Array.isArray(hand.winners) ? hand.winners.join(", ") || "—" : "—");
  addFact(facts, "Mãos no showdown", Object.entries(hand.showdown_ranks || {}).map(([id, rank]) => `${id}: ${rank}`).join(" · ") || "—");
  details.append(facts);

  const playerNames = Object.fromEntries((hand.players || []).map((player) => [player.id, player.name || player.id]));
  if (Array.isArray(hand.players) && hand.players.length) {
    const players = document.createElement("ul");
    players.className = "review-players";
    hand.players.forEach((player) => {
      const row = document.createElement("li");
      const cards = Array.isArray(player.hole_cards) && player.hole_cards.length
        ? formatCards(player.hole_cards)
        : player.active_at_end ? "não registrado" : "ocultas após fold";
      row.textContent = `${player.name || player.id} · ${player.position || "—"} · cartas ${cards} · contribuiu ${player.total_contributed ?? hand.contributions?.[player.id] ?? 0} · stack ${player.final_stack ?? "—"}`;
      players.append(row);
    });
    details.append(players);
  }
  const winningHands = Object.entries(hand.winning_hands || {});
  if (winningHands.length) {
    const winners = document.createElement("p");
    winners.className = "review-evidence";
    winners.textContent = `Combinações vencedoras · ${winningHands.map(([id, cards]) => `${playerNames[id] || id}: ${formatCards(cards)}`).join("; ")}`;
    details.append(winners);
  }
  const awards = Array.isArray(hand.pot_awards) ? hand.pot_awards : [];
  if (awards.length) {
    const awardSummary = document.createElement("p");
    awardSummary.className = "review-evidence";
    awardSummary.textContent = `Distribuição do pote · ${awards.map((award) => `${localizePotLabel(award.label)}: ${award.amount} para ${(award.winner_ids || []).map((id) => playerNames[id] || id).join(", ") || "devolvido"}`).join("; ")}`;
    details.append(awardSummary);
  }

  const actions = document.createElement("ol");
  actions.className = "review-actions";
  (hand.actions || []).forEach((action) => {
    const row = document.createElement("li");
    row.textContent = `${variantLabel(action.variant || hand.variant)} · ${localizeStreet(action.street)}: ${playerNames[action.player_id] || action.player_id || "Jogador"} ${action.action || "agiu"} · ${action.chips ?? 0} fichas · total apostado ${action.bet_to ?? "—"}`;
    actions.append(row);
  });
  if (actions.childElementCount) details.append(actions);

  const decisions = document.createElement("ul");
  decisions.className = "decision-notes";
  (hand.decisions || []).forEach((decision) => {
    const row = document.createElement("li");
    const pieces = [
      `${decision.street}: ${decision.action}`,
      decision.pot_odds_percentage == null ? "" : `preço ${formatPercent(decision.pot_odds_percentage)}`,
      decision.equity_percentage == null ? "" : `equity ${formatPercent(decision.equity_percentage)}`,
      decision.bet_purpose ? `propósito: ${localizeBetPurpose(decision.bet_purpose)}` : "",
      decision.range_description || decision.equity_source
        ? `faixa: ${localizeEquitySource(decision.range_description || decision.equity_source)}${decision.opponent_range_size == null ? "" : ` (${decision.opponent_range_size} combinações)`}` : "",
      decision.deterministic ? "river com mão conhecida e cálculo exato" : decision.equity_iterations == null ? "" : `${decision.equity_iterations} simulações${decision.estimation_seed == null ? "" : ` · semente ${decision.estimation_seed}`}`,
      decision.draw_analysis ? `outs para nuts ${formatCards(decision.draw_analysis.nut_outs)} · outs que não formam nuts ${formatCards(decision.draw_analysis.non_nut_outs)}` : "",
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
  byId("leak-study-target").textContent = report?.study_target || "Ainda não há uma meta de estudo.";
  const flags = byId("leak-flag-list");
  flags.replaceChildren();
  const groups = report?.by_variant;
  if (groups && typeof groups === "object") {
    Object.entries(groups).forEach(([variant, group]) => {
      const item = document.createElement("li");
      const title = document.createElement("strong");
      title.textContent = `${variantLabel(variant)} · ${group.hands_reviewed ?? 0} mãos`;
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
  summary.textContent = "Abrir a análise passo a passo do coach";
  details.append(summary);
  const list = document.createElement("ol");
  steps.forEach((step) => {
    const entry = document.createElement("li");
    const heading = document.createElement("strong");
    heading.textContent = step.title || step.label || "Etapa do coach";
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

function localizeStreet(street) {
  return ({ preflop: "pré-flop", flop: "flop", turn: "turn", river: "river", showdown: "showdown" })[street] || street || "etapa";
}

function localizePotLabel(label) {
  if (label === "Main Pot") return "Pote principal";
  if (label === "Uncalled return") return "Devolução de aposta não paga";
  const sidePot = /^Side Pot (\d+)$/.exec(label || "");
  return sidePot ? `Pote paralelo ${sidePot[1]}` : label || "Pote";
}

function localizeEquitySource(source) {
  return equitySourceCopy[source] || source || "faixa adversária modelada";
}

function localizeBetPurpose(purpose) {
  return ({ value: "aposta por valor", bluff: "blefe", pointless: "aposta sem propósito claro", unmodeled: "não modelado" })[purpose] || purpose;
}

function localizeDecimals(text) {
  return String(text).replace(/(\d)\.(\d)/g, "$1,$2");
}

function variantLabel(variant) {
  return variant === "pot_limit_omaha" ? "PLO4 · Pot-limit" : "Texas Hold’em";
}

function formatPercent(value) {
  return value == null || !Number.isFinite(Number(value)) ? "—" : `${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function formatChips(value) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const amount = Number(value);
  return `${amount > 0 ? "+" : ""}${amount.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} fichas`;
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
