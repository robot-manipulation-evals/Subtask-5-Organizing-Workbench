// Renders GHS bottle labels and storage-zone signs to PNG textures.
// Usage:  node make_labels.js            (reads ../chemicals.json, writes ../labels and ../zone_signs)
// Add a chemical to chemicals.json and re-run to get its label.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const data = JSON.parse(fs.readFileSync(path.join(ROOT, 'chemicals.json'), 'utf8'));
const picto = (code) => 'data:image/svg+xml;base64,' +
  fs.readFileSync(path.join(ROOT, 'pictograms', code + '.svg')).toString('base64');
const jsbarcode = fs.readFileSync(require.resolve('jsbarcode/dist/JsBarcode.all.min.js'), 'utf8');
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

const LABEL_W = 1600, LABEL_H = 800; // 2:1, maps to the front ~half of a 500 mL bottle

function labelHtml(c, idx) {
  const cat = 'BR-' + String(1001 + idx);
  const hs = c.hazard_statements.map(h =>
    `<li><b>${h}</b> ${esc(data.hazard_statement_text[h] || '')}</li>`).join('');
  const pics = c.pictograms.map(p => `<img class="pic" src="${picto(p)}">`).join('');
  const hazardBlock = c.pictograms.length
    ? `<div class="pics">${pics}</div>
       <div class="sig">${esc(c.signal_word)}</div>`
    : `<div class="nohaz">Not a hazardous substance or mixture according to GHS.</div>`;
  return `<!doctype html><html><head><meta charset="utf-8"><style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{width:${LABEL_W}px;height:${LABEL_H}px;background:#fbfaf6;font-family:"DejaVu Sans","Liberation Sans",Arial,sans-serif;color:#111;overflow:hidden}
  .wrap{position:absolute;inset:14px;border:4px solid #1d2a44;display:flex;flex-direction:column}
  .top{background:#1d2a44;color:#fff;display:flex;justify-content:space-between;align-items:center;padding:10px 26px;font-size:28px;letter-spacing:2px}
  .top b{font-size:32px;letter-spacing:4px}
  .id{padding:16px 26px 8px}
  .name{font-size:84px;font-weight:700;line-height:1.02}
  .sub{font-size:36px;margin-top:8px}
  .sub span{color:#555}
  .main{flex:1;display:flex;gap:22px;padding:6px 26px 0;align-items:flex-start}
  .haz{display:flex;flex-direction:column;align-items:flex-start;min-width:${'${MINW}'}px}
  .pics{display:flex;gap:4px}
  .pic{width:236px;height:236px}
  .sig{font-size:76px;font-weight:800;margin-top:4px;text-transform:uppercase;letter-spacing:2px}
  .nohaz{font-size:34px;max-width:470px;border:3px dashed #888;padding:18px;color:#333}
  ul{list-style:none;font-size:30px;line-height:1.25;padding-top:8px;display:grid;grid-template-columns:auto 1fr;column-gap:16px;row-gap:8px}
  ul li{display:contents}
  .p{font-size:24px;color:#333;margin-top:10px}
  .foot{display:flex;justify-content:space-between;align-items:flex-end;padding:0 26px 10px}
  .lot{font-size:24px;line-height:1.5}
  .rcv{display:inline-block;border:2px solid #888;width:300px;height:44px;vertical-align:middle;margin-left:8px}
  svg#bc{height:110px}
  </style></head><body><div class="wrap">
    <div class="top"><b>BENCHMARK REAGENTS</b><span>Cat. No. ${cat} &nbsp;·&nbsp; ${esc(c.size)}</span></div>
    <div class="id">
      <div class="name">${esc(c.name)}</div>
      <div class="sub">${esc(c.formula)} &nbsp;·&nbsp; ${esc(c.grade)} &nbsp;·&nbsp; <span>CAS ${esc(c.cas)}</span></div>
    </div>
    <div class="main">
      <div class="haz">${hazardBlock}</div>
      <div><ul>${hs}</ul>
        <div class="p">${c.pictograms.length ? 'Wear protective gloves / eye protection. Read SDS before use.' : 'Read SDS before use.'} For laboratory use only.</div></div>
    </div>
    <div class="foot">
      <div class="lot">Lot ${(0x5A3F00 + idx * 7919).toString(16).toUpperCase()} &nbsp;·&nbsp; Exp. 2028-06<br>Received:<span class="rcv"></span></div>
      <svg id="bc"></svg>
    </div>
  </div>
  <script>${jsbarcode}</script>
  <script>JsBarcode('#bc', ${JSON.stringify(cat)}, {format:'CODE128', width:3, height:80, fontSize:22, margin:0, background:'transparent'});</script>
  </body></html>`.replace('${MINW}', String(Math.max(c.pictograms.length, 2) * 240));
}

const ZONES = [
  { id: 'flammables_cabinet', title: 'FLAMMABLE', sub: 'KEEP FIRE AWAY', bg: '#f6c400', fg: '#c00000', pics: ['GHS02'] },
  { id: 'corrosives_acids', title: 'CORROSIVE — ACIDS', sub: 'Inorganic acids only', bg: '#1f5fa8', fg: '#fff', pics: ['GHS05'] },
  { id: 'corrosives_acids_oxidizing_tray', title: 'OXIDIZING ACIDS', sub: 'Nitric acid — separate tray', bg: '#1f5fa8', fg: '#fff', pics: ['GHS03', 'GHS05'] },
  { id: 'corrosives_bases', title: 'CORROSIVE — BASES', sub: 'Keep away from acids', bg: '#1f5fa8', fg: '#fff', pics: ['GHS05'] },
  { id: 'oxidizers', title: 'OXIDIZERS', sub: 'Keep away from flammables', bg: '#fff', fg: '#111', pics: ['GHS03'] },
  { id: 'toxics', title: 'TOXIC', sub: 'Acute toxics', bg: '#fff', fg: '#111', pics: ['GHS06'] },
  { id: 'general_shelf', title: 'GENERAL STORAGE', sub: 'Non-hazardous chemicals', bg: '#8a9099', fg: '#fff', pics: [] },
];
const ZW = 1200, ZH = 400;
function zoneHtml(z) {
  const pics = z.pics.map(p => `<img src="${picto(p)}">`).join('');
  return `<!doctype html><html><head><meta charset="utf-8"><style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{width:${ZW}px;height:${ZH}px;background:${z.bg};color:${z.fg};font-family:"DejaVu Sans",Arial,sans-serif;display:flex;align-items:center;gap:30px;padding:0 40px;overflow:hidden}
  body{border:12px solid ${z.fg}}
  img{width:220px;height:220px;background:#fff;border-radius:6px}
  h1{font-size:${z.title.length > 14 ? 78 : 104}px;font-weight:800;line-height:1}
  p{font-size:42px;margin-top:16px}
  </style></head><body>${pics}<div><h1>${esc(z.title)}</h1><p>${esc(z.sub)}</p></div></body></html>`;
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: LABEL_W, height: LABEL_H } });
  fs.mkdirSync(path.join(ROOT, 'labels'), { recursive: true });
  fs.mkdirSync(path.join(ROOT, 'zone_signs'), { recursive: true });
  for (const [i, c] of data.chemicals.entries()) {
    await page.setContent(labelHtml(c, i), { waitUntil: 'load' });
    await page.screenshot({ path: path.join(ROOT, 'labels', c.id + '.png') });
    c.catalog_no = 'BR-' + (1001 + i);
  }
  await page.setViewportSize({ width: ZW, height: ZH });
  for (const z of ZONES) {
    await page.setContent(zoneHtml(z), { waitUntil: 'load' });
    await page.screenshot({ path: path.join(ROOT, 'zone_signs', z.id + '.png') });
  }
  await browser.close();
  // write barcode numbers back into the manifest so scanning tasks can look them up
  fs.writeFileSync(path.join(ROOT, 'chemicals.json'), JSON.stringify(data, null, 2) + '\n');
  console.log(`wrote ${data.chemicals.length} labels, ${ZONES.length} zone signs`);
})();
