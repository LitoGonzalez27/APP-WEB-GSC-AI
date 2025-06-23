// static/js/ui-ai-overview-download.js - Versión modificada para deshabilitar el botón interno

import { elems } from './utils.js';
import { getAIOverviewResults } from './ui-ai-overview-main.js';

export function downloadExcelWithAI() {
  
  // En su lugar, mostramos un mensaje informativo
  const resultsContainer = document.getElementById('aiOverviewResultsContainer');
  if (!resultsContainer) return;
  
  // Verificar si ya existe el mensaje
  let infoMessage = resultsContainer.querySelector('.download-info-message');
  if (infoMessage) return;
  
  // Crear mensaje informativo
  infoMessage = document.createElement('div');
  infoMessage.className = 'download-info-message';
  infoMessage.style.cssText = `
    background: #e8f4f8;
    color: #0066cc;
    padding: 12px 20px;
    border-radius: 8px;
    margin: 15px auto;
    text-align: center;
    font-size: 14px;
    border: 1px solid #b3d9eb;
    max-width: 600px;
  `;
  infoMessage.innerHTML = '<i class="fas fa-info-circle"></i> To download the AI Overview analysis, use the "Download Excel" button at the bottom of the page.';
  
  const summaryDiv = resultsContainer.querySelector('.ai-overview-summary');
  if (summaryDiv) {
    summaryDiv.appendChild(infoMessage);
  } else {
    resultsContainer.appendChild(infoMessage);
  }
}

// El resto de las funciones las mantenemos por si se necesitan en el futuro
// pero no se usarán directamente

function createDownloadButton(hasValidData) {
  const button = document.createElement('button');
  button.innerHTML = '<i class="fas fa-download"></i> Download Excel with AI Analysis';
  button.className = 'btn-download-ai-excel';
  button.style.cssText = `
    background: #28a745;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    cursor: pointer;
    margin: 15px auto;
    display: block;
    font-weight: 600;
    transition: background-color 0.3s ease, transform 0.2s ease;
  `;
  button.disabled = !hasValidData;
  
  setupButtonEffects(button);
  
  return button;
}

function setupButtonEffects(button) {
  button.addEventListener('mouseenter', () => {
    if (!button.disabled) button.style.backgroundColor = '#218838';
  });
  
  button.addEventListener('mouseleave', () => {
    if (!button.disabled) button.style.backgroundColor = '#28a745';
  });
  
  button.addEventListener('mousedown', () => {
    if (!button.disabled) button.style.transform = 'scale(0.98)';
  });
  
  button.addEventListener('mouseup', () => {
    if (!button.disabled) button.style.transform = 'scale(1)';
  });
}

// Funciones auxiliares mantenidas para compatibilidad
async function handleDownloadClick(button, hasValidData, aiOverviewResults) {
  // Esta función ya no se usa, pero la mantenemos por compatibilidad
  console.warn('handleDownloadClick llamado pero no debería usarse. Use el botón principal.');
}

function extractFormData() {
  const site_url = elems.siteUrlSelect ? elems.siteUrlSelect.value : null;
  const urlsText = document.querySelector('textarea[name="urls"]');
  const urls = urlsText ? urlsText.value.split('\n').map(u => u.trim()).filter(u => u) : [];
  const months = [...document.querySelectorAll('#monthChips .chip.selected')].map(c => c.dataset.value);
  const match_type = elems.matchType ? elems.matchType.value : null;

  return { site_url, urls, months, match_type };
}