"""
Professional Editorial PDF Generator for 01_Texas_Holdem_Complete_Guide.md.
Uses ONLY the content from 01_Texas_Holdem_Complete_Guide.md, elevated with
bespoke executive book-level typography, vector diagrams, styled poker cards,
mathematical callout panels, and precision multi-page print pagination.
"""

import os
import sys
import pymupdf
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

HTML_DOCUMENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Texas Hold'em: Complete Reference Guide & Fundamental Theory</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400;1,600&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>

<style>
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :root {
    --emerald-950: #042f1e;
    --emerald-900: #064e3b;
    --emerald-800: #065f46;
    --emerald-700: #047857;
    --emerald-100: #d1fae5;
    --emerald-50:  #ecfdf5;
    --gold-700:    #92610e;
    --gold-600:    #b47b18;
    --gold-500:    #d4AF37;
    --gold-400:    #e5c158;
    --gold-100:    #fef9c3;
    --gold-50:     #fffdf2;
    --slate-950:   #090d16;
    --slate-900:   #0f172a;
    --slate-800:   #1e293b;
    --slate-700:   #334155;
    --slate-600:   #475569;
    --slate-500:   #64748b;
    --slate-300:   #cbd5e1;
    --slate-200:   #e2e8f0;
    --slate-100:   #f1f5f9;
    --slate-50:    #f8fafc;
    --suit-red:    #dc2626;
    --suit-black:  #0f172a;
    --font-display: 'Cinzel', Georgia, serif;
    --font-sans:    'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    --font-mono:    'JetBrains Mono', monospace;
  }

  @page {
    size: A4 portrait;
    margin: 14mm 13mm 14mm 13mm;
  }

  body {
    font-family: var(--font-sans);
    font-size: 8.2pt;
    line-height: 1.38;
    color: var(--slate-800);
    background-color: #ffffff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  .page {
    page-break-after: always;
    break-after: page;
    position: relative;
    width: 100%;
  }

  .page:last-child {
    page-break-after: auto;
    break-after: auto;
  }

  /* =========================================================
     HERO COVER BANNER (PAGE 1)
     ========================================================= */
  .hero-header {
    background: linear-gradient(135deg, var(--slate-950) 0%, var(--emerald-950) 58%, var(--emerald-900) 100%);
    color: #ffffff;
    padding: 18pt 20pt 16pt 20pt;
    border-radius: 8px;
    border-bottom: 3.5px solid var(--gold-500);
    position: relative;
    overflow: hidden;
    margin-bottom: 10pt;
    box-shadow: 0 6px 16px rgba(9, 13, 22, 0.14);
  }

  .hero-watermark {
    position: absolute;
    right: 12pt;
    top: -12pt;
    font-size: 88pt;
    color: rgba(212, 175, 55, 0.07);
    font-family: serif;
    line-height: 1;
    pointer-events: none;
    user-select: none;
  }

  .hero-title {
    font-family: var(--font-display);
    font-size: 19pt;
    font-weight: 800;
    letter-spacing: 0.5px;
    color: #ffffff;
    line-height: 1.18;
    margin-bottom: 5pt;
  }

  .hero-title span {
    color: var(--gold-400);
  }

  .hero-subtitle {
    font-size: 9.2pt;
    font-weight: 400;
    font-style: italic;
    color: #cbd5e1;
    max-width: 92%;
  }

  /* =========================================================
     TABLE OF CONTENTS PANEL
     ========================================================= */
  .toc-box {
    background: var(--slate-50);
    border: 1px solid var(--slate-200);
    border-left: 4px solid var(--emerald-800);
    border-radius: 6px;
    padding: 9pt 14pt;
    margin-bottom: 11pt;
  }

  .toc-header {
    font-family: var(--font-display);
    font-size: 8.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--emerald-900);
    margin-bottom: 6pt;
    border-bottom: 1px solid var(--slate-200);
    padding-bottom: 3pt;
  }

  .toc-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4pt 18pt;
  }

  .toc-entry {
    display: flex;
    align-items: baseline;
    font-size: 8.3pt;
    color: var(--slate-800);
    text-decoration: none;
  }

  .toc-num {
    font-family: var(--font-mono);
    font-weight: 700;
    color: var(--gold-700);
    width: 16pt;
    flex-shrink: 0;
  }

  .toc-label {
    font-weight: 600;
    color: var(--slate-900);
  }

  /* =========================================================
     SECTION & SUBSECTION HEADINGS
     ========================================================= */
  .section-banner {
    display: flex;
    align-items: center;
    gap: 8pt;
    margin: 7pt 0 5pt 0;
    padding-bottom: 3.5pt;
    border-bottom: 2px solid var(--emerald-900);
  }

  .section-badge {
    background: var(--emerald-900);
    color: var(--gold-400);
    font-family: var(--font-mono);
    font-size: 8.2pt;
    font-weight: 700;
    padding: 1.5pt 6pt;
    border-radius: 4px;
    letter-spacing: 0.5px;
  }

  .section-title {
    font-family: var(--font-display);
    font-size: 12pt;
    font-weight: 700;
    color: var(--slate-950);
    letter-spacing: 0.3px;
  }

  h3 {
    font-size: 9.2pt;
    font-weight: 700;
    color: var(--emerald-950);
    margin: 5.5pt 0 2.5pt 0;
    display: flex;
    align-items: center;
    gap: 5pt;
  }

  h3::before {
    content: "";
    display: inline-block;
    width: 3px;
    height: 11px;
    background: var(--gold-500);
    border-radius: 2px;
  }

  p {
    margin-bottom: 4pt;
    color: var(--slate-700);
  }

  ul, ol {
    margin: 0 0 4.5pt 0;
    padding-left: 14pt;
    color: var(--slate-700);
  }

  li {
    margin-bottom: 1.5pt;
  }

  li strong {
    color: var(--slate-900);
  }

  /* =========================================================
     CALLOUTS, CARDS & FORMULA BOXES
     ========================================================= */
  .grid-2col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8pt;
    margin: 5pt 0;
  }

  .info-card {
    background: #ffffff;
    border: 1px solid var(--slate-200);
    border-top: 3px solid var(--emerald-800);
    border-radius: 6px;
    padding: 7pt 10pt;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
  }

  .info-card-gold {
    background: var(--gold-50);
    border: 1px solid #f3e3b0;
    border-left: 4px solid var(--gold-500);
    border-radius: 6px;
    padding: 6.5pt 10pt;
    margin: 5pt 0;
  }

  .info-card-emerald {
    background: var(--emerald-50);
    border: 1px solid #a7f3d0;
    border-left: 4px solid var(--emerald-700);
    border-radius: 6px;
    padding: 6.5pt 10pt;
    margin: 5pt 0;
  }

  .math-panel {
    background: linear-gradient(to right, #f8fafc, #f1f5f9);
    border: 1px solid var(--slate-300);
    border-left: 4px solid var(--emerald-900);
    border-radius: 6px;
    padding: 4pt 10pt;
    margin: 3.5pt 0;
    text-align: center;
  }

  .math-panel .katex-display {
    margin: 1pt 0 !important;
    font-size: 9.2pt;
  }

  /* =========================================================
     PROFESSIONAL DATA TABLES
     ========================================================= */
  .pro-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 5pt 0 8pt 0;
    font-size: 8.1pt;
    border: 1px solid var(--slate-300);
    border-radius: 6px;
    overflow: hidden;
  }

  .pro-table th {
    background: var(--emerald-950);
    color: #ffffff;
    font-weight: 600;
    text-align: left;
    padding: 5.5pt 7pt;
    font-size: 7.8pt;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    border-bottom: 2px solid var(--gold-500);
  }

  .pro-table td {
    padding: 4.8pt 7pt;
    border-bottom: 1px solid var(--slate-200);
    color: var(--slate-700);
    vertical-align: middle;
  }

  .pro-table tr:last-child td {
    border-bottom: none;
  }

  .pro-table tr:nth-child(even) td {
    background: var(--slate-50);
  }

  .pos-badge {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 7.4pt;
    font-weight: 700;
    padding: 1.5pt 5pt;
    border-radius: 4px;
    text-align: center;
    min-width: 44px;
  }
  .pos-utg { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
  .pos-hj  { background: #ffedd5; color: #9a3412; border: 1px solid #fdba74; }
  .pos-co  { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
  .pos-btn { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
  .pos-sb  { background: #e0e7ff; color: #3730a3; border: 1px solid #a5b4fc; }
  .pos-bb  { background: #f3e8ff; color: #6b21a8; border: 1px solid #d8b4fe; }

  /* =========================================================
     HAND RANKINGS CARDS & MINI PLAYING CARDS (PAGE 3)
     ========================================================= */
  .rank-list {
    display: flex;
    flex-direction: column;
    gap: 4.5pt;
    margin-top: 4pt;
  }

  .rank-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #ffffff;
    border: 1px solid var(--slate-200);
    border-left: 3.5px solid var(--emerald-800);
    border-radius: 5px;
    padding: 4pt 8pt;
    gap: 10pt;
  }

  .rank-row.top-tier {
    border-left-color: var(--gold-500);
    background: linear-gradient(to right, #fffdf5, #ffffff 35%);
  }

  .rank-info {
    flex: 1;
  }

  .rank-head {
    display: flex;
    align-items: center;
    gap: 6pt;
    margin-bottom: 1.5pt;
  }

  .rank-num {
    background: var(--emerald-950);
    color: var(--gold-400);
    font-family: var(--font-mono);
    font-size: 7.2pt;
    font-weight: 700;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .rank-name {
    font-size: 8.8pt;
    font-weight: 700;
    color: var(--slate-950);
  }

  .rank-details {
    font-size: 7.65pt;
    color: var(--slate-700);
    line-height: 1.32;
  }

  .cards-group {
    display: flex;
    gap: 3px;
    flex-shrink: 0;
  }

  .p-card {
    width: 24px;
    height: 33px;
    background: #ffffff;
    border: 1px solid #94a3b8;
    border-radius: 3.5px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-family: var(--font-mono);
    box-shadow: 0 1px 2px rgba(0,0,0,0.08);
    line-height: 1;
  }

  .p-card .r {
    font-size: 8.2pt;
    font-weight: 800;
  }

  .p-card .s {
    font-size: 8.5pt;
    margin-top: 1px;
  }

  .p-card.red { color: var(--suit-red); border-color: #fca5a5; background: #fffafa; }
  .p-card.blk { color: var(--suit-black); }

  /* =========================================================
     BETTING STREETS FLOW & CARDS (PAGE 4)
     ========================================================= */
  .street-flow-bar {
    display: flex;
    align-items: stretch;
    justify-content: space-between;
    background: var(--slate-900);
    color: #ffffff;
    border-radius: 6px;
    padding: 4.5pt 6pt;
    margin: 3.5pt 0 5pt 0;
    gap: 3pt;
  }

  .flow-step {
    flex: 1;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(212,175,55,0.28);
    border-radius: 4px;
    padding: 3pt 4pt;
    text-align: center;
  }

  .flow-step-title {
    font-family: var(--font-mono);
    font-size: 6.9pt;
    font-weight: 700;
    color: var(--gold-400);
    text-transform: uppercase;
  }

  .flow-step-desc {
    font-size: 6.4pt;
    color: #e2e8f0;
    margin-top: 1pt;
    line-height: 1.2;
  }

  .flow-arrow {
    display: flex;
    align-items: center;
    color: var(--gold-400);
    font-weight: 700;
    font-size: 9pt;
  }

  .streets-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 5pt;
    margin-bottom: 4.5pt;
  }

  .street-box {
    background: #ffffff;
    border: 1px solid var(--slate-200);
    border-top: 2.5px solid var(--emerald-800);
    border-radius: 5px;
    padding: 4.5pt 7pt;
  }

  .street-box-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2.5pt;
    padding-bottom: 2pt;
    border-bottom: 1px solid var(--slate-100);
  }

  .street-box-title {
    font-weight: 700;
    font-size: 8.3pt;
    color: var(--emerald-950);
  }

  .street-pill {
    font-family: var(--font-mono);
    font-size: 6.5pt;
    font-weight: 600;
    background: var(--emerald-50);
    color: var(--emerald-800);
    border: 1px solid #a7f3d0;
    padding: 0.5pt 4pt;
    border-radius: 3px;
  }

  .street-box ol {
    margin-bottom: 0;
    padding-left: 12pt;
    font-size: 7.3pt;
    line-height: 1.3;
  }

  .street-box li {
    margin-bottom: 1pt;
  }

  /* =========================================================
     SIDE POT DIAGRAM (PAGE 4)
     ========================================================= */
  .sidepot-card {
    background: var(--slate-900);
    color: #f8fafc;
    border-radius: 6px;
    padding: 6pt 10pt;
    margin-top: 3.5pt;
    border-left: 4px solid var(--gold-500);
    font-family: var(--font-mono);
    font-size: 7.3pt;
  }

  .sidepot-players {
    display: flex;
    gap: 10pt;
    margin-bottom: 3.5pt;
    padding-bottom: 3pt;
    border-bottom: 1px solid #334155;
  }

  .sp-badge {
    background: rgba(255,255,255,0.08);
    padding: 2pt 6pt;
    border-radius: 4px;
    color: var(--gold-400);
    font-weight: 600;
  }

  /* =========================================================
     GLOSSARY GRID (PAGE 6)
     ========================================================= */
  .glossary-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 5.5pt;
    margin-top: 5pt;
  }

  .glossary-card {
    background: var(--slate-50);
    border: 1px solid var(--slate-200);
    border-left: 3px solid var(--emerald-800);
    border-radius: 4px;
    padding: 4.5pt 7.5pt;
  }

  .glossary-term {
    font-weight: 700;
    font-size: 8.2pt;
    color: var(--emerald-950);
    margin-bottom: 1pt;
  }

  .glossary-desc {
    font-size: 7.65pt;
    color: var(--slate-700);
    line-height: 1.32;
  }
</style>
</head>
<body>

<!-- =====================================================================
     PAGE 1: COVER HEADER, TOC & SECTION 1 (INTRODUCTION & PHILOSOPHY)
     ===================================================================== -->
<div class="page">
  <div class="hero-header">
    <div class="hero-watermark">&#9824;</div>
    <div class="hero-title">Texas Hold'em: <span>Complete Reference Guide &amp; Fundamental Theory</span></div>
    <div class="hero-subtitle">A comprehensive guide to rules, table dynamics, mathematical foundations, and strategic principles.</div>
  </div>

  <div class="toc-box">
    <div class="toc-header">Table of Contents</div>
    <div class="toc-grid">
      <div class="toc-entry"><span class="toc-num">01</span><span class="toc-label">Introduction &amp; Game Philosophy</span></div>
      <div class="toc-entry"><span class="toc-num">05</span><span class="toc-label">Betting Rules, Limits &amp; Pot Management</span></div>
      <div class="toc-entry"><span class="toc-num">02</span><span class="toc-label">Table Anatomy, Positions &amp; Blinds</span></div>
      <div class="toc-entry"><span class="toc-num">06</span><span class="toc-label">Fundamental Mathematics of Hold'em</span></div>
      <div class="toc-entry"><span class="toc-num">03</span><span class="toc-label">Hand Rankings &amp; Evaluation Mechanics</span></div>
      <div class="toc-entry"><span class="toc-num">07</span><span class="toc-label">Core Strategic Principles (The Hold'em Bridge)</span></div>
      <div class="toc-entry"><span class="toc-num">04</span><span class="toc-label">The Structure of a Hand (The Four Betting Streets)</span></div>
      <div class="toc-entry"><span class="toc-num">08</span><span class="toc-label">Glossary of Essential Terminology</span></div>
    </div>
  </div>

  <div class="section-banner">
    <span class="section-badge">01</span>
    <span class="section-title">Introduction &amp; Game Philosophy</span>
  </div>

  <p>No-Limit Texas Hold'em (NLHE) is the world's most widely played poker variant. While the basic mechanics can be learned in minutes, mastering the game requires deep understanding of probability, game theory, psychology, and risk management.</p>

  <p>At its core, Texas Hold'em is a <strong>game of incomplete information</strong>. Unlike chess, where both players observe all pieces on the board at all times, poker challenges each player to deduce hidden information (opponents' private hole cards and intentions) from observable actions:</p>

  <div class="grid-2col" style="margin-bottom: 7pt;">
    <div class="info-card" style="padding: 5pt 8pt;">
      <ul style="margin-bottom: 0;">
        <li><strong>Bet sizing and timing</strong></li>
        <li><strong>Board texture evolution</strong></li>
      </ul>
    </div>
    <div class="info-card" style="padding: 5pt 8pt;">
      <ul style="margin-bottom: 0;">
        <li><strong>Historical frequencies and player tendencies</strong></li>
        <li><strong>Positional dynamics</strong></li>
      </ul>
    </div>
  </div>

  <h3>The Hold'em vs. Omaha (PLO) Paradigm</h3>
  <div class="info-card-emerald">
    <p style="margin-bottom: 3pt; color: var(--emerald-950); font-weight: 600;">In Texas Hold'em:</p>
    <ul style="margin-bottom: 4pt;">
      <li>Each player is dealt <strong>2 private hole cards</strong>.</li>
      <li>Up to <strong>5 community cards</strong> are dealt face-up on the board.</li>
      <li>To form a hand, a player may use <strong>any combination</strong> of their hole cards and board cards:
        <ul style="margin-top: 2pt;">
          <li>Both hole cards and 3 board cards</li>
          <li>One hole card and 4 board cards</li>
          <li>Zero hole cards and all 5 board cards (<em>"playing the board"</em>)</li>
        </ul>
      </li>
    </ul>
    <p style="margin-bottom: 0; font-size: 7.9pt; font-style: italic; color: var(--emerald-900);">
      (Note: This is the fundamental contrast with Pot-Limit Omaha, detailed in Lesson 11 of your study companion, where a player is dealt 4 hole cards and <strong>must</strong> use exactly 2 hole cards and exactly 3 board cards).
    </p>
  </div>

  <p style="margin-top: 6pt;">Because players have only 2 hole cards, there are exactly:</p>

  <div class="math-panel">
    $$\binom{52}{2} = \frac{52 \times 51}{2} = 1,326 \text{ starting hand combinations}$$
  </div>

  <p style="margin-top: 5pt;">This manageable state space makes Texas Hold'em the premier pedagogical foundation—the <strong>"Hold'em Bridge"</strong>—for mastering position, ranges, pot odds, and expected value before tackling high-complexity games like PLO (which has 270,725 starting combos).</p>
</div>

<!-- =====================================================================
     PAGE 2: SECTION 2 (TABLE ANATOMY, POSITIONS & BLINDS)
     ===================================================================== -->
<div class="page">
  <div class="section-banner" style="margin-top: 0;">
    <span class="section-badge">02</span>
    <span class="section-title">Table Anatomy, Positions &amp; Blinds</span>
  </div>

  <h3>2.1 The Table Layout (6-Max vs. Full Ring)</h3>
  <p>In modern cash games, the <strong>6-Max</strong> format (6 players per table) is standard. In full ring games, 9 or 10 players participate. The seats rotate clockwise around the <strong>Dealer Button (BTN)</strong> after every hand:</p>

  <!-- Crisp Vector Representation of the Markdown 6-Max Table Layout -->
  <div style="text-align: center; margin: 6pt 0 8pt 0;">
    <svg viewBox="0 0 680 215" style="width: 100%; max-width: 620px; height: auto;">
      <defs>
        <radialGradient id="feltGrad" cx="50%" cy="50%" r="55%">
          <stop offset="0%" stop-color="#065f46"/>
          <stop offset="100%" stop-color="#042f1e"/>
        </radialGradient>
      </defs>
      <!-- Outer Rail -->
      <rect x="30" y="15" width="620" height="185" rx="92.5" fill="#1e293b" stroke="#d4af37" stroke-width="3"/>
      <!-- Inner Felt -->
      <rect x="42" y="27" width="596" height="161" rx="80.5" fill="url(#feltGrad)" stroke="#047857" stroke-width="2"/>
      <!-- Inner Betting Line -->
      <rect x="64" y="47" width="552" height="121" rx="60.5" fill="none" stroke="rgba(212,175,55,0.35)" stroke-width="1.2" stroke-dasharray="5,4"/>

      <!-- Center Title -->
      <text x="340" y="103" text-anchor="middle" fill="#e5c158" font-family="'Cinzel', serif" font-weight="700" font-size="11" letter-spacing="1.2">6-MAX TABLE LAYOUT</text>
      <text x="340" y="120" text-anchor="middle" fill="#a7f3d0" font-family="'Plus Jakarta Sans', sans-serif" font-size="8" font-weight="500">Seats Rotate Clockwise Around the Dealer Button (BTN)</text>

      <!-- Top Center: Small Blind (SB) -->
      <g transform="translate(340, 27)">
        <rect x="-70" y="-14" width="140" height="28" rx="14" fill="#e0e7ff" stroke="#4f46e5" stroke-width="1.8"/>
        <text x="0" y="4" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="700" font-size="8.5" fill="#312e81">Small Blind (SB)</text>
      </g>

      <!-- Top Right / Upper Right: Big Blind (BB) -->
      <g transform="translate(555, 68)">
        <rect x="-68" y="-14" width="136" height="28" rx="14" fill="#f3e8ff" stroke="#7e22ce" stroke-width="1.8"/>
        <text x="0" y="4" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="700" font-size="8.5" fill="#581c87">Big Blind (BB)</text>
      </g>

      <!-- Lower Right: Under the Gun (UTG) -->
      <g transform="translate(555, 148)">
        <rect x="-78" y="-14" width="156" height="28" rx="14" fill="#fee2e2" stroke="#dc2626" stroke-width="1.8"/>
        <text x="0" y="4" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="700" font-size="8.5" fill="#991b1b">Under the Gun (UTG)</text>
      </g>

      <!-- Bottom Center: Hijack (HJ / MP) -->
      <g transform="translate(340, 188)">
        <rect x="-72" y="-14" width="144" height="28" rx="14" fill="#ffedd5" stroke="#ea580c" stroke-width="1.8"/>
        <text x="0" y="4" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="700" font-size="8.5" fill="#9a3412">Hijack (HJ / MP)</text>
      </g>

      <!-- Lower Left: Cutoff (CO) -->
      <g transform="translate(125, 148)">
        <rect x="-62" y="-14" width="124" height="28" rx="14" fill="#fef3c7" stroke="#d97706" stroke-width="1.8"/>
        <text x="0" y="4" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="700" font-size="8.5" fill="#92400e">Cutoff (CO)</text>
      </g>

      <!-- Upper Left: Button (BTN) -->
      <g transform="translate(125, 68)">
        <rect x="-65" y="-14" width="130" height="28" rx="14" fill="#dcfce7" stroke="#16a34a" stroke-width="2"/>
        <text x="0" y="4" text-anchor="middle" font-family="'Plus Jakarta Sans', sans-serif" font-weight="800" font-size="8.5" fill="#14532d">Button (BTN)</text>
        <circle cx="52" cy="-14" r="9" fill="#d4af37" stroke="#ffffff" stroke-width="1.5"/>
        <text x="52" y="-11" text-anchor="middle" font-family="'JetBrains Mono', monospace" font-weight="800" font-size="7.5" fill="#090d16">D</text>
      </g>
    </svg>
  </div>

  <h3>2.2 Table Positions and Their Order of Action</h3>

  <table class="pro-table">
    <thead>
      <tr>
        <th style="width: 14%;">Position Code</th>
        <th style="width: 22%;">Position Name</th>
        <th style="width: 18%;">Preflop Action Order</th>
        <th style="width: 18%;">Postflop Action Order</th>
        <th style="width: 28%;">Strategic Character</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="pos-badge pos-utg">UTG</span></td>
        <td><strong>Under the Gun</strong></td>
        <td><strong>1st</strong> (Acts first)</td>
        <td>3rd to 6th</td>
        <td>Tightest range. Maximum players left to act behind.</td>
      </tr>
      <tr>
        <td><span class="pos-badge pos-hj">HJ / MP</span></td>
        <td><strong>Hijack / Middle Position</strong></td>
        <td>2nd</td>
        <td>3rd to 5th</td>
        <td>Moderately tight. Begins loosening hand selection.</td>
      </tr>
      <tr>
        <td><span class="pos-badge pos-co">CO</span></td>
        <td><strong>Cutoff</strong></td>
        <td>3rd</td>
        <td>2nd to 4th</td>
        <td>Wide range. Prime position to steal the blinds.</td>
      </tr>
      <tr>
        <td><span class="pos-badge pos-btn">BTN</span></td>
        <td><strong>The Button</strong></td>
        <td>4th</td>
        <td><strong>Last</strong> (Acts last on all postflop streets)</td>
        <td><strong>Most profitable seat at the table.</strong> Complete informational advantage.</td>
      </tr>
      <tr>
        <td><span class="pos-badge pos-sb">SB</span></td>
        <td><strong>Small Blind</strong></td>
        <td>5th</td>
        <td><strong>1st</strong> (Acts first postflop)</td>
        <td>Out of position (OOP) the entire hand. Worst seat postflop.</td>
      </tr>
      <tr>
        <td><span class="pos-badge pos-bb">BB</span></td>
        <td><strong>Big Blind</strong></td>
        <td>6th (Closes preflop action)</td>
        <td><strong>2nd</strong> (Acts second postflop)</td>
        <td>Defends with pot-discount preflop, but plays OOP postflop.</td>
      </tr>
    </tbody>
  </table>

  <h3>2.3 The Blinds</h3>
  <p>Before any cards are dealt, two forced bets must be posted to initiate action:</p>
  <div class="grid-2col">
    <div class="info-card">
      <div style="font-weight: 700; color: var(--emerald-950); margin-bottom: 2pt;">1. Small Blind (SB)</div>
      <p style="margin-bottom: 0; font-size: 8.1pt;">Posted by the player directly left of the Button (typically equal to \(0.5 \times \text{Big Blind}\)).</p>
    </div>
    <div class="info-card">
      <div style="font-weight: 700; color: var(--emerald-950); margin-bottom: 2pt;">2. Big Blind (BB)</div>
      <p style="margin-bottom: 0; font-size: 8.1pt;">Posted by the player directly left of the Small Blind (sets the baseline unit of currency for the hand, e.g., in a $1/$2 game, the SB is $1 and the BB is $2).</p>
    </div>
  </div>
  <div class="info-card-gold" style="margin-top: 6pt;">
    The blinds ensure that folding indefinitely has a real monetary cost, forcing players into action.
  </div>
</div>

<!-- =====================================================================
     PAGE 3: SECTION 3 (HAND RANKINGS & EVALUATION MECHANICS)
     ===================================================================== -->
<div class="page">
  <div class="section-banner" style="margin-top: 0;">
    <span class="section-badge">03</span>
    <span class="section-title">Hand Rankings &amp; Evaluation Mechanics</span>
  </div>

  <p>In Texas Hold'em, every player creates the best possible <strong>5-card hand</strong> out of the 7 available cards (2 hole cards + 5 board cards). All remaining cards are disregarded.</p>

  <h3>3.1 &amp; 3.2 Official Hierarchy of 5-Card Hands, Detailed Descriptions &amp; Tie-Breaking Rules</h3>

  <div class="rank-list">
    <!-- 1. Royal Flush -->
    <div class="rank-row top-tier">
      <div class="rank-info">
        <div class="rank-head"><span class="rank-num">1</span><span class="rank-name">Royal Flush</span></div>
        <div class="rank-details">
          <strong>Definition:</strong> An Ace-high straight of the exact same suit (\(A\text{-}K\text{-}Q\text{-}J\text{-}10\)).<br>
          <strong>Tie-break:</strong> Cannot be beaten. If two players hit a royal flush (only possible when it is on the board), the pot is split equally.
        </div>
      </div>
      <div class="cards-group">
        <div class="p-card blk"><span class="r">A</span><span class="s">&spades;</span></div>
        <div class="p-card blk"><span class="r">K</span><span class="s">&spades;</span></div>
        <div class="p-card blk"><span class="r">Q</span><span class="s">&spades;</span></div>
        <div class="p-card blk"><span class="r">J</span><span class="s">&spades;</span></div>
        <div class="p-card blk"><span class="r">T</span><span class="s">&spades;</span></div>
      </div>
    </div>

    <!-- 2. Straight Flush -->
    <div class="rank-row top-tier">
      <div class="rank-info">
        <div class="rank-head"><span class="rank-num">2</span><span class="rank-name">Straight Flush</span></div>
        <div class="rank-details">
          <strong>Definition:</strong> Five consecutive ranks of identical suit.<br>
          <strong>Tie-break:</strong> The highest rank at the top of the sequence wins. Example: \(9\text{-}8\text{-}7\text{-}6\text{-}5\) beats \(8\text{-}7\text{-}6\text{-}5\text{-}4\).
        </div>
      </div>
      <div class="cards-group">
        <div class="p-card red"><span class="r">9</span><span class="s">&hearts;</span></div>
        <div class="p-card red"><span class="r">8</span><span class="s">&hearts;</span></div>
        <div class="p-card red"><span class="r">7</span><span class="s">&hearts;</span></div>
        <div class="p-card red"><span class="r">6</span><span class="s">&hearts;</span></div>
        <div class="p-card red"><span class="r">5</span><span class="s">&hearts;</span></div>
      </div>
    </div>

    <!-- 3. Four of a Kind -->
    <div class="rank-row">
      <div class="rank-info">
        <div class="rank-head"><span class="rank-num">3</span><span class="rank-name">Four of a Kind (Quads)</span></div>
        <div class="rank-details">
          <strong>Definition:</strong> Four cards of identical rank plus one kicker.<br>
          <strong>Tie-break:</strong> Higher rank quads beat lower rank quads (\(K\text{-}K\text{-}K\text{-}K\) beats \(Q\text{-}Q\text{-}Q\text{-}Q\)). If quads are on the board, the player with the highest 5th card (<strong>kicker</strong>) wins.
        </div>
      </div>
      <div class="cards-group">
        <div class="p-card blk"><span class="r">J</span><span class="s">&spades;</span></div>
        <div class="p-card red"><span class="r">J</span><span class="s">&hearts;</span></div>
        <div class="p-card red"><span class="r">J</span><span class="s">&diams;</span></div>
        <div class="p-card blk"><span class="r">J</span><span class="s">&clubs;</span></div>
        <div class="p-card blk"><span class="r">4</span><span class="s">&spades;</span></div>
      </div>
    </div>

    <!-- 4. Full House -->
    <div class="rank-row">
      <div class="rank-info">
        <div class="rank-head"><span class="rank-num">4</span><span class="rank-name">Full House (Boat)</span></div>
        <div class="rank-details">
          <strong>Definition:</strong> Three cards of one rank plus two cards of another rank.<br>
          <strong>Tie-break:</strong> The rank of the three-of-a-kind determines the winner first. If identical, the rank of the pair determines the winner. Example: \(8\text{-}8\text{-}8\text{-}4\text{-}4\) beats \(7\text{-}7\text{-}7\text{-}A\text{-}A\) (8s full beats 7s full). Example: \(K\text{-}K\text{-}K\text{-}J\text{-}J\) beats \(K\text{-}K\text{-}K\text{-}T\text{-}T\).
        </div>
      </div>
      <div class="cards-group">
        <div class="p-card blk"><span class="r">K</span><span class="s">&spades;</span></div>
        <div class="p-card red"><span class="r">K</span><span class="s">&hearts;</span></div>
        <div class="p-card red"><span class="r">K</span><span class="s">&diams;</span></div>
        <div class="p-card blk"><span class="r">8</span><span class="s">&clubs;</span></div>
        <div class="p-card blk"><span class="r">8</span><span class="s">&spades;</span></div>
      </div>
    </div>

    <!-- 5. Flush -->
    <div class="rank-row">
      <div class="rank-info">
        <div class="rank-head"><span class="rank-num">5</span><span class="rank-name">Flush</span></div>
        <div class="rank-details">
          <strong>Definition:</strong> Five cards of the same suit, not in sequential rank.<br>
          <strong>Tie-break:</strong> The highest individual card wins. If highest cards match, compare 2nd highest, then 3rd, 4th, and 5th. Example: \(A\text{-}K\text{-}8\text{-}6\text{-}2\) of spades beats \(A\text{-}Q\text{-}J\text{-}9\text{-}7\) of spades.
        </div>
      </div>
      <div class="cards-group">
        <div class="p-card red"><span class="r">A</span><span class="s">&diams;</span></div>
        <div class="p-card red"><span class="r">J</span><span class="s">&diams;</span></div>
        <div class="p-card red"><span class="r">8</span><span class="s">&diams;</span></div>
        <div class="p-card red"><span class="r">6</span><span class="s">&diams;</span></div>
        <div class="p-card red"><span class="r">2</span><span class="s">&diams;</span></div>
      </div>
    </div>

    <!-- 6. Straight -->
    <div class="rank-row">
      <div class="rank-info">
        <div class="rank-head"><span class="rank-num">6</span><span class="rank-name">Straight</span></div>
        <div class="rank-details">
          <strong>Definition:</strong> Five consecutive cards of mixed suits. <strong>Special Ace Rules:</strong> An Ace can act as the highest card (\(A\text{-}K\text{-}Q\text{-}J\text{-}T\), the "Broadway" straight) or the lowest card (\(5\text{-}4\text{-}3\text{-}2\text{-}A\), the "Wheel" straight). <em>Crucial note:</em> The Ace <strong>cannot wrap around</strong> (e.g., \(Q\text{-}K\text{-}A\text{-}2\text{-}3\) is <strong>not</strong> a valid straight). <strong>Tie-break:</strong> Highest card at the top of the straight wins.
        </div>
      </div>
      <div class="cards-group">
        <div class="p-card blk"><span class="r">T</span><span class="s">&spades;</span></div>
        <div class="p-card red"><span class="r">9</span><span class="s">&diams;</span></div>
        <div class="p-card red"><span class="r">8</span><span class="s">&hearts;</span></div>
        <div class="p-card blk"><span class="r">7</span><span class="s">&clubs;</span></div>
        <div class="p-card blk"><span class="r">6</span><span class="s">&spades;</span></div>
      </div>
    </div>

    <!-- 7. Three of a Kind -->
    <div class="rank-row">
      <div class="rank-info">
        <div class="rank-head"><span class="rank-num">7</span><span class="rank-name">Three of a Kind / Trips / Set</span></div>
        <div class="rank-details">
          <strong>Set vs. Trips:</strong> <strong>Set:</strong> You hold a pocket pair (e.g., \(7\spadesuit 7\heartsuit\)) and one 7 hits the board. Highly disguised, massive value. <strong>Trips:</strong> Two 7s are on the board, and you hold one 7. Less disguised, more easily countered.<br>
          <strong>Tie-break:</strong> Highest three-of-a-kind wins. If shared on the board, the highest remaining kickers determine the winner.
        </div>
      </div>
      <div class="cards-group">
        <div class="p-card blk"><span class="r">7</span><span class="s">&spades;</span></div>
        <div class="p-card red"><span class="r">7</span><span class="s">&hearts;</span></div>
        <div class="p-card red"><span class="r">7</span><span class="s">&diams;</span></div>
        <div class="p-card blk"><span class="r">A</span><span class="s">&clubs;</span></div>
        <div class="p-card blk"><span class="r">5</span><span class="s">&spades;</span></div>
      </div>
    </div>

    <!-- 8. Two Pair -->
    <div class="rank-row">
      <div class="rank-info">
        <div class="rank-head"><span class="rank-num">8</span><span class="rank-name">Two Pair</span></div>
        <div class="rank-details">
          <strong>Definition:</strong> Two cards of one rank, two cards of another rank, and one kicker.<br>
          <strong>Tie-break:</strong> Highest pair wins first (\(A\text{-}A\text{-}2\text{-}2\) beats \(K\text{-}K\text{-}Q\text{-}Q\)). If the top pairs are equal, the second pair decides. If both pairs are equal, the 5th card kicker decides.
        </div>
      </div>
      <div class="cards-group">
        <div class="p-card blk"><span class="r">A</span><span class="s">&spades;</span></div>
        <div class="p-card red"><span class="r">A</span><span class="s">&diams;</span></div>
        <div class="p-card red"><span class="r">T</span><span class="s">&hearts;</span></div>
        <div class="p-card blk"><span class="r">T</span><span class="s">&clubs;</span></div>
        <div class="p-card blk"><span class="r">Q</span><span class="s">&spades;</span></div>
      </div>
    </div>

    <!-- 9. One Pair -->
    <div class="rank-row">
      <div class="rank-info">
        <div class="rank-head"><span class="rank-num">9</span><span class="rank-name">One Pair</span></div>
        <div class="rank-details">
          <strong>Definition:</strong> Two cards of identical rank and three unpaired kickers.<br>
          <strong>Tie-break:</strong> Higher pair wins. If pairs are equal, kickers are evaluated in descending order.
        </div>
      </div>
      <div class="cards-group">
        <div class="p-card blk"><span class="r">K</span><span class="s">&spades;</span></div>
        <div class="p-card red"><span class="r">K</span><span class="s">&diams;</span></div>
        <div class="p-card blk"><span class="r">Q</span><span class="s">&clubs;</span></div>
        <div class="p-card blk"><span class="r">8</span><span class="s">&spades;</span></div>
        <div class="p-card red"><span class="r">3</span><span class="s">&hearts;</span></div>
      </div>
    </div>

    <!-- 10. High Card -->
    <div class="rank-row">
      <div class="rank-info">
        <div class="rank-head"><span class="rank-num">10</span><span class="rank-name">High Card</span></div>
        <div class="rank-details">
          <strong>Definition:</strong> No pair, no sequence, not all same suit.<br>
          <strong>Tie-break:</strong> The single highest card wins, followed by kickers down to the 5th card.
        </div>
      </div>
      <div class="cards-group">
        <div class="p-card blk"><span class="r">A</span><span class="s">&spades;</span></div>
        <div class="p-card red"><span class="r">Q</span><span class="s">&diams;</span></div>
        <div class="p-card red"><span class="r">9</span><span class="s">&hearts;</span></div>
        <div class="p-card blk"><span class="r">7</span><span class="s">&clubs;</span></div>
        <div class="p-card blk"><span class="r">4</span><span class="s">&spades;</span></div>
      </div>
    </div>
  </div>
</div>

<!-- =====================================================================
     PAGE 4: SECTION 4 (STREETS) & SECTION 5 (BETTING & SIDE POTS)
     ===================================================================== -->
<div class="page">
  <div class="section-banner" style="margin-top: 0;">
    <span class="section-badge">04</span>
    <span class="section-title">The Structure of a Hand (The Four Betting Streets)</span>
  </div>

  <p>A single hand of Texas Hold'em proceeds through four distinct betting rounds. If at any point all players except one fold, the remaining player immediately wins the pot without having to reveal their cards.</p>

  <!-- Visual Flowchart Progression from Markdown -->
  <div class="street-flow-bar">
    <div class="flow-step">
      <div class="flow-step-title">1. Dealing &amp; Preflop</div>
      <div class="flow-step-desc">2 Hole Cards Dealt<br>Round 1 (UTG starts)</div>
    </div>
    <div class="flow-arrow">&rarr;</div>
    <div class="flow-step">
      <div class="flow-step-title">2. The Flop</div>
      <div class="flow-step-desc">Burn 1, Deal 3 Cards<br>Round 2 (SB/OOP starts)</div>
    </div>
    <div class="flow-arrow">&rarr;</div>
    <div class="flow-step">
      <div class="flow-step-title">3. The Turn</div>
      <div class="flow-step-desc">Burn 1, Deal 1 Card<br>Round 3 (SB/OOP starts)</div>
    </div>
    <div class="flow-arrow">&rarr;</div>
    <div class="flow-step">
      <div class="flow-step-title">4. The River</div>
      <div class="flow-step-desc">Burn 1, Deal 1 Card<br>Round 4 (SB/OOP starts)</div>
    </div>
    <div class="flow-arrow">&rarr;</div>
    <div class="flow-step" style="border-color: var(--gold-400); background: rgba(212,175,55,0.15);">
      <div class="flow-step-title">5. Showdown</div>
      <div class="flow-step-desc">Remaining players reveal best 5-card hand</div>
    </div>
  </div>

  <div class="streets-grid">
    <!-- Street 1 -->
    <div class="street-box">
      <div class="street-box-header">
        <span class="street-box-title">Street 1: Preflop</span>
        <span class="street-pill">2 Hole Cards</span>
      </div>
      <ol>
        <li><strong>Dealing:</strong> The dealer deals one card clockwise to each player, starting with the SB, then a second card, until everyone has 2 private hole cards.</li>
        <li><strong>Action Begins:</strong> The player sitting <strong>Under the Gun (UTG)</strong> acts first.</li>
        <li><strong>Legal Options:</strong>
          <ul>
            <li><strong>Fold:</strong> Discard cards into the muck; forfeit any claim to the pot.</li>
            <li><strong>Call:</strong> Match the amount of the Big Blind.</li>
            <li><strong>Raise:</strong> Increase the bet. In No-Limit, the minimum raise must at least equal the size of the previous bet/raise (e.g., if the BB is $2, the minimum raise is to $4).</li>
          </ul>
        </li>
        <li>Action continues clockwise around the table. The Big Blind is the last player to act preflop. If no player raised, the BB has the option to <strong>Check</strong> (keep their cards and see the flop for free) or <strong>Raise</strong>.</li>
      </ol>
    </div>

    <!-- Street 2 -->
    <div class="street-box">
      <div class="street-box-header">
        <span class="street-box-title">Street 2: The Flop</span>
        <span class="street-pill">3 Community Cards</span>
      </div>
      <ol>
        <li><strong>Burn &amp; Turn:</strong> The dealer "burns" (discards face down) the top card of the deck to prevent cheating/marked card reads, then deals <strong>3 community cards face up</strong> in the center of the table.</li>
        <li><strong>Action Begins:</strong> The first active player seated to the left of the Button (usually SB or BB) acts first.</li>
        <li><strong>Legal Options:</strong>
          <ul>
            <li><strong>Check:</strong> Pass the action to the next player without betting (only permitted if no bet has been made on this street).</li>
            <li><strong>Bet:</strong> Place chips into the pot.</li>
            <li><strong>Fold / Call / Raise:</strong> If a player has bet, subsequent players must either fold, call that bet, or raise it.</li>
          </ul>
        </li>
      </ol>
    </div>

    <!-- Street 3 -->
    <div class="street-box">
      <div class="street-box-header">
        <span class="street-box-title">Street 3: The Turn (Fourth Street)</span>
        <span class="street-pill">4th Community Card</span>
      </div>
      <ol>
        <li><strong>Burn &amp; Turn:</strong> The dealer burns one card and deals <strong>1 single community card</strong> face up alongside the flop (now 4 community cards visible).</li>
        <li><strong>Action:</strong> Identical structure to the Flop. Because the pot is now larger, bet sizes typically scale up significantly, creating high-leverage inflection points.</li>
      </ol>
    </div>

    <!-- Street 4 -->
    <div class="street-box">
      <div class="street-box-header">
        <span class="street-box-title">Street 4: The River (Fifth Street)</span>
        <span class="street-pill">5th Community Card</span>
      </div>
      <ol>
        <li><strong>Burn &amp; Turn:</strong> The dealer burns one final card and deals the <strong>5th and final community card</strong> face up.</li>
        <li><strong>Action:</strong> The final betting round occurs.</li>
        <li><strong>Strategic Reality:</strong> No more cards can be dealt. Draws have either hit or missed. Betting on the river is strictly <strong>polarized</strong>: a player is either betting a strong made hand for <strong>value</strong> (hoping to be called by worse) or betting a missed hand as a <strong>pure bluff</strong> (hoping to fold out better).</li>
      </ol>
    </div>
  </div>

  <div class="info-card" style="margin-bottom: 8pt; padding: 5.5pt 9pt;">
    <div style="font-weight: 700; color: var(--emerald-950); margin-bottom: 2pt;">The Showdown</div>
    <p style="font-size: 7.9pt; margin-bottom: 2pt;">If two or more players remain active after the river betting concludes:</p>
    <ol style="font-size: 7.8pt; margin-bottom: 0;">
      <li>The last aggressor (the player who made the last uncalled bet or raise on the river) must show their cards first. If there was no bet on the river, the player in the earliest position shows first.</li>
      <li>Any player holding a worse hand may simply muck (discard without showing) to protect their strategic information, or show their hand.</li>
      <li>The player with the highest-ranking 5-card hand takes the pot. In case of an identical 5-card hand, the pot is split equally (<strong>Chop</strong>).</li>
    </ol>
  </div>

  <div class="section-banner" style="margin-top: 4pt;">
    <span class="section-badge">05</span>
    <span class="section-title">Betting Rules, Limits &amp; Pot Management</span>
  </div>

  <div class="grid-2col">
    <div>
      <h3 style="margin-top: 0;">5.1 No-Limit Betting Rules</h3>
      <ul style="font-size: 7.9pt;">
        <li><strong>No Maximum Cap:</strong> At any point during their turn, a player may wager any amount up to their entire stack of chips on the table ("All-In").</li>
        <li><strong>Minimum Bet:</strong> The minimum allowable bet on any street equals the current Big Blind.</li>
        <li><strong>Minimum Raise:</strong> A raise must be at least the size of the previous bet or raise in the same round.
          <ul>
            <li><em>Example:</em> If Player A bets $10, Player B's minimum raise is $10 more (total $20). If Player B raises to $30 (a raise of $20), Player C's minimum re-raise must be at least $20 more (total $50).</li>
          </ul>
        </li>
      </ul>
    </div>
    <div>
      <h3 style="margin-top: 0;">5.2 All-In and Side Pot Mechanics</h3>
      <p style="font-size: 7.8pt;">A player cannot be forced out of a hand simply because they do not have enough chips to match an opponent's wager ("table stakes" rule). When a player commits all their remaining chips, one or more <strong>Side Pots</strong> are created:</p>
      <ol style="font-size: 7.8pt; margin-bottom: 0;">
        <li><strong>Main Pot:</strong> Formed by the all-in player's chips plus an equal amount contributed by all callers. The all-in player is eligible to win <em>only</em> the Main Pot.</li>
        <li><strong>Side Pot 1:</strong> Formed by additional chips bet by the remaining players with deeper stacks. The all-in player has zero equity in the Side Pot.</li>
        <li><strong>Resolution:</strong> The side pot is evaluated first among the active callers. Then the main pot is evaluated including the all-in player.</li>
      </ol>
    </div>
  </div>

  <div class="sidepot-card">
    <div class="sidepot-players">
      <span class="sp-badge">Player A (All-in for $20)</span>
      <span class="sp-badge">Player B (Calls $50)</span>
      <span class="sp-badge">Player C (Calls $50)</span>
      <span style="margin-left: auto; color: #ffffff; font-weight: 700;">Total Money in Play: $120</span>
    </div>
    <div style="line-height: 1.45;">
      &#9500;&#9472;&#9472; <strong style="color: #6ee7b7;">Main Pot:</strong> $20 (from A) + $20 (from B) + $20 (from C) = <strong>$60</strong> &nbsp;&rarr;&nbsp; <span style="color: #a7f3d0;">Contested by A, B, and C</span><br>
      &#9492;&#9472;&#9472; <strong style="color: #fcd34d;">Side Pot:</strong> $30 (from B) + $30 (from C) = <strong>$60</strong> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&rarr;&nbsp; <span style="color: #fde68a;">Contested ONLY by B and C</span>
    </div>
  </div>
</div>

<!-- =====================================================================
     PAGE 5: SECTION 6 (FUNDAMENTAL MATHEMATICS OF HOLD'EM)
     ===================================================================== -->
<div class="page">
  <div class="section-banner" style="margin-top: 0;">
    <span class="section-badge">06</span>
    <span class="section-title">Fundamental Mathematics of Hold'em</span>
  </div>

  <p>Poker is a probabilistic discipline. Decisions must be governed by mathematical expectation rather than intuition or short-term outcome bias.</p>

  <h3>6.1 Combinatorics: Counting Hands</h3>
  <p>Understanding hand frequencies is essential for range construction:</p>
  <ul>
    <li>Total unique starting hands: \(1,326\)</li>
    <li>Any specific Pocket Pair (e.g., \(A\spadesuit A\heartsuit\)): \(\binom{4}{2} = 6\) combinations.</li>
    <li>Any specific Suited hand (e.g., \(A\spadesuit K\spadesuit\)): \(4\) combinations.</li>
    <li>Any specific Offsuit hand (e.g., \(A\spadesuit K\heartsuit\)): \(4 \times 3 = 12\) combinations.</li>
  </ul>

  <table class="pro-table" style="margin-bottom: 8pt;">
    <thead>
      <tr>
        <th>Hand Category</th>
        <th>Formula Breakdown</th>
        <th>Total Combinations</th>
        <th>Share of All Hands</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Total Pairs</strong></td>
        <td>13 ranks &times; 6 combos</td>
        <td><strong>78 combos</strong></td>
        <td>5.88% of all hands</td>
      </tr>
      <tr>
        <td><strong>Total Suited Hands</strong></td>
        <td>78 types &times; 4 combos</td>
        <td><strong>312 combos</strong></td>
        <td>23.53% of all hands</td>
      </tr>
      <tr>
        <td><strong>Total Offsuit Hands</strong></td>
        <td>78 types &times; 12 combos</td>
        <td><strong>936 combos</strong></td>
        <td>70.59% of all hands</td>
      </tr>
      <tr style="background: var(--emerald-50); font-weight: 700;">
        <td><strong>Total Combinations</strong></td>
        <td>\(\binom{52}{2}\)</td>
        <td><strong>1,326 combos</strong></td>
        <td><strong>100.0%</strong></td>
      </tr>
    </tbody>
  </table>

  <h3>6.2 Pot Odds (Lesson 05 from Study Companion)</h3>
  <p>Pot odds represent the ratio between the size of the pot and the cost of the call. It defines the <strong>exact win percentage (equity)</strong> your hand needs to break even.</p>

  <div class="math-panel">
    $$\text{Pot Odds \%} = \frac{\text{Amount to Call}}{\text{Current Pot Size} + \text{Opponent Bet} + \text{Amount to Call}}$$
  </div>

  <div class="info-card-gold">
    <div style="font-weight: 700; color: var(--slate-950); margin-bottom: 3pt;">Step-by-Step Example (from Companion Lesson 05):</div>
    <div class="grid-2col" style="align-items: center; margin: 0;">
      <ul style="margin-bottom: 0; font-size: 8pt;">
        <li>There is $12 in the pot.</li>
        <li>Your opponent bets $6.</li>
        <li>Current total pot before your call = \(\$12 + \$6 = \$18\).</li>
        <li>Cost for you to call = $6.</li>
      </ul>
      <div style="text-align: center; background: #ffffff; border: 1px solid #e5c158; border-radius: 5px; padding: 3pt 6pt;">
        $$\text{Pot Odds} = \frac{6}{18 + 6} = \frac{6}{24} = 25\%$$
      </div>
    </div>
    <p style="margin: 4pt 0 0 0; font-size: 8.1pt; color: var(--slate-950);"><strong>Conclusion:</strong> To justify calling, your hand must have at least <strong>25% equity</strong> against the opponent's range.</p>
  </div>

  <h3>6.3 Expected Value / EV (Lesson 06 from Study Companion)</h3>
  <p>Expected Value (\(\text{EV}\)) is the average amount won or lost per decision if that exact scenario were repeated thousands of times:</p>

  <div class="math-panel">
    $$\text{EV} = (P(\text{Win}) \times \text{Net Profit}) - (P(\text{Loss}) \times \text{Cost of Bet})$$
  </div>

  <ul>
    <li>A decision is <strong>\(+EV\)</strong> if its average outcome yields positive profit.</li>
    <li>A decision is <strong>\(-EV\)</strong> if its average outcome loses chips.</li>
    <li><strong>Core Rule of Decision Quality:</strong> Even if you make a \(+EV\) play and lose a specific hand due to a bad river card (variance), <strong>the decision was correct</strong>. Never judge a play by its one-off result.</li>
  </ul>

  <h3>6.4 Calculating Outs and Equity (The Rule of 2 and 4)</h3>
  <p>An <strong>out</strong> is any unseen card remaining in the deck that, if dealt, will improve your hand to a likely winner.</p>

  <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6pt; margin: 4pt 0 6pt 0;">
    <div class="info-card" style="padding: 5pt 7pt;">
      <div style="font-weight: 700; color: var(--emerald-950); font-size: 8.1pt;">Flush Draw</div>
      <p style="font-size: 7.5pt; margin-bottom: 2pt;">You hold 2 suited cards, the board has 2 of your suit.</p>
      <div style="font-size: 8pt; font-weight: 700; color: var(--emerald-800);">\(\text{Outs} = 13 - 4 = 9 \text{ cards}\)</div>
    </div>
    <div class="info-card" style="padding: 5pt 7pt;">
      <div style="font-weight: 700; color: var(--emerald-950); font-size: 8.1pt;">Open-Ended Straight Draw (OESD)</div>
      <p style="font-size: 7.5pt; margin-bottom: 2pt;">Holding \(8\text{-}7\) on a \(9\text{-}6\text{-}2\) board. Any 5 or Ten makes a straight.</p>
      <div style="font-size: 8pt; font-weight: 700; color: var(--emerald-800);">\(\text{Outs} = 4 + 4 = 8 \text{ cards}\)</div>
    </div>
    <div class="info-card" style="padding: 5pt 7pt;">
      <div style="font-weight: 700; color: var(--emerald-950); font-size: 8.1pt;">Inside Straight Draw (Gutshot)</div>
      <p style="font-size: 7.5pt; margin-bottom: 2pt;">Holding \(8\text{-}7\) on a \(J\text{-}9\text{-}2\) board. Only a Ten makes a straight.</p>
      <div style="font-size: 8pt; font-weight: 700; color: var(--emerald-800);">\(\text{Outs} = 4 \text{ cards}\)</div>
    </div>
  </div>

  <div class="grid-2col">
    <div class="info-card-emerald" style="margin: 0;">
      <div style="font-weight: 700; color: var(--emerald-950); font-size: 8.2pt;">On the Flop (with 2 cards to come):</div>
      <div style="margin: 2pt 0;">$$\text{Approximate Equity \%} \approx \text{Outs} \times 4$$</div>
      <div style="font-size: 7.6pt; font-style: italic; text-align: center;">(Example: 9 flush outs \(\times 4 \approx 36\%\) equity)</div>
    </div>
    <div class="info-card-emerald" style="margin: 0;">
      <div style="font-weight: 700; color: var(--emerald-950); font-size: 8.2pt;">On the Turn (with 1 card to come):</div>
      <div style="margin: 2pt 0;">$$\text{Approximate Equity \%} \approx \text{Outs} \times 2$$</div>
      <div style="font-size: 7.6pt; font-style: italic; text-align: center;">(Example: 9 flush outs \(\times 2 \approx 18\%\) equity)</div>
    </div>
  </div>
</div>

<!-- =====================================================================
     PAGE 6: SECTION 7 (STRATEGIC PRINCIPLES) & SECTION 8 (GLOSSARY)
     ===================================================================== -->
<div class="page">
  <div class="section-banner" style="margin-top: 0;">
    <span class="section-badge">07</span>
    <span class="section-title">Core Strategic Principles (The Hold'em Bridge)</span>
  </div>

  <p>These strategic principles directly mirror the training syllabus presented in Lessons 01–10 of your study companion:</p>

  <h3>7.1 The Power of Position (In Position vs. Out of Position)</h3>
  <p>Acting last (In Position — IP) is the single greatest competitive edge in poker:</p>

  <div class="grid-2col" style="margin-bottom: 6pt;">
    <div class="info-card">
      <div style="font-weight: 700; color: var(--emerald-950); margin-bottom: 1.5pt;">1. Information Asymmetry</div>
      <p style="margin-bottom: 0; font-size: 7.9pt;">You see whether your opponent checks or bets before you must make any commitment.</p>
    </div>
    <div class="info-card">
      <div style="font-weight: 700; color: var(--emerald-950); margin-bottom: 1.5pt;">2. Pot Control</div>
      <p style="margin-bottom: 0; font-size: 7.9pt;">You can check back to keep pots small when holding medium-strength showdown value.</p>
    </div>
    <div class="info-card">
      <div style="font-weight: 700; color: var(--emerald-950); margin-bottom: 1.5pt;">3. Bluff Realization</div>
      <p style="margin-bottom: 0; font-size: 7.9pt;">Opponent checks show weakness, giving you high-equity bluffing opportunities.</p>
    </div>
    <div class="info-card">
      <div style="font-weight: 700; color: var(--emerald-950); margin-bottom: 1.5pt;">4. Value Maximization</div>
      <p style="margin-bottom: 0; font-size: 7.9pt;">When holding strong hands, you can extract an extra street of value on the river.</p>
    </div>
  </div>

  <h3>7.2 Giving Every Bet a Clear Reason (Lesson 04 &amp; 08)</h3>
  <p>Never bet "just to see where you are." Every aggressive action must fall into one of two categories:</p>
  <div class="grid-2col" style="margin-bottom: 5pt;">
    <div class="info-card" style="border-top-color: var(--emerald-700);">
      <div style="font-weight: 700; color: var(--emerald-950); margin-bottom: 1.5pt;">1. Value Bet</div>
      <p style="margin-bottom: 0; font-size: 7.9pt;">You wager chips expecting to be called by hands that are worse than yours.</p>
    </div>
    <div class="info-card" style="border-top-color: var(--gold-500);">
      <div style="font-weight: 700; color: var(--emerald-950); margin-bottom: 1.5pt;">2. Bluff</div>
      <p style="margin-bottom: 0; font-size: 7.9pt;">You wager chips expecting to cause hands that are better than yours to fold.</p>
    </div>
  </div>
  <div class="info-card-gold" style="margin-bottom: 7pt;">
    If a bet will only be called by better hands and will only fold out worse hands, <strong>betting is a mistake—you should check</strong>.
  </div>

  <h3>7.3 Stack-to-Pot Ratio / SPR (Lesson 20)</h3>
  <div class="math-panel">
    $$\text{SPR} = \frac{\text{Effective Stack Size}}{\text{Size of Pot on the Flop}}$$
  </div>

  <table class="pro-table" style="margin-bottom: 9pt;">
    <thead>
      <tr>
        <th style="width: 24%;">SPR Zone</th>
        <th style="width: 76%;">Strategic Implication</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Low SPR (\(< 3\))</strong></td>
        <td>You are committed. Hands like top pair / top kicker or overpairs become easy stack-off hands.</td>
      </tr>
      <tr>
        <td><strong>Medium SPR (\(4 - 10\))</strong></td>
        <td>High danger zone. One pair hands can lose massive pots; requires pot control.</td>
      </tr>
      <tr>
        <td><strong>High SPR (\(> 10\))</strong></td>
        <td>Implied odds dominate. Speculative hands (pocket pairs looking for sets, suited connectors looking for flushes and straights) gain tremendous value.</td>
      </tr>
    </tbody>
  </table>

  <div class="section-banner" style="margin-top: 6pt;">
    <span class="section-badge">08</span>
    <span class="section-title">Glossary of Essential Terminology</span>
  </div>

  <div class="glossary-grid">
    <div class="glossary-card">
      <div class="glossary-term">3-Bet</div>
      <div class="glossary-desc">The second raise preflop (The BB is the 1st bet, the open-raise is the 2nd bet, the re-raise is the 3-bet).</div>
    </div>
    <div class="glossary-card">
      <div class="glossary-term">C-Bet (Continuation Bet)</div>
      <div class="glossary-desc">A bet made on the flop by the player who initiated the aggression preflop.</div>
    </div>
    <div class="glossary-card">
      <div class="glossary-term">Effective Stack</div>
      <div class="glossary-desc">The smallest stack among active players in a hand; represents the maximum number of chips that can be contested.</div>
    </div>
    <div class="glossary-card">
      <div class="glossary-term">Kicker</div>
      <div class="glossary-desc">An unpaired side card used to break ties between identical pairs or three-of-a-kinds.</div>
    </div>
    <div class="glossary-card">
      <div class="glossary-term">Muck</div>
      <div class="glossary-desc">The discard pile, or the action of surrendering your cards face down without showing them.</div>
    </div>
    <div class="glossary-card">
      <div class="glossary-term">Nuts</div>
      <div class="glossary-desc">The absolute best possible 5-card hand given the specific community board cards.</div>
    </div>
    <div class="glossary-card">
      <div class="glossary-term">Pot-Committed</div>
      <div class="glossary-desc">A situation where the pot is so large relative to your remaining chips that folding has worse mathematical EV than calling, even with modest equity.</div>
    </div>
    <div class="glossary-card">
      <div class="glossary-term">Tilt</div>
      <div class="glossary-desc">An emotional state of frustration or anger leading to irrational, \(-EV\) decision-making.</div>
    </div>
  </div>
</div>

<script>
  document.addEventListener("DOMContentLoaded", function() {
    renderMathInElement(document.body, {
      delimiters: [
        {left: "$$", right: "$$", display: true},
        {left: "\\(", right: "\\)", display: false}
      ],
      throwOnError: false
    });
  });
</script>
</body>
</html>
"""

def build_pdf():
    workspace = r"c:\Users\berna\Downloads\poker_01-teste"
    docs_dir = os.path.join(workspace, "docs", "architecture")
    pdf_path = os.path.join(docs_dir, "01_Texas_Holdem_Complete_Guide.pdf")
    html_temp_path = os.path.join(docs_dir, "_temp_01_guide.html")

    with open(html_temp_path, "w", encoding="utf-8") as f:
        f.write(HTML_DOCUMENT)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page()
        url = "file:///" + os.path.abspath(html_temp_path).replace("\\", "/")
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1500)

        header_html = """
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 7.2pt; width: 100%; display: flex; justify-content: space-between; padding: 0 13mm 3px 13mm; color: #64748b; border-bottom: 1px solid #e2e8f0;">
            <span style="font-weight: 700; color: #064e3b; letter-spacing: 0.5px;">TEXAS HOLD'EM: COMPLETE REFERENCE GUIDE &amp; FUNDAMENTAL THEORY</span>
            <span style="font-weight: 500;">RULES &bull; TABLE DYNAMICS &bull; MATHEMATICS &bull; STRATEGY</span>
        </div>
        """

        footer_html = """
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 7.2pt; width: 100%; display: flex; justify-content: space-between; padding: 3px 13mm 0 13mm; color: #64748b; border-top: 1px solid #e2e8f0;">
            <span>01_Texas_Holdem_Complete_Guide</span>
            <span style="font-weight: 600; color: #0f172a;">Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
        </div>
        """

        page.pdf(
            path=pdf_path,
            format="A4",
            display_header_footer=True,
            header_template=header_html,
            footer_template=footer_html,
            margin={
                "top": "14mm",
                "bottom": "14mm",
                "left": "13mm",
                "right": "13mm"
            },
            print_background=True
        )
        browser.close()

    if os.path.exists(html_temp_path):
        os.remove(html_temp_path)

    doc = pymupdf.open(pdf_path)
    print(f"Generated {pdf_path} ({len(doc)} pages)")
    for i, p in enumerate(doc):
        print(f"  Page {i+1}: {len(p.get_text())} chars")
    doc.close()

if __name__ == "__main__":
    build_pdf()
