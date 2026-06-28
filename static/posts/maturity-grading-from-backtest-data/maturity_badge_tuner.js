(function(){if(window.__tunerInit)return;window.__tunerInit=1;

  const gcls = {A:'ga',B:'gb',C:'gc',D:'gd',E:'ge'};

  // ── OLD MODEL (geometric) - maturity classification + cycleScore. No backtest input: the badge
  //    lights up wherever the (D,W,M) grade curve LOOKS ripe (fast hot, slow cold). Kept LIVE so the
  //    OLD intensity stays derived (not hand-typed); each COMBO_DATA row's `old`/`sym` reproduce
  //    these functions exactly (cross-check against the recorded snapshot). ──
  const LEVELS = {A:4,B:3,C:2,D:1,E:0};
  const SHAPE_SYM = {descending:'↗',premature:'⤳',tent:'⋀',flatHigh:'→',flatLow:'↔',valley:'⋁',ascending:'↘'};
  function classify(d,w,m){
    if(w>d && w>m) return 'tent';
    if(w<d && w<m) return 'valley';
    const range = Math.max(d,w,m)-Math.min(d,w,m);
    if(range<=1) return ((d+w+m)/3)>=2.5 ? 'flatHigh' : 'flatLow';
    if(d>m) return w>=3 ? 'descending' : 'premature';
    return 'ascending';
  }
  function cycleScore(d,w,m){
    const fast=(d+2*w)/3, front=fast-m, level=(d+w+m)/3, raw=2*front+level;
    return Math.max(0,Math.min(100,Math.round(((raw+8)/20)*100)));
  }

  // ── NEW MODEL - operator-blessed (2026-06-24). Brightness = OUR EXISTING RANKING, shown as light.
  //    Each combo's badge brightness = its POSITION in our 2pc (fixed) TSLC-A/B confidence-weighted
  //    ranking (`_shrink_sorted` - the SAME ranking behind the re-rank ★): #1 = brightest (100), last
  //    = dimmest (0), everything in between by its weighted rank. NOTHING about the ranking changes -
  //    same equal weighting across stop% / R:R / expectancy, same n/(n+100) shrinkage. The badge does
  //    not re-score anything; it just visualises the ranking. Generated from the ranking, not hand-typed.
  const COMBO_DATA = [
    {D:'B',W:'B',M:'E',sym:'↗',old:80,nw:100,rank:1,n:509,mr:3.44,sl:11.2,rr:4.09,win:86.2},
    {D:'C',W:'B',M:'E',sym:'⋀',old:75,nw:99,rank:2,n:76,mr:8.76,sl:5.3,rr:7.62,win:94.7},
    {D:'A',W:'B',M:'E',sym:'↗',old:85,nw:97,rank:3,n:209,mr:2.66,sl:11.0,rr:2.96,win:87.6},
    {D:'C',W:'C',M:'E',sym:'⤳',old:67,nw:96,rank:4,n:937,mr:2.18,sl:13.4,rr:2.49,win:84.6},
    {D:'B',W:'C',M:'E',sym:'⤳',old:72,nw:95,rank:5,n:400,mr:2.27,sl:15.2,rr:2.73,win:83.0},
    {D:'A',W:'A',M:'E',sym:'↗',old:93,nw:94,rank:6,n:305,mr:3.41,sl:18.7,rr:4.21,win:80.0},
    {D:'C',W:'B',M:'C',sym:'⋀',old:58,nw:92,rank:7,n:299,mr:2.19,sl:17.1,rr:2.66,win:80.6},
    {D:'A',W:'A',M:'C',sym:'↗',old:77,nw:91,rank:8,n:444,mr:2.01,sl:19.8,rr:2.53,win:78.8},
    {D:'B',W:'B',M:'D',sym:'↗',old:72,nw:90,rank:9,n:553,mr:1.61,sl:18.3,rr:2.16,win:79.2},
    {D:'B',W:'C',M:'D',sym:'⤳',old:63,nw:88,rank:10,n:317,mr:1.73,sl:17.7,rr:2.16,win:81.1},
    {D:'B',W:'A',M:'E',sym:'⋀',old:88,nw:87,rank:11,n:19,mr:9.07,sl:0.0,rr:2.05,win:100.0},
    {D:'A',W:'A',M:'D',sym:'↗',old:85,nw:86,rank:12,n:205,mr:1.87,sl:24.9,rr:2.47,win:74.6},
    {D:'A',W:'C',M:'E',sym:'⤳',old:77,nw:85,rank:13,n:22,mr:3.16,sl:4.5,rr:2.43,win:95.5},
    {D:'B',W:'A',M:'C',sym:'⋀',old:72,nw:83,rank:14,n:86,mr:1.98,sl:15.1,rr:2.06,win:84.9},
    {D:'A',W:'C',M:'C',sym:'⤳',old:60,nw:82,rank:15,n:14,mr:4.28,sl:0.0,rr:2.05,win:100.0},
    {D:'D',W:'D',M:'E',sym:'↔',old:53,nw:81,rank:16,n:1011,mr:1.65,sl:17.9,rr:2.01,win:81.0},
    {D:'C',W:'C',M:'A',sym:'↘',old:33,nw:79,rank:17,n:92,mr:2.31,sl:30.4,rr:3.57,win:67.4},
    {D:'A',W:'C',M:'A',sym:'⋁',old:43,nw:78,rank:18,n:63,mr:1.22,sl:14.3,rr:2.25,win:76.2},
    {D:'A',W:'C',M:'B',sym:'⋁',old:52,nw:77,rank:19,n:12,mr:3.26,sl:25.0,rr:3.82,win:75.0},
    {D:'A',W:'A',M:'B',sym:'→',old:68,nw:76,rank:20,n:1298,mr:1.38,sl:25.0,rr:2.08,win:73.2},
    {D:'D',W:'C',M:'E',sym:'⋀',old:62,nw:74,rank:21,n:126,mr:1.71,sl:12.7,rr:1.85,win:86.5},
    {D:'D',W:'E',M:'E',sym:'↔',old:45,nw:73,rank:22,n:156,mr:1.42,sl:14.1,rr:1.91,win:82.1},
    {D:'B',W:'A',M:'D',sym:'⋀',old:80,nw:72,rank:23,n:52,mr:1.83,sl:15.4,rr:1.95,win:84.6},
    {D:'D',W:'B',M:'B',sym:'↘',old:45,nw:71,rank:24,n:7,mr:3.45,sl:0.0,rr:2.05,win:100.0},
    {D:'A',W:'B',M:'D',sym:'↗',old:77,nw:69,rank:25,n:181,mr:1.19,sl:22.1,rr:2.17,win:70.7},
    {D:'B',W:'D',M:'A',sym:'⋁',old:30,nw:68,rank:26,n:11,mr:1.27,sl:0.0,rr:2.05,win:100.0},
    {D:'E',W:'C',M:'C',sym:'↘',old:40,nw:67,rank:27,n:6,mr:2.99,sl:0.0,rr:2.05,win:100.0},
    {D:'A',W:'B',M:'C',sym:'↗',old:68,nw:65,rank:28,n:315,mr:1.34,sl:27.9,rr:2.17,win:70.2},
    {D:'C',W:'B',M:'D',sym:'⋀',old:67,nw:64,rank:29,n:218,mr:1.75,sl:34.9,rr:2.71,win:64.7},
    {D:'E',W:'C',M:'D',sym:'⋀',old:48,nw:63,rank:30,n:6,mr:2.12,sl:0.0,rr:2.05,win:100.0},
    {D:'D',W:'E',M:'B',sym:'⋁',old:20,nw:62,rank:31,n:32,mr:1.15,sl:12.5,rr:2.04,win:81.2},
    {D:'D',W:'E',M:'A',sym:'⋁',old:12,nw:60,rank:32,n:8,mr:0.82,sl:0.0,rr:2.05,win:100.0},
    {D:'C',W:'E',M:'B',sym:'⋁',old:25,nw:59,rank:33,n:5,mr:1.73,sl:0.0,rr:2.05,win:100.0},
    {D:'D',W:'C',M:'A',sym:'↘',old:28,nw:58,rank:34,n:11,mr:1.08,sl:36.4,rr:2.91,win:54.5},
    {D:'E',W:'D',M:'E',sym:'⋀',old:48,nw:56,rank:35,n:135,mr:1.34,sl:24.4,rr:2.04,win:71.1},
    {D:'E',W:'E',M:'E',sym:'↔',old:40,nw:55,rank:36,n:740,mr:1.38,sl:19.6,rr:1.79,win:79.2},
    {D:'D',W:'C',M:'B',sym:'↘',old:37,nw:54,rank:37,n:119,mr:1.34,sl:29.4,rr:2.17,win:68.9},
    {D:'C',W:'D',M:'E',sym:'⤳',old:58,nw:53,rank:38,n:339,mr:1.37,sl:20.6,rr:1.81,win:77.9},
    {D:'A',W:'B',M:'B',sym:'→',old:60,nw:51,rank:39,n:513,mr:1.14,sl:27.1,rr:2.12,win:67.6},
    {D:'B',W:'D',M:'D',sym:'⤳',old:55,nw:50,rank:40,n:1,mr:-1.33,sl:100.0,rr:2.05,win:0.0},
    {D:'E',W:'E',M:'B',sym:'↘',old:15,nw:49,rank:41,n:2,mr:-0.45,sl:50.0,rr:0.22,win:50.0},
    {D:'A',W:'A',M:'A',sym:'→',old:60,nw:47,rank:42,n:3257,mr:1.16,sl:32.8,rr:2.15,win:65.3},
    {D:'D',W:'D',M:'A',sym:'↘',old:20,nw:46,rank:43,n:4,mr:0.11,sl:50.0,rr:1.21,win:50.0},
    {D:'B',W:'D',M:'E',sym:'⤳',old:63,nw:45,rank:44,n:13,mr:0.54,sl:38.5,rr:1.85,win:53.8},
    {D:'B',W:'B',M:'C',sym:'→',old:63,nw:44,rank:45,n:1271,mr:1.19,sl:27.9,rr:1.90,win:70.9},
    {D:'B',W:'C',M:'C',sym:'↔',old:55,nw:42,rank:46,n:476,mr:1.03,sl:25.0,rr:1.88,win:69.7},
    {D:'C',W:'C',M:'D',sym:'↔',old:58,nw:41,rank:47,n:1253,mr:1.11,sl:25.4,rr:1.75,win:72.5},
    {D:'C',W:'A',M:'B',sym:'⋀',old:58,nw:40,rank:48,n:8,mr:-1.18,sl:100.0,rr:2.05,win:0.0},
    {D:'D',W:'B',M:'A',sym:'↘',old:37,nw:38,rank:49,n:7,mr:-0.58,sl:57.1,rr:0.38,win:28.6},
    {D:'E',W:'D',M:'C',sym:'↘',old:32,nw:37,rank:50,n:95,mr:0.92,sl:27.4,rr:1.72,win:66.3},
    {D:'D',W:'D',M:'D',sym:'↔',old:45,nw:36,rank:51,n:1396,mr:1.07,sl:24.4,rr:1.71,win:72.8},
    {D:'B',W:'C',M:'A',sym:'⋁',old:38,nw:35,rank:52,n:250,mr:1.03,sl:31.6,rr:1.98,win:64.4},
    {D:'C',W:'D',M:'D',sym:'↔',old:50,nw:33,rank:53,n:370,mr:1.02,sl:23.0,rr:1.52,win:75.7},
    {D:'E',W:'D',M:'B',sym:'↘',old:23,nw:32,rank:54,n:14,mr:0.23,sl:42.9,rr:1.07,win:57.1},
    {D:'C',W:'A',M:'A',sym:'↘',old:50,nw:31,rank:55,n:6,mr:-0.90,sl:83.3,rr:0.11,win:16.7},
    {D:'A',W:'B',M:'A',sym:'⋁',old:52,nw:29,rank:56,n:444,mr:1.01,sl:30.2,rr:1.94,win:66.4},
    {D:'C',W:'D',M:'B',sym:'⋁',old:33,nw:28,rank:57,n:134,mr:0.64,sl:47.8,rr:2.41,win:47.0},
    {D:'B',W:'D',M:'B',sym:'⋁',old:38,nw:27,rank:58,n:13,mr:-0.23,sl:38.5,rr:0.52,win:53.8},
    {D:'B',W:'D',M:'C',sym:'⋁',old:47,nw:26,rank:59,n:9,mr:-0.68,sl:66.7,rr:0.16,win:33.3},
    {D:'C',W:'B',M:'A',sym:'↘',old:42,nw:24,rank:60,n:148,mr:0.77,sl:24.3,rr:1.50,win:70.3},
    {D:'B',W:'A',M:'B',sym:'⋀',old:63,nw:23,rank:61,n:211,mr:0.92,sl:25.1,rr:1.44,win:73.0},
    {D:'D',W:'C',M:'C',sym:'↔',old:45,nw:22,rank:62,n:280,mr:0.97,sl:32.9,rr:1.89,win:64.6},
    {D:'C',W:'B',M:'B',sym:'→',old:50,nw:21,rank:63,n:373,mr:0.81,sl:36.5,rr:1.95,win:59.2},
    {D:'C',W:'C',M:'C',sym:'↔',old:50,nw:19,rank:64,n:1342,mr:1.00,sl:33.2,rr:1.85,win:65.6},
    {D:'E',W:'D',M:'D',sym:'↔',old:40,nw:18,rank:65,n:125,mr:0.76,sl:32.0,rr:1.52,win:66.4},
    {D:'E',W:'E',M:'C',sym:'↘',old:23,nw:17,rank:66,n:92,mr:0.59,sl:33.7,rr:1.53,win:59.8},
    {D:'D',W:'C',M:'D',sym:'⋀',old:53,nw:15,rank:67,n:260,mr:0.90,sl:32.7,rr:1.73,win:65.4},
    {D:'C',W:'D',M:'A',sym:'⋁',old:25,nw:14,rank:68,n:59,mr:0.21,sl:30.5,rr:1.19,win:55.9},
    {D:'B',W:'B',M:'B',sym:'→',old:55,nw:13,rank:69,n:1673,mr:0.90,sl:33.4,rr:1.90,win:62.8},
    {D:'C',W:'C',M:'B',sym:'↔',old:42,nw:12,rank:70,n:694,mr:0.80,sl:38.8,rr:1.93,win:58.6},
    {D:'B',W:'A',M:'A',sym:'→',old:55,nw:10,rank:71,n:454,mr:0.86,sl:34.8,rr:1.80,win:63.2},
    {D:'D',W:'D',M:'B',sym:'↘',old:28,nw:9,rank:72,n:185,mr:0.48,sl:48.6,rr:1.90,win:49.2},
    {D:'E',W:'E',M:'D',sym:'↔',old:32,nw:8,rank:73,n:445,mr:0.85,sl:36.2,rr:1.79,win:62.2},
    {D:'D',W:'E',M:'D',sym:'⋁',old:37,nw:6,rank:74,n:135,mr:0.61,sl:33.3,rr:1.33,win:65.9},
    {D:'D',W:'E',M:'C',sym:'⋁',old:28,nw:5,rank:75,n:74,mr:0.03,sl:54.1,rr:1.44,win:41.9},
    {D:'D',W:'D',M:'C',sym:'↔',old:37,nw:4,rank:76,n:829,mr:0.60,sl:36.3,rr:1.59,win:59.6},
    {D:'B',W:'B',M:'A',sym:'→',old:47,nw:3,rank:77,n:650,mr:0.58,sl:39.1,rr:1.69,win:57.2},
    {D:'B',W:'C',M:'B',sym:'⋁',old:47,nw:1,rank:78,n:359,mr:0.43,sl:39.8,rr:1.48,win:56.5},
    {D:'C',W:'D',M:'C',sym:'⋁',old:42,nw:0,rank:79,n:353,mr:0.35,sl:38.5,rr:1.26,win:57.8},
  ];

  const ids = ['k','lmin','lrange','fbase','frange','bbase','brange','gth'];
  const def = {k:3.4,lmin:17,lrange:83,fbase:0.02,frange:0.56,bbase:0.07,brange:0.56,gth:66};
  function P(){ const o={}; ids.forEach(id=>o[id]=parseFloat(document.getElementById(id).value)); return o; }

  // Shared brightness curve - maps a 0-100 intensity (OLD cycleScore OR NEW perf score) to the badge
  // fill/border/glyph/glow. BOTH badges use the SAME curve so you compare the SOURCES, not the curve.
  function badgeStyle(cs, p){
    if(cs===null) return {color:'var(--tx-muted)',bg:'rgba(255,255,255,0.03)',bd:'1px solid var(--bd-default)',glow:''};
    const t = Math.max(0,Math.min(1,cs/100));
    const f = (Math.exp(p.k*t)-1)/(Math.exp(p.k)-1);
    const L = (p.lmin + p.lrange*f).toFixed(1);
    const fa = (p.fbase + p.frange*f).toFixed(3);
    const ba = (p.bbase + p.brange*f).toFixed(3);
    let glow='';
    if(cs>=p.gth){ const g=Math.min(0.6, 0.32 + (t-p.gth/100)*1.8).toFixed(2); glow=`box-shadow:0 0 8px rgba(255,255,255,${g});`; }
    return {color:`hsl(0,0%,${L}%)`, bg:`rgba(255,255,255,${fa})`, bd:`1px solid rgba(255,255,255,${ba})`, glow};
  }

  function badge(intensity, sym, p){
    const s = badgeStyle(intensity, p);
    return `<span class="badge" style="background:${s.bg};border:${s.bd};${s.glow}">`+
      `<span class="sym" style="color:${s.color}">${sym}</span></span>`+
      `<span class="scoreval">${intensity===null?'-':intensity}</span>`;
  }

  function comboCell(D,W,M){
    return `<span class="combo"><span class="${gcls[D]||''}">${D}</span>·`+
      `<span class="${gcls[W]||''}">${W}</span>·<span class="${gcls[M]||''}">${M}</span></span>`;
  }

  function deltaCell(oldv, nw){
    if(nw===null) return `<span class="delta delta-flat">-</span>`;
    const d = nw - oldv;
    if(d===0) return `<span class="delta delta-flat">·</span>`;
    const up = d>0;
    return `<span class="delta ${up?'delta-up':'delta-down'}">${up?'▲':'▼'} ${Math.abs(d)}</span>`;
  }

  function render(){
    const p = P();
    ids.forEach(id=>{ document.getElementById('v'+id).textContent = document.getElementById(id).value; });

    document.getElementById('cmphead').innerHTML =
      `<tr>`+
      `<th class="l" title="The Daily·Weekly·Monthly maturity-grade triple (A = fully expanded / hot, E = dormant / flat).">Combo</th>`+
      `<th class="c" title="The maturity 'ripple' shape this combo classifies to (↗ peak · ⤳ premature · ⋀ weekly-led · → late · ↔ dormant · ⋁ divergent · ↘ backside). Shape-based - unchanged by the new model.">Shape</th>`+
      `<th class="c" title="Badge brightness = this combo's POSITION in our 2pc (fixed) confidence-weighted ranking (#1 brightest, last dimmest). Same ranking behind the re-rank ★; nothing re-scored.">Badge</th>`+
      `<th title="This combo's place in our 2pc (fixed) TSLC-A/B confidence-weighted ranking (1 = best).">Rank</th>`+
      `<th title="Number of tradeable (A/B) backtest trades for this combo - the sample size behind its stats (small samples are shrunk toward the pool average).">n</th>`+
      `<th title="Average R-multiple (reward ÷ initial risk) across this combo's trades - its expectancy. Green = positive, red = negative.">Mean R</th>`+
      `<th title="Share of this combo's trades that hit the initial stop (r ≤ −0.9). Lower is better.">Stop%</th>`+
      `<th title="Reward:risk - mean winner ÷ |mean loser|. Higher is better.">R:R</th>`+
      `<th title="Share of this combo's trades that closed positive (r > 0).">Win%</th>`+
      `</tr>`;

    // OLD sym + score derived LIVE from classify()/cycleScore(); NEW intensity + trade stats from COMBO_DATA.
    document.getElementById('rows').innerHTML = COMBO_DATA.map(r=>{
      const d=LEVELS[r.D], w=LEVELS[r.W], m=LEVELS[r.M];
      const sym = SHAPE_SYM[classify(d,w,m)];
      const rr = (r.rr===null) ? '-' : r.rr.toFixed(2);
      const neutral = r.nw===null;
      return `<tr class="${neutral?'row-neutral':''}"><td class="l">${comboCell(r.D,r.W,r.M)}</td>`+
        `<td class="c" style="font-size:1.3em;color:#fff">${sym}</td>`+
        `<td class="c badgecell cell-new">${badge(r.nw,sym,p)}</td>`+
        `<td>${neutral?'-':'#'+r.rank}</td><td>${r.n.toLocaleString()}</td>`+
        `<td class="${r.mr>=0?'pos':'neg'}">${r.mr>=0?'+':''}${r.mr.toFixed(2)}R</td>`+
        `<td>${r.sl.toFixed(1)}%</td><td>${rr}</td><td>${r.win.toFixed(1)}%</td></tr>`;
    }).join('');

    document.getElementById('colkey').textContent =
      'Badge = our existing 2pc (fixed) confidence-weighted ranking shown as brightness - #1 brightest, '+
      'last dimmest, everyone in between by their weighted rank. Same ranking that drives the re-rank ★; '+
      'the badge re-scores nothing, it just visualises the ranking (equal weighting + n/(n+100) shrinkage, '+
      'all unchanged). Mean R / Stop% / R:R / Win% are the combo\'s underlying trade stats.';

    document.getElementById('params').textContent =
      `f = (e^(${p.k}·t) − 1)/(e^${p.k} − 1),  t = intensity/100\n`+
      `glyph L  = ${p.lmin}% + ${p.lrange}%·f\n`+
      `fill α   = ${p.fbase} + ${p.frange}·f\n`+
      `border α = ${p.bbase} + ${p.brange}·f\n`+
      `glow     = intensity ≥ ${p.gth}`;
  }

  ids.forEach(id=>document.getElementById(id).addEventListener('input',render));
  document.getElementById('reset').addEventListener('click',()=>{ ids.forEach(id=>document.getElementById(id).value=def[id]); render(); });
  render();

})();
