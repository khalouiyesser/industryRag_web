/* ═══════════════════════════════════════════════════════════
   Industrial RAG — Ahmed · DSL Agent
   app.js — JavaScript séparé de index.html
   ═══════════════════════════════════════════════════════════ */

'use strict';

// ════════════════════════════════════════════
// ÉTAT GLOBAL
// ════════════════════════════════════════════
const SESSION_ID = 'sess_' + Math.random().toString(36).slice(2);
let isLoading = false;

// DSL Agent state
let dslDomain = null;
let dslFormData = {};
let dslA3 = '';
let dslPanelHistory = [];
let dslPanelLoading = false;
let dslResult   = null;   // kept for compat
let dslRawText  = '';
let dslAllResults = {};   // { output_type_id: {result, raw} } — tous les types générés
let dslActiveTab  = null; // onglet actif dans la vue résultat

// ════════════════════════════════════════════
// OUTPUT TYPES — Tables 49-54 du rapport PFE
// Logique de sélection : urgence × audience × situation (Table 55)
// ════════════════════════════════════════════
const OUTPUT_TYPES = [
  { id:'digital_a3',   label:'📋 Digital A3 Report',     shortLabel:'A3',
    desc:'Analyse DMAIC complète — 8 sections, root cause, plan d\'action, contrôle',
    audience:'Ingénieur Qualité / Maintenance / Process',
    trigger:'Déviation significative (> 2× cible), problème récurrent ou audit',
    time:'< 45s', color:'#4a9eff' },
  { id:'kpi_alert',    label:'⚠️ Real-Time KPI Alert',   shortLabel:'Alerte',
    desc:'Alerte compacte 5 champs — seuil dépassé, cause probable, action immédiate',
    audience:'Opérateur sur le poste',
    trigger:'KPI dépasse un seuil en temps réel (< 30 min)',
    time:'< 5s',  color:'#e05050' },
  { id:'quick_fix',    label:'🔧 Quick-Fix Action Card',  shortLabel:'Quick-Fix',
    desc:'Carte 4 champs — cause évidente, actions exécutables ce shift',
    audience:'Technicien / Opérateur (sans escalade superviseur)',
    trigger:'Problème mineur connu, cause unique, premier shift',
    time:'< 15s', color:'#d4a017' },
  { id:'exec_summary', label:'📊 Executive Summary',      shortLabel:'Exec',
    desc:'Vue synthèse 5 sections — traffic-light par domaine, COPQ, actions semaine',
    audience:'Superviseur / Chef de production / Directeur',
    trigger:'Revue hebdo/mensuelle de performance multi-domaines',
    time:'< 30s', color:'#3fb950' },
  { id:'cbam_report',  label:'🌍 CBAM Compliance Report', shortLabel:'CBAM',
    desc:'Rapport CO₂ 7 sections — intensité/unité, conformité EU 2023/956, exposition financière',
    audience:'Responsable énergie / Compliance officer',
    trigger:'Reporting mensuel EU Reg. 2023/956 (export EU)',
    time:'< 60s', color:'#8b5cf6' },
  { id:'cross_domain', label:'🔗 Cross-Domain Report',    shortLabel:'Cross',
    desc:'Analyse inter-domaines — chaîne causale, facteur amplification, plan intégré',
    audience:'Ingénieur process / Green Belt',
    trigger:'Symptômes détectés simultanément sur 2+ domaines',
    time:'< 60s', color:'#f59e0b' },
];

// ── Trigger keywords par domaine (Table 48) ───────────────────────────────
const DOMAIN_TRIGGERS = {
  A: ['defect_rate','batch_rejected','cpk_value','rework_hours','scrap_weight',
    'defective_units','total_units','usl','lsl','defect_type'],
  B: ['oee_value','downtime_hours','downtime','mtbf','failure_mode',
    'vibration_alert','mttr','planned_time','actual_output','theoretical_output'],
  C: ['lead_time','wip','takt_time','cycle_time','otd','bottleneck',
    'customer_demand','available_time','current_lead_time'],
  D: ['energy_kwh','energy_consumed','co2_equivalent','co2_factor',
    'compressed_air_m3','idle_time','idle_time_pct','power_factor',
    'energy_source','target_intensity','production_volume'],
};

// ── Auto-sélection output type (Table 55) ─────────────────────────────────
function autoSelectOutputType(formData, domain) {
  const keys = Object.keys(formData).filter(k => formData[k] && String(formData[k]).trim() !== '');
  // Cross-domain : champs de 2+ domaines détectés
  const domainsDetected = Object.entries(DOMAIN_TRIGGERS)
      .filter(([, trigs]) => trigs.some(t => keys.includes(t)))
      .map(([d]) => d);
  if (domainsDetected.length >= 2) return 'cross_domain';
  // Domaine D avec données CO₂ → CBAM
  if (domain === 'D' && keys.some(k => ['energy_consumed','co2_factor','target_intensity'].includes(k)))
    return 'cbam_report';
  // Déviation KPI critique → alerte (Table 50)
  const dr = parseFloat(formData.defective_units) / parseFloat(formData.total_units);
  if (!isNaN(dr) && dr > 0.05) return 'kpi_alert';
  const avail = (parseFloat(formData.planned_time) - parseFloat(formData.downtime)) / parseFloat(formData.planned_time);
  const perf  = parseFloat(formData.actual_output) / parseFloat(formData.theoretical_output);
  const oee   = avail * perf;
  if (!isNaN(oee) && oee < 0.70) return 'kpi_alert';
  // Peu de champs → Quick-Fix
  if (keys.length <= 3) return 'quick_fix';
  return 'digital_a3';
}

// ── Cross-domain patterns (Table 56) ─────────────────────────────────────
const CROSS_PATTERNS = [
  { combo:['A','B'], label:'Qualité ↔ Maintenance',
    desc:'Dégradation équipement (B) → variabilité process → taux défauts (A)',
    action:'TPM corrective + Poka-Yoke' },
  { combo:['B','D'], label:'Maintenance ↔ Énergie',
    desc:'Machine dégradée (B) consomme 30-40% énergie excédentaire (D)',
    action:'TPM + installation VFD' },
  { combo:['C','D'], label:'Flux ↔ Énergie',
    desc:'WIP accumulé (C) → machines idle consomment de l\'énergie (D)',
    action:'Kanban pull + auto-standby CNC' },
  { combo:['A','G'], label:'Qualité ↔ Formation',
    desc:'Lacunes compétences opérateurs (G) → variabilité process (A)',
    action:'Standard Work OJT/TWI + Poka-Yoke' },
  { combo:['D','H'], label:'Énergie ↔ Coûts',
    desc:'Surconsommation (D) → coût/unité ↑ + exposition CBAM (H)',
    action:'DMAIC énergie + modèle coût PAF' },
];

// ════════════════════════════════════════════
// DOMAINES DSL — Table 48 (trigger keywords + tools enrichis)
// ════════════════════════════════════════════
const DOMAINS = {
  A:{id:"A",label:"Quality & Defects",icon:"🔴",
    metric:"Defect rate · DPMO · Cp/Cpk",
    tools:"FMEA · Pareto · Fishbone 5M · SPC P-chart · Poka-Yoke · 5 Whys",
    desc:"Taux de défauts, non-conformités, rebuts, retouches",
    fields:[
      {key:"machine",label:"Machine / Line ID",type:"text",ph:"ex. PL-03"},
      {key:"total_units",label:"Total unités produites",type:"number",ph:"ex. 241"},
      {key:"defective_units",label:"Unités défectueuses",type:"number",ph:"ex. 28"},
      {key:"defect_type",label:"Type de défaut",type:"text",ph:"ex. Rayures surface"},
      {key:"batch_rejected",label:"Lots rejetés",type:"number",ph:"ex. 3"},
      {key:"rework_hours",label:"Heures de retouche",type:"number",ph:"ex. 4.5"},
      {key:"scrap_weight",label:"Poids rebuts (kg)",type:"number",ph:"ex. 12.4"},
      {key:"cpk_value",label:"Cpk mesuré",type:"number",ph:"ex. 0.82"},
      {key:"shift",label:"Équipe",type:"select",opts:["Matin","Après-midi","Nuit"]},
      {key:"usl",label:"Limite supérieure USL",type:"number",ph:"ex. 25.5 mm"},
      {key:"lsl",label:"Limite inférieure LSL",type:"number",ph:"ex. 24.5 mm"},
    ]},
  B:{id:"B",label:"Maintenance & OEE",icon:"🟠",
    metric:"OEE · MTBF · MTTR",
    tools:"FMEA RPN · TPM · SMED · OEE A×P×Q · MTBF/MTTR analysis",
    desc:"Pannes, disponibilité, MTTR, TRS",
    fields:[
      {key:"machine",label:"ID Machine",type:"text",ph:"ex. Moteur M-07"},
      {key:"planned_time",label:"Temps planifié (h)",type:"number",ph:"ex. 8"},
      {key:"downtime",label:"Temps d'arrêt total (h)",type:"number",ph:"ex. 2.3"},
      {key:"downtime_reason",label:"Cause principale / failure_mode",type:"text",ph:"ex. Défaillance roulement"},
      {key:"vibration_alert",label:"Alerte vibration (mm/s)",type:"number",ph:"ex. 12.4"},
      {key:"mtbf",label:"MTBF (h)",type:"number",ph:"ex. 145"},
      {key:"mttr",label:"MTTR (h)",type:"number",ph:"ex. 3.2"},
      {key:"actual_output",label:"Production réelle (u)",type:"number",ph:"ex. 180"},
      {key:"theoretical_output",label:"Production théorique (u)",type:"number",ph:"ex. 240"},
      {key:"defective_units",label:"Unités défectueuses",type:"number",ph:"ex. 21"},
    ]},
  C:{id:"C",label:"Flow & Lead Time",icon:"🟡",
    metric:"Lead time · WIP · Takt time",
    tools:"VSM · Kanban sizing · Takt analysis · Heijunka · Line balancing",
    desc:"Délais, WIP, goulots, livraisons tardives",
    fields:[
      {key:"product",label:"Produit / Processus",type:"text",ph:"ex. Ligne assemblage 2"},
      {key:"customer_demand",label:"Demande client (u/jour)",type:"number",ph:"ex. 150"},
      {key:"available_time",label:"Temps dispo (min/jour)",type:"number",ph:"ex. 480"},
      {key:"current_lead_time",label:"Lead time actuel (h)",type:"number",ph:"ex. 18.4"},
      {key:"cycle_time",label:"Cycle time (min/u)",type:"number",ph:"ex. 3.2"},
      {key:"wip",label:"WIP actuel (u en file)",type:"number",ph:"ex. 340"},
      {key:"otd",label:"Taux livraison à temps OTD (%)",type:"number",ph:"ex. 67"},
      {key:"bottleneck",label:"Goulot identifié",type:"text",ph:"ex. Poste peinture"},
    ]},
  D:{id:"D",label:"Energy & Environment",icon:"🟢",
    metric:"kWh/unit · CO₂/shift",
    tools:"Green FMEA · E-VSM · ISO 50001 SPC · Energy Poka-Yoke · CBAM KPI",
    desc:"Surconsommation, CO₂, ISO 14001/50001",
    fields:[
      {key:"site",label:"Site / Département",type:"text",ph:"ex. Atelier usinage"},
      {key:"energy_consumed",label:"Énergie consommée kWh/mois",type:"number",ph:"ex. 12500"},
      {key:"production_volume",label:"Volume production (u/mois)",type:"number",ph:"ex. 4200"},
      {key:"target_intensity",label:"Intensité cible (kWh/u)",type:"number",ph:"ex. 2.0"},
      {key:"idle_time_pct",label:"Temps machine idle (%)",type:"number",ph:"ex. 22"},
      {key:"co2_factor",label:"Facteur CO₂ kg/kWh (STEG : 0.233)",type:"number",ph:"ex. 0.233"},
      {key:"compressed_air_m3",label:"Air comprimé (m³/mois)",type:"number",ph:"ex. 3400"},
      {key:"power_factor",label:"Facteur de puissance (cosφ)",type:"number",ph:"ex. 0.82"},
      {key:"energy_source",label:"Source énergie",type:"select",opts:["Réseau électrique (STEG)","Gaz naturel","Mixte","Renouvelable","Autre"]},
    ]},

  E:{id:"E",label:"Supply Chain",icon:"🔵",desc:"Ruptures stock, délais fournisseurs, bullwhip",isSoon:true,isLocked:true,
    fields:[
      {key:"supplier",label:"Fournisseur / Catégorie",type:"text",ph:"ex. MP — Fournisseur X"},
      {key:"ordered_qty",label:"Quantité commandée (u)",type:"number",ph:"ex. 500"},
      {key:"delivered_qty",label:"Quantité livrée (u)",type:"number",ph:"ex. 420"},
      {key:"promised_lead_time",label:"Lead time promis (j)",type:"number",ph:"ex. 7"},
      {key:"actual_lead_time",label:"Lead time réel (j)",type:"number",ph:"ex. 14"},
      {key:"stockout_events",label:"Ruptures (mois dernier)",type:"number",ph:"ex. 3"},
      {key:"safety_stock_days",label:"Stock sécurité (jours)",type:"number",ph:"ex. 2"},
    ]},
  F:{id:"F",label:"Safety & Ergonomics",icon:"🟣",desc:"Accidents, near-miss, TMS, non-conformités EPI",isSoon:true,isLocked:true,
    fields:[
      {key:"workstation",label:"Poste / Zone",type:"text",ph:"ex. Ligne conditionnement 3"},
      {key:"incident_type",label:"Type d'incident",type:"select",opts:["Accident avec blessure","Presqu'accident","TMS","Exposition chimique","Glissade/chute","Lié équipement"]},
      {key:"incident_count",label:"Incidents (mois)",type:"number",ph:"ex. 4"},
      {key:"near_miss_count",label:"Near-miss (mois)",type:"number",ph:"ex. 12"},
      {key:"days_lost",label:"Jours perdus",type:"number",ph:"ex. 8"},
      {key:"workforce_size",label:"Effectif exposé",type:"number",ph:"ex. 35"},
      {key:"ppe_compliance",label:"Taux conformité EPI (%)",type:"number",ph:"ex. 72"},
    ]},
  G:{id:"G",label:"Human Performance",icon:"🟤",desc:"Erreurs opérateurs, compétences, formation",isSoon:true,isLocked:true,
    fields:[
      {key:"department",label:"Département / Équipe",type:"text",ph:"ex. Équipe assemblage B"},
      {key:"team_size",label:"Taille équipe",type:"number",ph:"ex. 12"},
      {key:"error_rate",label:"Taux d'erreur (%)",type:"number",ph:"ex. 8.5"},
      {key:"training_hours",label:"Heures formation moy. (6 mois)",type:"number",ph:"ex. 6"},
      {key:"competency_coverage",label:"Couverture matrice compétences (%)",type:"number",ph:"ex. 55"},
      {key:"turnover_rate",label:"Turnover annuel (%)",type:"number",ph:"ex. 18"},
      {key:"task_type",label:"Type de tâche",type:"select",opts:["Assemblage / manuel","Conduite machine","Contrôle qualité","Maintenance","Logistique"]},
    ]},
  H:{id:"H",label:"Cost & Finance",icon:"⚫",desc:"COPQ, dépassements coûts, érosion marge",isSoon:true,isLocked:true,
    fields:[
      {key:"product_line",label:"Ligne produit / Centre coût",type:"text",ph:"ex. Ligne A"},
      {key:"production_cost",label:"Coût production réel (TND/u)",type:"number",ph:"ex. 45.2"},
      {key:"target_cost",label:"Coût cible (TND/u)",type:"number",ph:"ex. 38.0"},
      {key:"rework_cost",label:"Coût retouches/mois (TND)",type:"number",ph:"ex. 3200"},
      {key:"scrap_cost",label:"Coût rebuts/mois (TND)",type:"number",ph:"ex. 1800"},
      {key:"inspection_cost",label:"Coût contrôle/mois (TND)",type:"number",ph:"ex. 1100"},
      {key:"revenue_per_unit",label:"Revenu par unité (TND)",type:"number",ph:"ex. 72.0"},
    ]},
};
const DOMAIN_ORDER = ["A","B","C","D","E","F","G","H"];


// ════════════════════════════════════════════
// HEALTH / ENV KEY CHECK
// ════════════════════════════════════════════
async function checkEnvKey() {
  try {
    const r = await fetch('/api/health', {signal: AbortSignal.timeout(4000)});
    const d = await r.json();
    if (d.status === 'ok') {
      document.getElementById('env-dot').className = 'env-dot';
      document.getElementById('env-label').textContent =
          `Clé API : .env ✓ · ${d.documents} doc(s)`;
    }
  } catch {
    document.getElementById('env-dot').className = 'env-dot warn';
    document.getElementById('env-label').textContent = 'Backend hors ligne';
  }
}

// ════════════════════════════════════════════
// HAMBURGER / SIDEBAR MOBILE
// ════════════════════════════════════════════
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const isOpen  = sidebar.classList.contains('open');
  sidebar.classList.toggle('open', !isOpen);
  overlay.classList.toggle('active', !isOpen);
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('active');
}

// ════════════════════════════════════════════
// TAB SWITCH
// ════════════════════════════════════════════
function switchTab(tab) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('visible'));
  document.querySelectorAll('.nav-item[data-tab]').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.bnav-item[data-tab]').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('visible');
  document.querySelectorAll(`[data-tab="${tab}"]`).forEach(el => el.classList.add('active'));
  if (tab === 'docs') loadDocuments();
  if (tab === 'dsl') buildHomeDomainGrid();
  closeSidebar();
}

// ════════════════════════════════════════════
// UTILS
// ════════════════════════════════════════════
function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}
function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
}
function fillQ(el) {
  const q = document.getElementById('question');
  q.value = el.textContent;
  autoResize(q);
  q.focus();
}

// ════════════════════════════════════════════
// CHAT RAG (Ahmed)
// ════════════════════════════════════════════
function appendMsg(role, text) {
  const area = document.getElementById('chat-area');
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = `
    <div class="msg-label">${role === 'user' ? '👤 Vous' : '✦ Ahmed'}</div>
    <div class="msg-bubble">${escapeHtml(text)}</div>`;
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
  return div;
}
function showLoading() {
  const area = document.getElementById('chat-area');
  const div = document.createElement('div');
  div.className = 'msg bot'; div.id = 'loading-msg';
  div.innerHTML = `<div class="msg-label">✦ Ahmed</div>
    <div class="loading-bubble">
      <div class="dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
      Ahmed analyse vos documents…
    </div>`;
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
}
function removeLoading() {
  const el = document.getElementById('loading-msg');
  if (el) el.remove();
}
async function sendChat() {
  if (isLoading) return;
  const qEl = document.getElementById('question');
  const question = qEl.value.trim();
  if (!question) return;
  isLoading = true;
  document.getElementById('btn-send').disabled = true;
  document.getElementById('btn-send').textContent = '⏳';
  appendMsg('user', question);
  qEl.value = ''; qEl.style.height = 'auto';
  showLoading();
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, session_id: SESSION_ID }),
    });
    const data = await res.json();
    removeLoading();
    appendMsg('bot', data.answer || data.error || 'Erreur inconnue.');
  } catch {
    removeLoading();
    appendMsg('bot', '❌ Erreur de connexion. Vérifiez que le backend Flask est démarré (python server.py).');
  } finally {
    isLoading = false;
    document.getElementById('btn-send').disabled = false;
    document.getElementById('btn-send').textContent = '➤ Envoyer';
  }
}
async function clearChat() {
  if (!confirm("Effacer l'historique du chat ?")) return;
  await fetch('/api/chat/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: SESSION_ID }),
  }).catch(() => {});
  const area = document.getElementById('chat-area');
  area.innerHTML = `
    <div class="welcome-card">
      <h2>🏭 Assistant Ahmed</h2>
      <p>Expert en ingénierie industrielle — s'appuie en priorité sur VOS documents.<br>
      Ajoutez vos fichiers via <strong>📂 Documents</strong>, puis posez vos questions.</p>
      <div class="example-qs">
        <span class="example-q" onclick="fillQ(this)">Procédure de maintenance préventive ?</span>
        <span class="example-q" onclick="fillQ(this)">Analyser les causes de rebut sur la ligne X</span>
        <span class="example-q" onclick="fillQ(this)">Quel est l'OEE cible selon les KPI ?</span>
        <span class="example-q" onclick="fillQ(this)">Démarche 5 Why sur arrêt machine</span>
      </div>
    </div>`;
}

// ════════════════════════════════════════════
// DOCUMENTS
// ════════════════════════════════════════════
async function loadDocuments() {
  try {
    const res = await fetch('/api/documents');
    const data = await res.json();
    renderDocs(data.documents || []);
    updateCtxBadge(data.documents || []);
  } catch {
    document.getElementById('docs-tbody').innerHTML =
        '<tr><td colspan="5" class="no-docs">Erreur de chargement</td></tr>';
  }
}
function renderDocs(docs) {
  const tbody = document.getElementById('docs-tbody');
  if (!docs.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="no-docs">Aucun document indexé</td></tr>';
    return;
  }
  tbody.innerHTML = docs.map(d => {
    const ext = d.name.split('.').pop().toUpperCase();
    const sizeK = Math.round(d.chars / 1000);
    const sizeStr = sizeK < 1000 ? sizeK + ' Ko' : (sizeK / 1000).toFixed(1) + ' Mo';
    return `<tr>
      <td class="doc-name">📄 ${escapeHtml(d.name)}</td>
      <td><span class="doc-ext">${ext}</span></td>
      <td>${sizeStr}</td>
      <td><span class="status-ok">✅ Indexé</span></td>
      <td><button class="btn-del-row" onclick="deleteDoc('${escapeHtml(d.name)}')">🗑</button></td>
    </tr>`;
  }).join('');
}
function updateCtxBadge(docs) {
  const badge = document.getElementById('ctx-badge');
  if (!docs.length) {
    badge.className = 'ctx-badge warn';
    badge.innerHTML = '⚠️ Aucun document<br>Ajoutez vos fichiers';
  } else {
    badge.className = 'ctx-badge ok';
    const docList = docs
        .filter(d => d.name && d.name.trim() !== '')
        .map(d => {
          const name = d.name.length > 22 ? d.name.slice(0, 20) + '…' : d.name;
          return `<span style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px;margin-top:2px">• ${name}</span>`;
        }).join('');
    badge.innerHTML = `✅ ${docs.length} doc(s) :<br>${docList}`;
  }
}
function refreshContext() {
  fetch('/api/documents').then(r => r.json())
      .then(d => updateCtxBadge(d.documents || [])).catch(() => {});
}
async function uploadFiles(files) {
  if (!files || !files.length) return;
  setDocsStatus('⏳ Envoi en cours…', 'var(--yellow)');
  const fd = new FormData();
  Array.from(files).forEach(f => fd.append('files', f));
  try {
    const res = await fetch('/api/documents/upload', { method: 'POST', body: fd });
    const data = await res.json();
    const ok = data.added?.length;
    setDocsStatus(
        ok ? `✅ ${data.added.length} fichier(s) indexé(s)` + (data.errors?.length ? ` · ⚠️ ${data.errors.length} erreur(s)` : '')
            : '⚠️ Aucun fichier ajouté' + (data.errors?.length ? ` : ${data.errors[0]}` : ''),
        ok ? 'var(--green)' : 'var(--yellow)'
    );
    loadDocuments(); checkEnvKey();
  } catch { setDocsStatus("❌ Erreur d'upload", 'var(--red)'); }
  document.getElementById('file-input').value = '';
}
async function scanDocuments() {
  setDocsStatus('🔄 Scan en cours…', 'var(--yellow)');
  try {
    const res = await fetch('/api/documents/scan', { method: 'POST' });
    const data = await res.json();
    setDocsStatus(
        data.added?.length ? `✅ ${data.added.length} nouveau(x) fichier(s)` : 'ℹ️ Aucun nouveau fichier',
        data.added?.length ? 'var(--green)' : 'var(--txt-dim)'
    );
    loadDocuments();
  } catch { setDocsStatus('❌ Erreur de scan', 'var(--red)'); }
}
async function deleteDoc(name) {
  if (!confirm(`Supprimer "${name}" de l'index ?`)) return;
  try {
    const res = await fetch('/api/documents/' + encodeURIComponent(name), { method: 'DELETE' });
    if (res.ok) { setDocsStatus(`🗑 "${name}" supprimé`, 'var(--red)'); loadDocuments(); }
  } catch {}
}
function setDocsStatus(msg, color) {
  const el = document.getElementById('docs-status');
  el.textContent = msg; el.style.color = color;
}
function dragOver(e) { e.preventDefault(); document.getElementById('drop-zone').classList.add('dragging'); }
function dragLeave() { document.getElementById('drop-zone').classList.remove('dragging'); }
function dropFiles(e) {
  e.preventDefault();
  document.getElementById('drop-zone').classList.remove('dragging');
  uploadFiles(e.dataTransfer.files);
}

// ════════════════════════════════════════════
// DSL AGENT — NAVIGATION
// ════════════════════════════════════════════
function dslShowStep(step) {
  ['dsl-home','dsl-select','dsl-form','dsl-loading','dsl-result'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (id === 'dsl-home') {
      el.classList.toggle('hidden', step !== 'home');
    } else if (id === 'dsl-loading') {
      el.classList.toggle('active', step === 'loading');
    } else {
      el.classList.toggle('active', el.id === 'dsl-' + step);
    }
  });
}
function dslGoSelect() { buildDomainCards(); dslShowStep('select'); }
function dslNewAnalysis() {
  // Reset complet de l'état DSL
  dslDomain     = null;
  dslFormData   = {};
  dslAllResults = {};
  dslActiveTab  = null;
  dslResult     = null;
  dslRawText    = '';
  dslPanelHistory = [];
  // Reconstruire la grille de domaines et aller directement à la sélection
  buildDomainCards();
  dslShowStep('select');
}
function dslBack(step) {
  if (step === 'home') { dslDomain = null; dslFormData = {}; buildHomeDomainGrid(); }
  if (step === 'select') buildDomainCards();
  if (step === 'form') buildForm();
  dslShowStep(step);
}
function dslGoForm() { if (!dslDomain) return; buildForm(); dslShowStep('form'); }

// ════════════════════════════════════════════
// DSL — GRIDS & FORM
// ════════════════════════════════════════════
function buildHomeDomainGrid() {
  document.getElementById('home-domain-grid').innerHTML = DOMAIN_ORDER.map(id => {
    const d = DOMAINS[id];
    const locked = d.isLocked;
    return '<div class="domain-tile' + (locked ? ' domain-tile-locked' : '') + '"'
        + (locked ? '' : ' onclick="dslGoSelect()"')
        + ' title="' + (locked ? 'Bientôt disponible — roadmap Phase 2' : d.desc) + '">'
        + (d.isSoon ? '<span class="soon-badge">SOON</span>' : '')
        + '<div class="d-icon"' + (locked ? ' style="opacity:.45;filter:grayscale(1)"' : '') + '>' + d.icon + '</div>'
        + '<div class="d-id"' + (locked ? ' style="opacity:.45"' : '') + '>' + d.id + '</div>'
        + '<div class="d-lbl"' + (locked ? ' style="opacity:.45"' : '') + '>' + d.label + '</div>'
        + (locked ? '<div class="d-lock">🔒</div>' : '')
        + '</div>';
  }).join('');
}
function buildDomainCards() {
  document.getElementById('dsl-domain-cards').innerHTML = DOMAIN_ORDER.map(id => {
    const d = DOMAINS[id];
    const locked = d.isLocked;
    return '<div class="dcard'
        + (dslDomain === id ? ' selected' : '')
        + (locked ? ' dcard-locked' : '') + '"'
        + (locked ? ' title="Bientôt disponible — roadmap Phase 2"' : ' onclick="dslSelectDomain(\''+id+'\')"') + '>'
        + (d.isSoon ? '<span class="new-badge soon-badge-card">SOON</span>' : '')
        + (locked ? '<span class="lock-icon">🔒</span>' : '')
        + '<div class="di"' + (locked ? ' style="opacity:.4;filter:grayscale(1)"' : '') + '>' + d.icon + '</div>'
        + '<div class="did"' + (locked ? ' style="opacity:.4"' : '') + '>' + d.id + '</div>'
        + '<div class="dlbl"' + (locked ? ' style="opacity:.4"' : '') + '>' + d.label + '</div>'
        + '</div>';
  }).join('');
}
function dslSelectDomain(id) {
  if (DOMAINS[id].isLocked) return;
  dslDomain = id;
  buildDomainCards();
  document.getElementById('btn-continue').classList.add('ready');
}
function buildForm() {
  const d = DOMAINS[dslDomain];
  document.getElementById('form-domain-header').innerHTML = `
    <div class="dh-top"><span class="dh-icon">${d.icon}</span><span class="dh-name">${d.id} — ${d.label}</span></div>
    <div class="dh-desc">${d.desc}</div>
    <div class="dh-tools" style="margin-top:6px;font-size:11px;color:var(--txt-dark)">🔧 ${escapeHtml(d.tools || '')}</div>
    <div class="dh-all-badge">⚡ Tous les rapports seront générés automatiquement</div>`;

  document.getElementById('form-fields').innerHTML = d.fields.map(f => {
    const valStr = escapeHtml(dslFormData[f.key] || '');
    if (f.type === 'select') {
      const opts = f.opts.map(o => `<option${dslFormData[f.key]===o?' selected':''}>${o}</option>`).join('');
      return `<div class="field-group"><label class="field-label">${f.label}</label><select class="field-select" onchange="dslUpdateField('${f.key}',this.value)">${opts}</select></div>`;
    }
    return `<div class="field-group"><label class="field-label">${f.label}</label><input class="field-input" type="${f.type}" placeholder="${f.ph||''}" value="${valStr}" oninput="dslUpdateField('${f.key}',this.value)"/></div>`;
  }).join('');

  document.getElementById('form-error').style.display = 'none';
  dslUpdateConf();
}

function dslUpdateField(k, v) {
  dslFormData[k] = v;
  dslUpdateConf();
}
function dslCalcConf() {
  const d = DOMAINS[dslDomain];
  const filled = d.fields.filter(f => dslFormData[f.key] && String(dslFormData[f.key]).trim() !== '').length;
  const nums = d.fields.filter(f => f.type==='number' && dslFormData[f.key] && Number(dslFormData[f.key])>0).length;
  const total = d.fields.length;
  const totalNums = d.fields.filter(f => f.type==='number').length;
  return Math.min(97, Math.round((filled/total)*60) + Math.min(25, Math.round((nums/Math.max(1,totalNums))*25)) + 12);
}
function dslUpdateConf() {
  const hasSome = Object.entries(dslFormData).some(([k,v]) => v && String(v).trim() !== '');
  const row = document.getElementById('conf-row');
  if (!hasSome) { row.style.display = 'none'; return; }
  const conf = dslCalcConf();
  const color = conf>=85?'#3fb950':conf>=60?'#d4a017':'#e05050';
  const lbl = conf>=85?'Haute confiance':conf>=60?'Confiance modérée':'Confiance faible';
  row.style.display = 'flex';
  document.getElementById('conf-dot').style.background = color;
  document.getElementById('conf-text').style.color = color;
  document.getElementById('conf-text').textContent = `${conf}% — ${lbl}`;
}



// ════════════════════════════════════════════
// DSL — ANALYSE  →  /api/dsl/analyze
// ════════════════════════════════════════════
function tryParseJson(raw) {
  if (!raw) return null;
  let s = raw.replace(/```json/gi, '').replace(/```/g, '').trim();
  const start = s.indexOf('{');
  const end   = s.lastIndexOf('}');
  if (start === -1) return null;
  s = s.slice(start, end + 1);
  try { return JSON.parse(s); } catch(e1) {}
  try {
    let rep = s.replace(/,\s*$/, '').replace(/,\s*}$/, '}').replace(/,\s*]$/, ']');
    const opens = (rep.match(/\{/g)||[]).length - (rep.match(/\}/g)||[]).length;
    const arrs  = (rep.match(/\[/g)||[]).length - (rep.match(/\]/g)||[]).length;
    rep += ']'.repeat(Math.max(arrs,0)) + '}'.repeat(Math.max(opens,0));
    return JSON.parse(rep);
  } catch(e2) {}
  return null;
}

// ════════════════════════════════════════════
// DSL — ANALYSE MULTI-OUTPUT → /api/dsl/analyze
// Appels séquentiels avec affichage progressif
// (évite le timeout Render free tier ~30s)
// ════════════════════════════════════════════
async function dslRunAnalysis() {
  const hasSome = Object.entries(dslFormData)
      .some(([,v]) => v && String(v).trim() !== '');
  if (!hasSome) {
    const errEl = document.getElementById('form-error');
    errEl.textContent = "Veuillez renseigner au moins un champ avant d'analyser.";
    errEl.style.display = 'block'; return;
  }
  document.getElementById('form-error').style.display = 'none';

  const conf = dslCalcConf();
  const typesToGenerate = OUTPUT_TYPES.map(o => o.id); // tous les 6

  // ── Initialise la vue résultat avec onglets vides ─────────────────────
  dslAllResults = {};
  dslActiveTab  = typesToGenerate[0];
  dslResult     = null;
  dslRawText    = '';
  dslPanelHistory = [];
  dslInitResult(conf, typesToGenerate);  // affiche la structure immédiatement
  dslShowStep('result');

  // ── Helper : un appel API ─────────────────────────────────────────────
  async function callAnalyze(outputType) {
    try {
      const res = await fetch('/api/dsl/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          form_data:   dslFormData,
          domain:      dslDomain,
          output_type: outputType,
          session_id:  'dsl_' + SESSION_ID,
        }),
      });
      const data = await res.json();
      if (!res.ok) return { result: null, raw: data.error || 'Erreur serveur', error: true };
      const raw = data.raw_answer || '';
      const result = (data.result && typeof data.result === 'object')
          ? data.result : tryParseJson(raw);
      return { result, raw, error: false };
    } catch (e) {
      return { result: null, raw: e.message, error: true };
    }
  }

  // ── Appels séquentiels — chaque résultat s'affiche dès qu'il arrive ───
  let completedCount = 0;
  for (const id of typesToGenerate) {
    // Mettre le panneau en état "chargement"
    dslSetPanelLoading(id, true);
    const r = await callAnalyze(id);
    if (!r.error) {
      dslAllResults[id] = r;
      // Premier résultat → compat
      if (!dslResult) {
        dslResult  = r.result;
        dslRawText = r.raw;
      }
    }
    completedCount++;
    // Rendre le panneau immédiatement
    dslRenderPanel(id, r);
    // Mettre à jour le compteur dans le titre
    const d = DOMAINS[dslDomain];
    document.getElementById('result-title').textContent =
        `${d.icon} ${d.label} — ${completedCount}/${typesToGenerate.length} rapports`;
  }

  // Titre final
  const d = DOMAINS[dslDomain];
  document.getElementById('result-title').textContent =
      `${d.icon} ${d.label} — ${Object.keys(dslAllResults).length} rapports`;

  // Panel chat RAG
  const msgs = document.getElementById('panel-msgs');
  msgs.innerHTML = '';
  dslPanelHistory = [];
  addPanelMsg('bot',
      `${Object.keys(dslAllResults).length} rapports générés ✓\n\nPosez vos questions sur l'analyse — je m'appuie sur vos documents indexés.`);
  dslUpdateRagInfo();
}

// ── Initialise la structure onglets + panneaux (avant les données) ────────
function dslInitResult(conf, typesToGenerate) {
  const d = DOMAINS[dslDomain];

  document.getElementById('result-title').textContent =
      `${d.icon} ${d.label} — 0/${typesToGenerate.length} rapports`;

  // Badge confiance
  const color = conf>=85?'#3fb950':conf>=60?'#d4a017':'#e05050';
  const lbl   = conf>=85?'Haute confiance':conf>=60?'Confiance modérée':'Faible confiance';
  const confStyle = 'background:' + color + '18;border:1px solid ' + color + ';color:' + color;
  document.getElementById('result-conf').innerHTML =
      `<div class="conf-badge" style="${confStyle}"><span>●</span> ${conf}% — ${lbl}</div>`;

  // Onglets
  const tabsHtml = typesToGenerate.map((id, i) => {
    const ot = OUTPUT_TYPES.find(o => o.id === id);
    if (!ot) return '';
    const isActive = i === 0;
    const btnStyle = isActive
        ? ('background:' + ot.color + '18;border-color:' + ot.color + ';color:' + ot.color)
        : '';
    return `<button class="multi-tab${isActive ? ' active' : ''}" id="mtab-${id}"
      style="${btnStyle}" onclick="dslSwitchTab('${id}')">
      ${escapeHtml(ot.label)}
      <span class="tab-spinner" id="tspinner-${id}">⏳</span>
    </button>`;
  }).join('');

  // Panneaux vides
  const panelsHtml = typesToGenerate.map((id, i) =>
      `<div class="multi-panel" id="mpanel-${id}" style="${i===0?'':'display:none'}">
      <div class="panel-loading-msg" id="pload-${id}">
        <div class="spin" style="width:24px;height:24px;border-width:2px"></div>
        <span style="color:var(--txt-dim);font-size:13px">Génération en cours…</span>
      </div>
    </div>`
  ).join('');

  document.getElementById('a3-content').innerHTML =
      `<div class="multi-tabs" id="multi-tabs">${tabsHtml}</div>${panelsHtml}`;

  // Panel chat RAG — message d'attente
  const msgs = document.getElementById('panel-msgs');
  msgs.innerHTML = '';
  addPanelMsg('bot', 'Génération des rapports en cours…\nLes onglets s\'activent au fur et à mesure.');
  dslUpdateRagInfo();
}

// ── Affiche le spinner de chargement dans un panneau ─────────────────────
function dslSetPanelLoading(id, isLoading) {
  const spinner = document.getElementById('tspinner-' + id);
  if (spinner) spinner.style.display = isLoading ? '' : 'none';
}

// ── Rend le contenu d'un panneau dès réception ───────────────────────────
function dslRenderPanel(id, r) {
  const panel   = document.getElementById('mpanel-' + id);
  const pload   = document.getElementById('pload-' + id);
  const spinner = document.getElementById('tspinner-' + id);
  if (!panel) return;
  if (pload) pload.remove();
  if (spinner) spinner.style.display = 'none';

  if (r.error) {
    panel.innerHTML = `<div style="color:var(--red);padding:16px;font-size:13px">❌ ${escapeHtml(r.raw)}</div>`;
    return;
  }
  if (r.result && typeof r.result === 'object') {
    panel.innerHTML = renderA3Json(r.result);
  } else {
    panel.style.whiteSpace = 'pre-wrap';
    panel.textContent = r.raw || 'Pas de réponse.';
  }
}

// ── Affichage du résultat (kept for compat with dslBack('form') → re-render)
function dslShowResult(conf, typesToGenerate) {
  dslInitResult(conf, typesToGenerate || OUTPUT_TYPES.map(o => o.id));
  dslShowStep('result');
}


// ════════════════════════════════════════════
// DSL — RENDERERS JSON
// ════════════════════════════════════════════
function renderA3Json(r) {
  if (!r) return '<em>Pas de résultat.</em>';
  const ot = r.output_type || 'digital_a3';
  if (ot === 'Domain Not Deployed')              return renderNotDeployed(r);
  if (ot === 'Real-Time KPI Alert')              return renderKpiAlert(r);
  if (ot === 'Quick-Fix Action Card')            return renderQuickFix(r);
  if (ot === 'Executive Summary Report')         return renderExecSummary(r);
  if (ot === 'CBAM Compliance Report')           return renderCbam(r);
  if (ot === 'Cross-Domain Interdependency Report') return renderCrossDomain(r);
  return renderDigitalA3(r);
}

// ── HTML helpers ──────────────────────────────────────────────────────────
function section(icon, title, body) {
  return `<div class="a3-section">
    <div class="a3-sec-title">${icon} ${escapeHtml(title)}</div>
    <div class="a3-sec-body">${body}</div>
  </div>`;
}
function kv(label, value) {
  if (value === null || value === undefined || value === '') return '';
  return `<div class="a3-kv"><span class="a3-kv-label">${escapeHtml(label)}</span>
    <span class="a3-kv-value">${escapeHtml(String(value))}</span></div>`;
}
function badge(text, color) {
  const bStyle = 'background:' + color + '22;border:1px solid ' + color + ';color:' + color;
  return `<span class="a3-badge" style="${bStyle}">${escapeHtml(String(text))}</span>`;
}
function tbl(headers, rows) {
  return `<div style="overflow-x:auto"><table class="a3-table"><thead><tr>${headers.map(h=>`<th>${escapeHtml(h)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${typeof c==='string'&&c.startsWith('<')?c:escapeHtml(String(c??'—'))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function objToRows(obj) {
  if (!obj || typeof obj !== 'object') return '';
  return Object.entries(obj).map(([k,v]) => kv(k, v)).join('');
}

// ── OUTPUT TYPE 1 — Digital A3 ────────────────────────────────────────────
function renderDigitalA3(r) {
  let html = '';
  html += `<div class="a3-header">
    <div class="a3-header-top">
      <span class="a3-domain-badge">Domaine ${escapeHtml(r.domain||'?')}</span>
      <span class="a3-output-type">Digital A3 Report</span>
    </div>
    ${r.title ? `<div class="a3-title">${escapeHtml(r.title)}</div>` : ''}
    ${r.owner ? `<div class="a3-owner">👤 Responsable : ${escapeHtml(r.owner)}</div>` : ''}
  </div>`;
  if (r.disclaimer) html += `<div class="a3-disclaimer">⚠️ ${escapeHtml(r.disclaimer)}</div>`;
  if (r.background || r.business_case) {
    html += section('📋','Section 2 — Contexte & Business Case',
        [r.background && kv('Contexte', r.background),
          r.business_case && kv('Impact business', r.business_case)].filter(Boolean).join(''));
  }
  if (r.current_condition) {
    const cc = r.current_condition;
    let body = '';
    if (cc.kpi_baseline && typeof cc.kpi_baseline === 'object') {
      body += `<div class="a3-sub-title">KPIs de référence</div>`;
      body += tbl(['Indicateur','Valeur actuelle'], Object.entries(cc.kpi_baseline).map(([k,v])=>[k,v]));
    }
    if (cc.process_description) body += kv('État actuel', cc.process_description);
    if (cc.deviation_magnitude)  body += kv('Écart constaté', cc.deviation_magnitude);
    html += section('📏','Section 3 — Condition Actuelle', body);
  }
  if (r.target_condition) {
    const tc = r.target_condition;
    let body = '';
    if (tc.ctq_target && typeof tc.ctq_target === 'object') {
      body += `<div class="a3-sub-title">CTQ — Cibles mesurables</div>`;
      body += tbl(['KPI','Cible'], Object.entries(tc.ctq_target).map(([k,v])=>[k,v]));
    }
    if (tc.deadline)         body += kv('Délai cible', tc.deadline);
    if (tc.success_criteria) body += kv('Critère de succès', tc.success_criteria);
    html += section('🎯','Section 4 — Condition Cible', body);
  }
  if (r.root_cause_analysis) {
    const rca = r.root_cause_analysis;
    let body = '';
    if (Array.isArray(rca.five_whys) && rca.five_whys.length) {
      body += `<div class="a3-sub-title">5 Pourquoi</div><ol class="a3-whys">`;
      rca.five_whys.forEach(w => {
        body += `<li><strong>${escapeHtml(w.why||'Pourquoi ?')}</strong><br>
          <span class="a3-why-ans">→ ${escapeHtml(w.answer||'')}</span>
          ${w.root_cause ? `<br><span class="a3-root-cause">✦ Cause racine : ${escapeHtml(w.root_cause)}</span>` : ''}
        </li>`;
      });
      body += '</ol>';
    }
    if (rca.fishbone_5m && typeof rca.fishbone_5m === 'object') {
      body += `<div class="a3-sub-title">Ishikawa — 5M</div>`;
      const icons5m = {machine:'⚙️',method:'📋',manpower:'👷',material:'📦',environment:'🌡️'};
      body += '<div class="a3-5m">';
      Object.entries(rca.fishbone_5m).forEach(([m, causes]) => {
        if (!Array.isArray(causes) || !causes.length) return;
        body += `<div class="a3-5m-item">
          <div class="a3-5m-label">${icons5m[m]||''} ${escapeHtml(m.charAt(0).toUpperCase()+m.slice(1))}</div>
          <ul>${causes.map(c=>`<li>${escapeHtml(c)}</li>`).join('')}</ul>
        </div>`;
      });
      body += '</div>';
    }
    if (Array.isArray(rca.fmea) && rca.fmea.length) {
      body += `<div class="a3-sub-title">FMEA — Modes de défaillance</div>`;
      body += tbl(['Mode de défaillance','Effet','Sév.','Occ.','Dét.','RPN'],
          rca.fmea.map(f=>[f.failure_mode,f.effect,f.severity,f.occurrence,f.detection,
            `<strong style="color:${f.rpn>=200?'#e05050':f.rpn>=100?'#d4a017':'#3fb950'}">${f.rpn}</strong>`]));
    }
    html += section('🔍','Section 5 — Analyse des Causes Racines', body);
  }
  if (Array.isArray(r.countermeasures) && r.countermeasures.length) {
    html += section('✅','Section 6 — Contre-mesures',
        tbl(['Action corrective','Outil Lean/SS','Cause adressée','Responsable','Délai','Impact attendu'],
            r.countermeasures.map(c=>[c.action,c.lean_tool,c.root_cause_addressed,c.owner,c.deadline,c.expected_impact])));
  }
  if (Array.isArray(r.implementation_plan) && r.implementation_plan.length) {
    let body = '<div class="a3-impl">';
    r.implementation_plan.forEach(p => {
      body += `<div class="a3-impl-phase">
        <div class="a3-impl-phase-title">📅 ${escapeHtml(p.phase||'')} — ${escapeHtml(p.owner||'')}</div>
        <ul>${(p.actions||[]).map(a=>`<li>${escapeHtml(a)}</li>`).join('')}</ul>
        ${p.milestone ? `<div class="a3-milestone">🏁 Jalon : ${escapeHtml(p.milestone)}</div>` : ''}
      </div>`;
    });
    body += '</div>';
    html += section('📅','Section 7 — Plan de mise en œuvre', body);
  }
  if (r.results_and_control_plan) {
    const rcp = r.results_and_control_plan;
    let body = '';
    if (rcp.expected_results && typeof rcp.expected_results === 'object') {
      body += `<div class="a3-sub-title">Résultats attendus</div>`;
      body += tbl(['KPI','Valeur cible post-amélioration'], Object.entries(rcp.expected_results).map(([k,v])=>[k,v]));
    }
    if (Array.isArray(rcp.control_plan) && rcp.control_plan.length) {
      body += `<div class="a3-sub-title">Plan de contrôle</div>`;
      body += tbl(['À surveiller','Méthode','Fréquence','Seuil d\'alerte','Responsable'],
          rcp.control_plan.map(c=>[c.what_to_monitor,c.method,c.frequency,c.alert_threshold,c.responsible]));
    }
    if (Array.isArray(rcp.sustainability_actions) && rcp.sustainability_actions.length) {
      body += `<div class="a3-sub-title">Actions de pérennisation</div><ul class="a3-list">`;
      rcp.sustainability_actions.forEach(a => { body += `<li>${escapeHtml(a)}</li>`; });
      body += '</ul>';
    }
    html += section('🔒','Section 8 — Résultats & Plan de Contrôle', body);
  }
  if (r.composite_index && r.composite_index !== null) {
    const ci = r.composite_index;
    const pct = typeof ci.result_percent === 'number' ? ci.result_percent : null;
    const stColor = ci.status === 'above benchmark' ? '#3fb950' : '#e05050';
    let body = `<div class="a3-ci-header">
      <span class="a3-ci-name">${escapeHtml(ci.index_name||'')}</span>
      ${pct !== null ? `<span class="a3-ci-pct" style="color:${stColor}">${pct.toFixed(1)}%</span>` : ''}
    </div>`;
    if (ci.formula) body += `<div class="a3-ci-formula">${escapeHtml(ci.formula)}</div>`;
    if (ci.factors && typeof ci.factors === 'object') {
      body += '<div class="a3-ci-factors">';
      Object.entries(ci.factors).forEach(([k,v]) => {
        body += `<div class="a3-ci-factor"><span>${escapeHtml(k)}</span><strong>${escapeHtml(String(v))}</strong></div>`;
      });
      body += '</div>';
    }
    if (pct !== null) {
      const bm = parseFloat(ci.benchmark) || 85;
      const w  = Math.min((pct / bm) * 100, 100);
      body += `<div class="a3-ci-bar-track"><div class="a3-ci-bar-fill" style="width:${w}%;background:${stColor}"></div></div>`;
    }
    if (ci.benchmark) body += `<div class="a3-ci-bench">Benchmark world-class : ${escapeHtml(ci.benchmark)} — <strong style="color:${stColor}">${escapeHtml(ci.status||'')}</strong></div>`;
    html += section('📊','Index Composite (OEE-style)', body);
  }
  return html;
}

// ── OUTPUT TYPE 2 — KPI Alert ──────────────────────────────────────────────
function renderKpiAlert(r) {
  const sevColor = r.severity === 'red' ? '#e05050' : '#d4a017';
  let html = `<div class="a3-alert-header" style="border-color:${sevColor}">
    <span class="a3-alert-type" style="color:${sevColor}">⚠️ ${escapeHtml(r.alert_type||'Alerte KPI')}</span>
    <span class="a3-alert-sev" style="background:${sevColor}">${(r.severity||'yellow').toUpperCase()}</span>
  </div>`;
  if (r.kpi_status) {
    const k = r.kpi_status;
    html += section('📏','KPI en alerte',
        tbl(['KPI','Valeur actuelle','Seuil','Écart (%)'],
            [[k.kpi_name, `${k.current_value} ${k.unit||''}`, `${k.threshold_value} ${k.unit||''}`,
              `${k.deviation_percent > 0 ? '+' : ''}${k.deviation_percent?.toFixed(1)||'?'}%`]]));
  }
  if (r.probable_cause) html += section('🔍','Cause probable',kv('Cause',r.probable_cause));
  if (r.recommended_first_action) {
    const a = r.recommended_first_action;
    html += section('✅','Action immédiate',
        kv('Action',a.action) + kv('Délai max',a.time_limit_minutes ? a.time_limit_minutes+' min' : null) + kv('Responsable',a.responsible));
  }
  if (r.escalation_rule) html += section('🔒',"Règle d'escalade",kv('Escalade',r.escalation_rule));
  return html;
}

// ── OUTPUT TYPE 3 — Quick-Fix ─────────────────────────────────────────────
function renderQuickFix(r) {
  let html = `<div class="a3-qf-header">
    <span class="a3-output-type">Quick-Fix Action Card</span>
    <span class="a3-domain-badge">Domaine ${escapeHtml(r.domain||'?')}</span>
  </div>`;
  html += section('🔴','Problème',kv('Type',r.problem_type)+kv('Écart KPI',r.kpi_deviation));
  html += section('🔍','Cause probable',kv('Cause',r.probable_root_cause));
  if (Array.isArray(r.corrective_action_steps) && r.corrective_action_steps.length) {
    let body = '<ol class="a3-steps">';
    r.corrective_action_steps.forEach(s => {
      const step = typeof s === 'object' ? s : {step:'',action:s,reference:null};
      body += `<li>${escapeHtml(step.action||String(s))}${step.reference ? ` <code class="a3-ref">${escapeHtml(step.reference)}</code>` : ''}</li>`;
    });
    body += '</ol>';
    html += section('✅','Actions correctives — À faire MAINTENANT',body);
  }
  if (r.verification_check) {
    const v = r.verification_check;
    const body = typeof v === 'object'
        ? kv('Méthode',v.method)+kv("Critère d'acceptation",v.acceptance_criterion)+kv('Timing',v.timing)
        : kv('Vérification',v);
    html += section('✔️','Vérification (avant fin de shift)',body);
  }
  if (r.escalation_trigger) html += `<div class="a3-escalate">🔺 ${escapeHtml(r.escalation_trigger)}</div>`;
  return html;
}

// ── OUTPUT TYPE 4 — Executive Summary ────────────────────────────────────
function renderExecSummary(r) {
  let html = `<div class="a3-exec-header">
    <div class="a3-title">Executive Summary</div>
    ${r.period ? `<div class="a3-owner">📅 ${escapeHtml(r.period)}</div>` : ''}
  </div>`;
  const trafficColor = s => s==='green'?'#3fb950':s==='red'?'#e05050':'#d4a017';
  if (Array.isArray(r.performance_snapshot) && r.performance_snapshot.length) {
    let body = '<div class="a3-snap-grid">';
    r.performance_snapshot.forEach(d => {
      const sc = trafficColor(d.domain_status);
      body += `<div class="a3-snap-card" style="border-color:${sc}">
        <div class="a3-snap-domain" style="color:${sc}">Domaine ${escapeHtml(d.domain)} — ${escapeHtml(d.domain_name||'')}</div>
        ${Array.isArray(d.top_kpis) ? d.top_kpis.map(k=>
          `<div class="a3-snap-kpi">
            <span>${escapeHtml(k.kpi)}</span>
            <span style="color:${trafficColor(k.status)}">${escapeHtml(k.current_value)}</span>
            <span class="a3-snap-target">cible ${escapeHtml(k.target)}</span>
          </div>`).join('') : ''}
        ${d.composite_index_percent !== null && d.composite_index_percent !== undefined
          ? `<div class="a3-snap-ci">${escapeHtml(d.composite_index_name||'Index')} : <strong style="color:${sc}">${d.composite_index_percent.toFixed(1)}%</strong></div>` : ''}
        ${d.a3_in_progress ? '<div class="a3-snap-a3">A3 en cours</div>' : ''}
      </div>`;
    });
    body += '</div>';
    html += section('📊','§1 — Performance par domaine (traffic-light)',body);
  }
  if (Array.isArray(r.top_problems) && r.top_problems.length) {
    html += section('⚠️','§2 — Top problèmes actifs',
        tbl(['#','Problème','Domaine','A3','COPQ / Impact'],
            r.top_problems.map(p=>[p.rank||'',p.description,p.domain,p.a3_status||'—',p.copq_or_impact_estimate||'—'])));
  }
  if (Array.isArray(r.improvements_this_period) && r.improvements_this_period.length) {
    let body = '';
    r.improvements_this_period.forEach(i => {
      if (typeof i === 'object') {
        body += `<div class="a3-improve-row">
          <span>${escapeHtml(i.description||'')}</span>
          <span>${escapeHtml(i.kpi_before||'')} → <strong style="color:#3fb950">${escapeHtml(i.kpi_after||'')}</strong></span>
        </div>`;
      } else { body += `<div class="a3-improve-row">${escapeHtml(String(i))}</div>`; }
    });
    html += section('✅','§3 — Améliorations de la période',body);
  }
  if (Array.isArray(r.action_items_due) && r.action_items_due.length) {
    html += section('📋','§4 — Actions à traiter cette semaine',
        tbl(['Action','Domaine','Responsable','Délai','Priorité'],
            r.action_items_due.map(a=>[a.action,a.domain,a.owner,a.deadline,a.priority||'—'])));
  }
  if (Array.isArray(r.strategic_flags) && r.strategic_flags.length) {
    let body = '<ul class="a3-flags">';
    r.strategic_flags.forEach(f => {
      const fc = f.severity==='critical'?'#e05050':f.severity==='warning'?'#d4a017':'#4a9eff';
      const item = typeof f === 'object' ? f : {flag:f,domain:'',severity:'info'};
      body += `<li style="border-left:3px solid ${fc};padding-left:8px">
        <strong style="color:${fc}">${escapeHtml(item.flag||String(f))}</strong>
        ${item.domain ? `<span class="a3-flag-domain"> — Domaine ${escapeHtml(item.domain)}</span>` : ''}
      </li>`;
    });
    body += '</ul>';
    html += section('🚩','§5 — Alertes stratégiques',body);
  }
  return html;
}

// ── OUTPUT TYPE 5 — CBAM ──────────────────────────────────────────────────
function renderCbam(r) {
  const compliant = r.compliance_status === 'compliant';
  const sc = compliant ? '#3fb950' : '#e05050';
  const cbamBadgeStyle = 'background:' + sc + '22;border:1px solid ' + sc + ';color:' + sc;
  const cbamVerdict = compliant ? '✅ CONFORME' : '❌ NON CONFORME';
  let html = `<div class="a3-cbam-header">
    <span class="a3-output-type">CBAM Compliance Report</span>
    <span class="a3-badge" style="${cbamBadgeStyle}">${cbamVerdict}</span>
  </div>`;
  html += kv('Période de reporting', r.reporting_period);
  if (Array.isArray(r.product_categories) && r.product_categories.length)
    html += kv('Catégories produits', r.product_categories.join(', '));
  if (r.energy_summary) html += section('⚡','§2 — Bilan énergétique', objToRows(r.energy_summary));
  if (r.co2_calculation) html += section('🌡️','§3 — Calcul CO₂', objToRows(r.co2_calculation));
  let co2Body = kv('CO₂ intensité réelle (kg/u)', r.co2_intensity_kg_per_unit)
      + kv('Seuil CBAM (kg/u)', r.cbam_threshold_kg_per_unit)
      + kv('Ratio vs seuil (%)', r.intensity_vs_threshold_percent);
  if (r.compliance_gap_kg_per_unit !== undefined)
    co2Body += kv(compliant ? 'Marge (kg/u)' : 'Dépassement (kg/u)', Math.abs(r.compliance_gap_kg_per_unit));
  if (r.gap_analysis) co2Body += kv('Analyse', r.gap_analysis);
  html += section('📊','§4–5 — Intensité CO₂ & statut conformité', co2Body);
  if (Array.isArray(r.actions_taken) && r.actions_taken.length) {
    html += section('✅','§6 — Actions de réduction CO₂',
        tbl(['Action','Réduction CO₂ (kg/u)','Date'],
            r.actions_taken.map(a=>[
              typeof a === 'object' ? a.action : String(a),
              typeof a === 'object' ? (a.co2_reduction_kg_per_unit??'—') : '—',
              typeof a === 'object' ? (a.implementation_date||'—') : '—',
            ])));
  }
  if (r.projected_financial_exposure)
    html += section('💰','§7 — Exposition financière CBAM', objToRows(r.projected_financial_exposure));
  if (r.disclaimer) html += `<div class="a3-disclaimer">⚠️ ${escapeHtml(r.disclaimer)}</div>`;
  return html;
}

// ── OUTPUT TYPE 6 — Cross-Domain ──────────────────────────────────────────
function renderCrossDomain(r) {
  let html = `<div class="a3-exec-header">
    <span class="a3-output-type">Cross-Domain Interdependency Report</span>
    <span>Domaines : ${(r.domains_detected||[]).map(d=>`<span class="a3-domain-badge">${escapeHtml(d)}</span>`).join(' ')}</span>
  </div>`;
  if (r.symptom_summary && typeof r.symptom_summary === 'object') {
    let body = '<div class="a3-snap-grid">';
    Object.entries(r.symptom_summary).forEach(([dom, s]) => {
      const sc = s.severity==='critical'?'#e05050':s.severity==='warning'?'#d4a017':'#4a9eff';
      body += `<div class="a3-snap-card" style="border-color:${sc}">
        <div class="a3-snap-domain" style="color:${sc}">Domaine ${escapeHtml(dom)} — ${escapeHtml(s.domain_name||'')}</div>
        ${kv(s.key_kpi||'KPI', `${s.current_value||''} (cible ${s.target_value||'?'})`)}
        ${kv('Écart', s.deviation||'')}
      </div>`;
    });
    body += '</div>';
    html += section('📊','§1 — Symptômes par domaine',body);
  }
  if (Array.isArray(r.causal_chain) && r.causal_chain.length) {
    let body = '<div class="a3-chain">';
    r.causal_chain.forEach(c => {
      body += `<div class="a3-chain-step">
        <div class="a3-chain-arrow">
          <span class="a3-domain-badge">${escapeHtml(c.cause_domain||'?')}</span>
          <span class="a3-chain-mech">${escapeHtml(c.mechanism||'→')}</span>
          <span class="a3-domain-badge">${escapeHtml(c.effect_domain||'?')}</span>
        </div>
        <div class="a3-chain-desc">${escapeHtml(c.cause_description||'')} → ${escapeHtml(c.effect_description||'')}</div>
        ${c.estimated_amplification_factor !== null && c.estimated_amplification_factor !== undefined
          ? `<div class="a3-chain-amp">Facteur d'amplification estimé : ×${c.estimated_amplification_factor}</div>` : ''}
      </div>`;
    });
    body += '</div>';
    html += section('🔗','§2 — Chaîne causale inter-domaines',body);
  }
  if (Array.isArray(r.integrated_action_plan) && r.integrated_action_plan.length) {
    html += section('✅',"§3 — Plan d'action intégré",
        tbl(['#','Action intégrée','Domaines adressés','Outils','Responsable','Délai'],
            r.integrated_action_plan.map(a=>[
              a.rank||'', a.action||String(a),
              Array.isArray(a.domains_addressed) ? a.domains_addressed.join('+') : '—',
              Array.isArray(a.lean_tools) ? a.lean_tools.join(', ') : '—',
              a.owner||'—', a.deadline||'—',
            ])));
  }
  if (r.priority_matrix) {
    const pm = r.priority_matrix;
    let body = kv('Domaine prioritaire', pm.priority_domain) + kv('Justification', pm.rationale);
    if (Array.isArray(pm.treatment_sequence) && pm.treatment_sequence.length) {
      body += `<div class="a3-kv"><span class="a3-kv-label">Séquence de traitement</span>
        <span class="a3-kv-value">${pm.treatment_sequence.map((d,i)=>
          `<span class="a3-domain-badge">${i+1}. ${escapeHtml(d)}</span>`).join(' → ')}</span></div>`;
    }
    html += section('🎯','§4 — Matrice de priorité',body);
  }
  if (r.disclaimer) html += `<div class="a3-disclaimer">⚠️ ${escapeHtml(r.disclaimer)}</div>`;
  return html;
}

// ── Domain Not Deployed ───────────────────────────────────────────────────
function renderNotDeployed(r) {
  return `<div class="a3-not-deployed">
    <div style="font-size:32px;margin-bottom:10px">🚧</div>
    <div style="font-size:16px;font-weight:700;margin-bottom:6px">Domaine non déployé</div>
    <div style="color:var(--txt-dim);font-size:13px">${escapeHtml(r.message||'')}</div>
    <div style="color:var(--txt-dark);font-size:11px;margin-top:8px">${escapeHtml(r.roadmap_note||'')}</div>
  </div>`;
}

// ── Copier le rapport ──────────────────────────────────────────────────────
function copyA3() {
  const text = dslResult ? JSON.stringify(dslResult, null, 2) : (dslRawText || '');
  navigator.clipboard.writeText(text).then(() => alert('Rapport copié !')).catch(() => {});
}

// ════════════════════════════════════════════
// DSL — PANEL CHAT RAG (post-A3) → /api/dsl/chat
// ════════════════════════════════════════════
async function dslUpdateRagInfo() {
  try {
    const r = await fetch('/api/documents');
    const d = await r.json();
    const n = d.documents?.length || 0;
    document.getElementById('rag-info').textContent =
        n > 0 ? `📄 ${n} doc(s) indexé(s) — contexte RAG actif` : '⚠️ Aucun document — réponses basées sur bonnes pratiques';
  } catch {
    document.getElementById('rag-info').textContent = '⚠️ Backend non connecté';
  }
}
function addPanelMsg(role, content) {
  const msgs = document.getElementById('panel-msgs');
  const div = document.createElement('div');
  div.className = 'pmsg ' + role;
  div.textContent = content;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}
async function sendPanel() {
  if (dslPanelLoading) return;
  const inputEl = document.getElementById('panel-input');
  const q = inputEl.value.trim();
  if (!q) return;
  inputEl.value = '';
  document.getElementById('panel-send').disabled = true;
  dslPanelLoading = true;
  addPanelMsg('user', q);
  const thinking = addPanelMsg('bot', '…');
  thinking.classList.add('thinking');
  dslPanelHistory.push({ role: 'user', content: q });
  const a3Context = dslResult
      ? `Domaine ${dslResult.domain||dslDomain} — ${dslResult.title||''}`
      : '';
  try {
    const res = await fetch('/api/dsl/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question:    q,
        a3_context:  dslPanelHistory.length === 1 ? a3Context : '',
        session_id:  'dsl_chat_' + SESSION_ID,
      }),
    });
    const data = await res.json();
    const ans = data.answer || data.error || 'Erreur.';
    thinking.textContent = ans;
    thinking.classList.remove('thinking');
    dslPanelHistory.push({ role: 'assistant', content: ans });
  } catch (e) {
    thinking.textContent = '❌ Erreur : ' + e.message;
    thinking.classList.remove('thinking');
  }
  dslPanelLoading = false;
  document.getElementById('panel-send').disabled = false;
}
function panelKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendPanel(); }
}

// ════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════
window.addEventListener('DOMContentLoaded', () => {
  checkEnvKey();
  refreshContext();
  buildHomeDomainGrid();

  // Sidebar overlay close on click
  document.getElementById('sidebar-overlay').addEventListener('click', closeSidebar);
});