// static/js/ui-ai-overview-main.js - Archivo principal con inicialización y control

import { elems } from './utils.js';
import { handleAIOverviewAnalysis } from './ui-ai-overview-analysis.js';

let aiOverviewResults = null;

export function initAIOverviewAnalysis() {
  // Buscar el contenedor de la tabla de keywords en lugar del título
  const keywordComparisonBlock = document.getElementById('keywordComparisonBlock');
  if (!keywordComparisonBlock) {
    console.warn("Elemento keywordComparisonBlock no encontrado para initAIOverviewAnalysis.");
    return;
  }

  let existingButton = document.getElementById('analyzeAIOverviewBtn');
  if (existingButton) return;

  // Insertar el botón DESPUÉS de la tabla de keywords
  const buttonContainer = createButtonContainer();
  
  // Insertar después del bloque de la tabla
  keywordComparisonBlock.parentNode.insertBefore(buttonContainer, keywordComparisonBlock.nextSibling);
  
  const analyzeBtn = document.getElementById('analyzeAIOverviewBtn');
  analyzeBtn.addEventListener('click', () => handleAIOverviewAnalysis(aiOverviewResults, setAIOverviewResults));
  
  // Efectos hover
  setupButtonEffects(analyzeBtn);
}

export function enableAIOverviewAnalysis(keywordComparisonData, siteUrl) {
  const analyzeBtn = document.getElementById('analyzeAIOverviewBtn');
  const statusSpan = document.getElementById('aiAnalysisStatus');
  
  if (analyzeBtn && keywordComparisonData && keywordComparisonData.length > 0 && siteUrl) { 
    analyzeBtn.disabled = false;
    analyzeBtn.dataset.keywordData = JSON.stringify(keywordComparisonData);
    analyzeBtn.dataset.siteUrl = siteUrl; 
    if (statusSpan) {
      statusSpan.textContent = '';  // Eliminar texto de keywords disponibles
      statusSpan.style.display = 'none';  // Ocultar completamente el span
    }
  } else {
    if (analyzeBtn) analyzeBtn.disabled = true;
    if (statusSpan) {
      statusSpan.textContent = 'No keyword data or site URL available';
      statusSpan.style.color = '#dc3545';
    }
  }
}

function createButtonContainer() {
  const buttonContainer = document.createElement('div');
  buttonContainer.className = 'ai-analysis-controls';
  buttonContainer.style.cssText = 'text-align: center; margin: 2em 0 1em 0; padding: 1.5em; background: rgba(255,255,255,0.1); border-radius: var(--radius-lg); backdrop-filter: blur(10px); border-top: 2px solid rgba(102, 126, 234, 0.3);';
  
  buttonContainer.innerHTML = `
    <div style="margin-bottom: 1em; font-size: 0.9em; color: #666;">
      <i class="fas fa-robot"></i> Análisis de Visibilidad AI Overview
    </div>
    <button id="analyzeAIOverviewBtn" class="btn-ai-overview" style="
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      border: none;
      padding: 12px 24px; /* Default padding, will be overridden by CSS */
      border-radius: var(--radius-sm); /* Use variable for border-radius */
      font-weight: 600;
      cursor: pointer;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
      margin-right: 10px;
    " disabled>
      <i class="fas fa-robot" style="margin-right: 8px;"></i>
      Analizar Visibilidad AI
    </button>
    <span id="aiAnalysisStatus" style="color: #666; font-size: 0.9em; margin-left: 10px;">
      Selecciona datos primero
    </span>
  `;
  
  return buttonContainer;
}

function setupButtonEffects(button) {
  button.addEventListener('mouseenter', () => {
    if (!button.disabled) {
      button.style.transform = 'translateY(-2px)';
      button.style.boxShadow = '0 6px 20px rgba(102, 126, 234, 0.4)';
    }
  });
  
  button.addEventListener('mouseleave', () => {
    if (!button.disabled) {
      button.style.transform = 'translateY(0)';
      button.style.boxShadow = '0 4px 15px rgba(102, 126, 234, 0.3)';
    }
  });
}

function setAIOverviewResults(results) {
  aiOverviewResults = results;
  window.currentAIOverviewData = results;
}

export function getAIOverviewResults() {
  return aiOverviewResults;
}