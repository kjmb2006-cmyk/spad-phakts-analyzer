/* ── SPAD Analyzer — JavaScript principal ── */

'use strict';

// ── Sidebar toggle ────────────────────────────────────────────────────────────
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebar       = document.getElementById('sidebar');
const mainContent   = document.getElementById('mainContent');

if (sidebarToggle && sidebar) {
  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');        // mobile
    if (window.innerWidth > 768) {
      const collapsed = sidebar.style.width === '0px';
      sidebar.style.width        = collapsed ? '240px' : '0px';
      mainContent.style.marginLeft = collapsed ? '240px' : '0px';
    }
  });
}

// ── Rendu des graphiques Plotly depuis JSON ───────────────────────────────────
function renderPlotly(containerId, jsonData) {
  if (!containerId || !jsonData) return;
  const el = document.getElementById(containerId);
  if (!el) return;
  try {
    const fig = (typeof jsonData === 'string') ? JSON.parse(jsonData) : jsonData;
    Plotly.newPlot(el, fig.data, fig.layout || {}, {
      responsive:    true,
      displaylogo:   false,
      modeBarButtonsToRemove: ['sendDataToCloud', 'lasso2d', 'select2d'],
    });
  } catch (e) {
    el.innerHTML = `<div class="alert alert-warning">Graphique indisponible : ${e.message}</div>`;
  }
}

// Initialisation automatique — cherche tous les éléments [data-plotly]
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-plotly]').forEach(el => {
    const src = el.dataset.plotly;
    try {
      renderPlotly(el.id, src);
    } catch (_) {}
  });
});

// ── Auto-dismiss des alertes flash après 5 s ──────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    document.querySelectorAll('.alert.alert-success, .alert.alert-info').forEach(a => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(a);
      bsAlert.close();
    });
  }, 5000);
});

// ── Confirmation avant réinitialisation des données ───────────────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});
