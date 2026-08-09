import React from 'react';

// Self-contained visual flowchart of a Fusion search, shown in the Help page's
// "How Fusion Search Works" section. Static SVG/HTML; all CSS is scoped under
// .ffc so it can't affect the rest of the page. Rendered via innerHTML because
// it's non-interactive markup (no React state).
const HTML = `<style>.ffc{
    --ground:#f7f5f3; --card:#fff; --ink:#1c1917; --body:#44403c; --muted:#79716b;
    --line:#e6e1dc; --spine:#d9d2cb;
    --accent:#b91c1c; --accent-deep:#991b1b; --accent-tint:#fdf3f2; --accent-bd:#f3d6d3;
    --src:#1d4ed8; --src-bg:#eef3fd; --src-bd:#cfddf8;
    --tgt:#b45309; --tgt-bg:#fbf1e3; --tgt-bd:#f0dcbf;
    --good:#15803d; --grey:#cbc7c2;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  }.ffc *{box-sizing:border-box;}.ffc .fx{font-family:var(--sans);color:var(--body);background:var(--ground);
      padding:38px 18px 46px;display:flex;flex-direction:column;align-items:center;
      min-height:100%;-webkit-font-smoothing:antialiased;}.ffc .fx-in{width:100%;max-width:600px;}.ffc .fx-eyebrow{font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;font-weight:600;color:var(--accent);margin:0 0 9px;}.ffc .fx-title{font-family:var(--serif);font-size:clamp(1.5rem,4.5vw,1.95rem);line-height:1.14;color:var(--ink);margin:0 0 9px;font-weight:600;text-wrap:balance;}.ffc .fx-lede{font-size:1rem;line-height:1.55;color:var(--muted);margin:0 0 8px;max-width:52ch;}.ffc .stage{position:relative;padding:22px 0 8px;}.ffc .stage-hd{display:flex;align-items:center;gap:10px;margin:0 0 14px;}.ffc .stage-no{flex:none;width:26px;height:26px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;font-size:.82rem;font-variant-numeric:tabular-nums;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 2px rgba(120,20,15,.28);}.ffc .stage-hd h2{font-size:1.06rem;color:var(--ink);margin:0;font-weight:650;letter-spacing:-.01em;}.ffc .stage-cap{font-size:.9rem;line-height:1.5;color:var(--body);margin:12px 2px 0;}.ffc .stage-cap b{color:var(--ink);font-weight:640;}.ffc .arrow{display:flex;justify-content:center;padding:4px 0;}.ffc .arrow svg{display:block;}.ffc .viz{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 16px;box-shadow:0 1px 2px rgba(28,25,23,.04);}.ffc .viz.tint{background:var(--accent-tint);border-color:var(--accent-bd);}.ffc /* stage 1: two documents */
  .docs{display:flex;align-items:stretch;gap:14px;justify-content:center;}.ffc .doc{flex:1;max-width:210px;background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px;box-shadow:0 1px 1px rgba(0,0,0,.03);}.ffc .doc-tag{font-size:.62rem;text-transform:uppercase;letter-spacing:.08em;font-weight:700;margin:0 0 8px;}.ffc .doc.src .doc-tag{color:var(--src);}.ffc .doc.tgt .doc-tag{color:var(--tgt);}.ffc .doc-ttl{font-size:.8rem;font-weight:600;color:var(--ink);margin:0 0 9px;}.ffc .tl{height:5px;border-radius:3px;background:#e8e4df;margin:5px 0;}.ffc .doc.src .tl{background:#dbe4f7;}.ffc .doc.tgt .tl{background:#f4e6cf;}.ffc .docs-vs{align-self:center;font-family:var(--serif);font-size:.9rem;color:var(--muted);font-style:italic;}.ffc /* stage 2: split */
  .split{display:flex;align-items:center;gap:12px;justify-content:center;}.ffc .split .doc{max-width:104px;flex:none;}.ffc .split-lines{display:flex;flex-direction:column;gap:6px;flex:none;width:200px;}.ffc .lrow{background:#fff;border:1px solid var(--line);border-radius:6px;padding:6px 8px;display:flex;align-items:center;gap:6px;box-shadow:0 1px 1px rgba(0,0,0,.03);}.ffc .lrow .tl{flex:1;margin:0;background:#e8e4df;}.ffc .lrow .lemma{font-size:.6rem;font-weight:700;color:var(--accent-deep);background:#fbe9e7;border-radius:3px;padding:1px 5px;white-space:nowrap;}.ffc .split-arrow{color:var(--accent);font-size:1.3rem;line-height:1;}.ffc /* stage 3: fan out */
  .fan{width:100%;height:auto;display:block;}.ffc .fan .lead{fill:none;stroke:var(--accent);stroke-width:1.1;opacity:.26;}.ffc .fan .hub{fill:var(--accent);}.ffc .fan .hub-t{fill:var(--muted);font-size:8.5px;font-family:var(--sans);font-weight:600;letter-spacing:.03em;text-transform:uppercase;}.ffc .fan .chip-on{fill:#fff;stroke:var(--accent);stroke-width:1.4;}.ffc .fan .chip-off{fill:#f4f1ee;stroke:#ddd7d1;stroke-width:1;}.ffc .fan .dot-on{fill:var(--accent);}.ffc .fan .dot-off{fill:none;stroke:#c3bdb6;stroke-width:1.2;}.ffc .fan .t-on{fill:var(--ink);font-size:8px;font-family:var(--sans);font-weight:600;}.ffc .fan .t-off{fill:#a49e97;font-size:8px;font-family:var(--sans);font-weight:500;}.ffc .fx-note{font-size:.76rem;color:var(--accent-deep);margin:12px 2px 0;font-weight:500;}.ffc /* stage 4: weight & combine */
  .weigh{display:flex;flex-direction:column;gap:9px;}.ffc .wrow{display:grid;grid-template-columns:98px 30px 1fr;align-items:center;gap:10px;}.ffc .wch{font-size:.82rem;font-weight:600;color:var(--ink);}.ffc .wx{font-size:.74rem;font-weight:700;color:var(--accent-deep);background:#fbe9e7;border:1px solid var(--accent-bd);border-radius:4px;padding:2px 0;text-align:center;font-variant-numeric:tabular-nums;}.ffc .wbar{height:16px;display:flex;align-items:center;}.ffc .wbar i{display:block;height:16px;border-radius:4px;min-width:4px;}.ffc .wsum{display:grid;grid-template-columns:98px 30px 1fr;align-items:center;gap:10px;margin-top:6px;padding-top:11px;border-top:1px solid var(--accent-bd);}.ffc .wsum .wch{font-weight:700;color:var(--accent-deep);}.ffc .wsum .wsigma{font-family:var(--serif);font-size:1.05rem;color:var(--accent-deep);text-align:center;}.ffc .wstack{height:22px;display:flex;border-radius:5px;overflow:hidden;box-shadow:inset 0 0 0 1px rgba(0,0,0,.05);}.ffc .wstack span{display:block;height:22px;}.ffc /* stage 5: funnel */
  .funnel{width:100%;height:auto;display:block;}.ffc .funnel .fbody{fill:#faf8f6;stroke:var(--line);stroke-width:1;}.ffc .funnel .common{fill:var(--grey);}.ffc .funnel .rare{fill:var(--accent);}.ffc .funnel .flab{fill:var(--muted);font-size:8.5px;font-family:var(--sans);font-weight:600;text-transform:uppercase;letter-spacing:.04em;}.ffc /* stage 6: rank + pair */
  .rank{display:flex;flex-direction:column;gap:7px;}.ffc .rrow{display:grid;grid-template-columns:16px 118px 1fr 34px;align-items:center;gap:9px;}.ffc .rn{font-size:.72rem;font-weight:700;color:var(--muted);text-align:right;font-variant-numeric:tabular-nums;}.ffc .rpair{font-size:.74rem;color:var(--ink);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}.ffc .rmeter{height:14px;display:flex;align-items:center;}.ffc .rmeter i{display:block;height:14px;border-radius:4px;background:linear-gradient(90deg,var(--accent),var(--accent-deep));}.ffc .rrow.dim .rmeter i{background:#d9c9c6;}.ffc .rrow.dim .rpair{color:var(--muted);font-weight:500;}.ffc .rpct{font-size:.72rem;font-weight:700;color:var(--good);text-align:right;font-variant-numeric:tabular-nums;}.ffc .rrow.dim .rpct{color:var(--muted);}.ffc .pair{margin-top:14px;border:1px solid var(--line);border-radius:9px;overflow:hidden;}.ffc .pair-hd{background:#faf8f6;border-bottom:1px solid var(--line);padding:7px 12px;font-size:.72rem;font-weight:700;color:var(--ink);display:flex;justify-content:space-between;}.ffc .pair-hd .pconf{color:var(--good);}.ffc .pline{padding:10px 12px;font-size:.86rem;line-height:1.5;}.ffc .pline.src{background:var(--src-bg);border-bottom:1px dashed var(--tgt-bd);}.ffc .pline.tgt{background:var(--tgt-bg);}.ffc .plab{display:block;font-size:.6rem;text-transform:uppercase;letter-spacing:.07em;font-weight:700;margin-bottom:3px;}.ffc .pline.src .plab{color:var(--src);}.ffc .pline.tgt .plab{color:var(--tgt);}.ffc .mk{background:#fde68a;border-radius:3px;padding:0 3px;color:#1c1917;font-weight:600;}.ffc .rbadges{display:flex;gap:5px;flex-wrap:wrap;padding:9px 12px;background:#fff;border-top:1px solid var(--line);}.ffc .rbadge{font-size:.63rem;text-transform:uppercase;letter-spacing:.05em;font-weight:600;color:var(--accent-deep);background:#fbe9e7;border:1px solid var(--accent-bd);border-radius:4px;padding:2px 6px;}.ffc .fx-foot{font-size:.83rem;color:var(--muted);line-height:1.5;margin:24px 2px 0;border-top:1px dashed var(--line);padding-top:14px;}

  @media (prefers-reduced-motion: no-preference){.ffc .stage{animation:ffcrise .5s cubic-bezier(.22,1,.36,1) both;}.ffc .stage:nth-of-type(1){animation-delay:.02s;}.ffc .stage:nth-of-type(2){animation-delay:.09s;}.ffc .stage:nth-of-type(3){animation-delay:.16s;}.ffc .stage:nth-of-type(4){animation-delay:.23s;}.ffc .stage:nth-of-type(5){animation-delay:.30s;}.ffc .stage:nth-of-type(6){animation-delay:.37s;}
    @keyframes ffcrise{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
  }</style>
<div class="ffc"><div class="fx">
  <div class="fx-in">
    <p class="fx-eyebrow">Tesserae · Intertext Search</p>
    <h1 class="fx-title">How a Fusion search works</h1>
    <p class="fx-lede">The default “Phrases” search compares two texts and combines many kinds of similarity into one ranked list of parallels.</p>

    <!-- 1 -->
    <div class="stage">
      <div class="stage-hd"><span class="stage-no">1</span><h2>Choose two texts</h2></div>
      <div class="viz"><div class="docs">
        <div class="doc src"><p class="doc-tag">Source</p><p class="doc-ttl">Vergil, Aeneid 1</p>
          <div class="tl" style="width:92%"></div><div class="tl" style="width:78%"></div><div class="tl" style="width:85%"></div><div class="tl" style="width:60%"></div></div>
        <div class="docs-vs">compared with</div>
        <div class="doc tgt"><p class="doc-tag">Target</p><p class="doc-ttl">Lucan, Civil War 1</p>
          <div class="tl" style="width:80%"></div><div class="tl" style="width:90%"></div><div class="tl" style="width:66%"></div><div class="tl" style="width:84%"></div></div>
      </div></div>
      <p class="stage-cap">Pick a <b>source</b> (usually the earlier text) and a <b>target</b> that may echo it.</p>
    </div>
    <div class="arrow"><svg width="20" height="26" viewBox="0 0 20 26"><path d="M10 0 v18 M4 13 l6 7 6-7" fill="none" stroke="#c9c2bb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>

    <!-- 2 -->
    <div class="stage">
      <div class="stage-hd"><span class="stage-no">2</span><h2>Split into lines &amp; simplify words</h2></div>
      <div class="viz"><div class="split">
        <div class="doc tgt" style="max-width:104px"><div class="tl" style="width:88%"></div><div class="tl" style="width:70%"></div><div class="tl" style="width:82%"></div><div class="tl" style="width:64%"></div></div>
        <span class="split-arrow">→</span>
        <div class="split-lines">
          <div class="lrow"><span class="tl"></span><span class="lemma">arma → arma</span></div>
          <div class="lrow"><span class="tl"></span><span class="lemma">cano → cano</span></div>
          <div class="lrow"><span class="tl"></span><span class="lemma">iactatus → iacto</span></div>
          <div class="lrow"><span class="tl"></span><span class="lemma">alto → altus</span></div>
        </div>
      </div></div>
      <p class="stage-cap">Each text is broken into lines, and every word is reduced to its dictionary form (its <b>lemma</b>) so related forms match.</p>
    </div>
    <div class="arrow"><svg width="20" height="26" viewBox="0 0 20 26"><path d="M10 0 v18 M4 13 l6 7 6-7" fill="none" stroke="#c9c2bb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>

    <!-- 3 -->
    <div class="stage">
      <div class="stage-hd"><span class="stage-no">3</span><h2>Ten channels search in parallel</h2></div>
      <div class="viz tint">
        <svg class="fan" viewBox="0 0 600 150" role="img" aria-label="One line pair fans out to ten detection channels; some find a signal, some do not">
          <g class="lead">
            <line x1="300" y1="34" x2="39"  y2="100"/><line x1="300" y1="34" x2="97"  y2="100"/><line x1="300" y1="34" x2="155" y2="100"/><line x1="300" y1="34" x2="213" y2="100"/><line x1="300" y1="34" x2="271" y2="100"/><line x1="300" y1="34" x2="329" y2="100"/><line x1="300" y1="34" x2="387" y2="100"/><line x1="300" y1="34" x2="445" y2="100"/><line x1="300" y1="34" x2="503" y2="100"/><line x1="300" y1="34" x2="561" y2="100"/>
          </g>
          <circle class="hub" cx="300" cy="22" r="12"/><text class="hub-t" x="300" y="9" text-anchor="middle">one line pair</text>
          <!-- on = found a signal -->
          <g><rect class="chip-on"  x="12"  y="100" width="54" height="34" rx="6"/><circle class="dot-on"  cx="22" cy="112" r="3"/><text class="t-on"  x="18" y="128">Shared</text></g>
          <g><rect class="chip-off" x="70"  y="100" width="54" height="34" rx="6"/><circle class="dot-off" cx="80" cy="112" r="3"/><text class="t-off" x="76" y="128">Single</text></g>
          <g><rect class="chip-off" x="128" y="100" width="54" height="34" rx="6"/><circle class="dot-off" cx="138" cy="112" r="3"/><text class="t-off" x="134" y="128">Exact</text></g>
          <g><rect class="chip-on"  x="186" y="100" width="54" height="34" rx="6"/><circle class="dot-on"  cx="196" cy="112" r="3"/><text class="t-on"  x="192" y="128">Sound</text></g>
          <g><rect class="chip-off" x="244" y="100" width="54" height="34" rx="6"/><circle class="dot-off" cx="254" cy="112" r="3"/><text class="t-off" x="250" y="128">Spelling</text></g>
          <g><rect class="chip-on"  x="302" y="100" width="54" height="34" rx="6"/><circle class="dot-on"  cx="312" cy="112" r="3"/><text class="t-on"  x="308" y="128">Meaning</text></g>
          <g><rect class="chip-off" x="360" y="100" width="54" height="34" rx="6"/><circle class="dot-off" cx="370" cy="112" r="3"/><text class="t-off" x="366" y="128">Synonym</text></g>
          <g><rect class="chip-off" x="418" y="100" width="54" height="34" rx="6"/><circle class="dot-off" cx="428" cy="112" r="3"/><text class="t-off" x="424" y="128">Syntax</text></g>
          <g><rect class="chip-off" x="476" y="100" width="54" height="34" rx="6"/><circle class="dot-off" cx="486" cy="112" r="3"/><text class="t-off" x="482" y="128">Structure</text></g>
          <g><rect class="chip-on"  x="534" y="100" width="54" height="34" rx="6"/><circle class="dot-on"  cx="544" cy="112" r="3"/><text class="t-on"  x="540" y="128">Rare</text></g>
        </svg>
        <p class="fx-note">Each channel searches independently for a different kind of similarity. For any given pair, only some channels find a signal (outlined in red).</p>
      </div>
      <p class="stage-cap">The channels look for shared words, sound, meaning, syntax, rare vocabulary, and more — all at the same time.</p>
    </div>
    <div class="arrow"><svg width="20" height="26" viewBox="0 0 20 26"><path d="M10 0 v18 M4 13 l6 7 6-7" fill="none" stroke="#c9c2bb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>

    <!-- 4 -->
    <div class="stage">
      <div class="stage-hd"><span class="stage-no">4</span><h2>Weight &amp; combine into one score</h2></div>
      <div class="viz">
        <div class="weigh">
          <div class="wrow"><span class="wch">Rare words</span><span class="wx">×7</span><span class="wbar"><i style="width:52%;background:#8f1717"></i></span></div>
          <div class="wrow"><span class="wch">Sound</span><span class="wx">×5</span><span class="wbar"><i style="width:29%;background:#b91c1c"></i></span></div>
          <div class="wrow"><span class="wch">Shared words</span><span class="wx">×2</span><span class="wbar"><i style="width:13%;background:#d64c42"></i></span></div>
          <div class="wrow"><span class="wch">Meaning</span><span class="wx">×1</span><span class="wbar"><i style="width:6%;background:#ea9089"></i></span></div>
          <div class="wsum"><span class="wch">Fused score</span><span class="wsigma">Σ</span>
            <span class="wstack"><span style="width:52%;background:#8f1717"></span><span style="width:29%;background:#b91c1c"></span><span style="width:13%;background:#d64c42"></span><span style="width:6%;background:#ea9089"></span></span>
          </div>
        </div>
      </div>
      <p class="stage-cap">Channels don’t count equally. Each has a <b>weight</b> — rare vocabulary and sound weigh heavily, common signals lightly. Each channel’s weighted contribution (the colored bars) <b>stacks into the pair’s single fused score</b>. These weights are tuned for each language.</p>
    </div>
    <div class="arrow"><svg width="20" height="26" viewBox="0 0 20 26"><path d="M10 0 v18 M4 13 l6 7 6-7" fill="none" stroke="#c9c2bb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>

    <!-- 5 -->
    <div class="stage">
      <div class="stage-hd"><span class="stage-no">5</span><h2>Tune for rarity &amp; filter noise</h2></div>
      <div class="viz">
        <svg class="funnel" viewBox="0 0 600 214" role="img" aria-label="Many candidate pairs enter a funnel; matches built on common words are removed while rare wording passes through and is boosted">
          <text class="flab" x="300" y="13" text-anchor="middle">many candidate pairs — mostly common words</text>
          <g>
            <rect class="common" x="70"  y="24" width="30" height="8" rx="4"/>
            <rect class="common" x="112" y="24" width="36" height="8" rx="4"/>
            <rect class="rare"   x="160" y="23" width="22" height="10" rx="5"/>
            <rect class="common" x="196" y="24" width="34" height="8" rx="4"/>
            <rect class="common" x="242" y="24" width="28" height="8" rx="4"/>
            <rect class="common" x="284" y="24" width="40" height="8" rx="4"/>
            <rect class="rare"   x="338" y="23" width="22" height="10" rx="5"/>
            <rect class="common" x="374" y="24" width="30" height="8" rx="4"/>
            <rect class="common" x="418" y="24" width="36" height="8" rx="4"/>
            <rect class="rare"   x="468" y="23" width="22" height="10" rx="5"/>
            <rect class="common" x="504" y="24" width="30" height="8" rx="4"/>
          </g>
          <path class="fbody" d="M74 44 L526 44 L340 132 L340 158 L260 158 L260 132 Z"/>
          <text class="flab" x="300" y="74"  text-anchor="middle" style="fill:#78716c">common-word matches removed</text>
          <text class="flab" x="300" y="120" text-anchor="middle" style="fill:#991b1b">rare wording kept</text>
          <text class="flab" x="300" y="182" text-anchor="middle">kept &amp; boosted</text>
          <g>
            <rect class="rare" x="250" y="192" width="30" height="13" rx="6"/>
            <rect class="rare" x="288" y="193" width="26" height="12" rx="6"/>
            <rect class="rare" x="322" y="192" width="28" height="13" rx="6"/>
          </g>
        </svg>
      </div>
      <p class="stage-cap">Matches built only from <b>common words</b> are down-weighted or dropped; <b>rare wording</b> caught by several channels at once is boosted — so the strongest parallels rise and noise falls away.</p>
    </div>
    <div class="arrow"><svg width="20" height="26" viewBox="0 0 20 26"><path d="M10 0 v18 M4 13 l6 7 6-7" fill="none" stroke="#c9c2bb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>

    <!-- 6 -->
    <div class="stage">
      <div class="stage-hd"><span class="stage-no">6</span><h2>Rank the paired passages</h2></div>
      <div class="viz">
        <div class="rank">
          <div class="rrow"><span class="rn">1</span><span class="rpair">Aen 1.1 ↔ BC 1.2</span><span class="rmeter"><i style="width:100%"></i></span><span class="rpct">94%</span></div>
          <div class="rrow"><span class="rn">2</span><span class="rpair">Aen 1.34 ↔ BC 2.7</span><span class="rmeter"><i style="width:82%"></i></span><span class="rpct">88%</span></div>
          <div class="rrow"><span class="rn">3</span><span class="rpair">Aen 1.94 ↔ BC 1.8</span><span class="rmeter"><i style="width:66%"></i></span><span class="rpct">79%</span></div>
          <div class="rrow dim"><span class="rn">4</span><span class="rpair">Aen 1.50 ↔ BC 3.1</span><span class="rmeter"><i style="width:40%"></i></span><span class="rpct">61%</span></div>
          <div class="rrow dim"><span class="rn">5</span><span class="rpair">Aen 1.12 ↔ BC 2.4</span><span class="rmeter"><i style="width:24%"></i></span><span class="rpct">47%</span></div>
        </div>
        <div class="pair">
          <div class="pair-hd"><span>Top match · 94% confidence</span><span class="pconf">Shared &amp; rare wording</span></div>
          <div class="pline src"><span class="plab">Source · Vergil, Aeneid 1.1</span>Arma virumque <span class="mk">cano</span>, Troiae qui primus ab oris</div>
          <div class="pline tgt"><span class="plab">Target · Lucan, Civil War 1.2</span>iusque datum sceleri <span class="mk">canimus</span>, populumque potentem</div>
          <div class="rbadges"><span class="rbadge">Shared words</span><span class="rbadge">Sound</span><span class="rbadge">Rare words</span></div>
        </div>
      </div>
      <p class="stage-cap">Each result is a <b>pair of passages</b> — source and target — ranked by confidence, with the shared words highlighted in both and badges showing which channels detected them.</p>
    </div>

    <p class="fx-foot">The other search types — Lines, String Search, Rare Pairs, Rare Words — follow simpler versions of this flow, described in their own sections.</p>
  </div>
</div></div>`;

export default function FusionFlowchart() {
  return <div className="my-4" dangerouslySetInnerHTML={{ __html: HTML }} />;
}
