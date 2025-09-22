// static/js/ui-ai-overview-modals.js - Manejo de modales y diálogos

import { escapeHtml } from './ui-ai-overview-utils.js';

export function showAIDetailsModalImproved(result) {
  const modalId = 'aiDetailsModal';
  let modal = document.getElementById(modalId);
  if (modal) modal.remove();

  modal = document.createElement('div');
  modal.id = modalId;
  modal.className = 'modal ai-details-modal';
  modal.style.cssText = 'display: block; position: fixed; z-index: 10000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.6); overflow-y: auto;';
  
  const aiAnalysis = result.ai_analysis || getDefaultAIAnalysis();
  const aiElements = Array.isArray(aiAnalysis.ai_overview_detected) ? aiAnalysis.ai_overview_detected : [];
  const debugInfo = aiAnalysis.debug_info || {};
  
  const debugSection = createDebugSection(debugInfo);
  const domainAsSourceHTML = createDomainAsSourceSection(aiAnalysis);
  const impactSummaryHTML = createImpactSummaryHTML(aiAnalysis, result);
  const elementsListHTML = createElementsListHTML(aiElements);

  modal.innerHTML = createModalHTML(result, debugSection, impactSummaryHTML, elementsListHTML, domainAsSourceHTML);
  
  document.body.appendChild(modal);
  setupModalEventListeners(modal, result);
}

function getDefaultAIAnalysis() {
  return { 
    impact_score: 0, 
    ai_overview_detected: [],
    has_ai_overview: false,
    total_elements: 0,
    domain_is_ai_source: false,
    domain_ai_source_position: null,
    domain_ai_source_link: null,
    debug_info: {}
  };
}

function createDebugSection(debugInfo) {
  if (Object.keys(debugInfo).length === 0) return '';
  
  return `
    <div class="debug-section" style="margin-top: 1.5em; padding: 1em; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #17a2b8;">
      <h5 style="color: #17a2b8; margin-bottom: 0.8em; font-size: 1em;">
        <i class="fas fa-bug"></i> Debugging Information
      </h5>
      <details>
        <summary style="cursor: pointer; font-weight: bold; color: #495057;">View technical details</summary>
        <pre style="background: #fff; padding: 0.8em; border-radius: 4px; overflow-x: auto; font-size: 0.8em; margin-top: 0.5em; white-space: pre-wrap;">${JSON.stringify(debugInfo, null, 2)}</pre>
      </details>
    </div>
  `;
}

function createDomainAsSourceSection(aiAnalysis) {
  if (!aiAnalysis.has_ai_overview) return '';
  
  const domainIsAISource = aiAnalysis.domain_is_ai_source || false;
  const domainAISourcePos = aiAnalysis.domain_ai_source_position;
  const domainAISourceLink = aiAnalysis.domain_ai_source_link;

  return `
    <div class="ai-source-domain-info" style="margin-top: 1.5em; padding: 1em; border-radius: 8px; ${domainIsAISource ? 'background: rgba(40, 167, 69, 0.1); border-left: 4px solid #28a745;' : 'background: rgba(220, 53, 69, 0.1); border-left: 4px solid #dc3545;'}">
      <h5 style="margin-bottom: 0.8em; color: ${domainIsAISource ? '#28a745' : '#dc3545'}; font-size: 1em;">
        <i class="fas fa-${domainIsAISource ? 'check-circle' : 'times-circle'}"></i> 
        Your Domain in AI Overview
      </h5>
      ${domainIsAISource
        ? `<p style="color: #28a745; margin-bottom: 0.5em; font-weight: bold;">
             <strong>FOUND</strong> at position <strong>#${escapeHtml(String(domainAISourcePos))}</strong>
           </p>
           ${domainAISourceLink 
             ? `<p style=\"font-size: 0.9em;\"><a href=\"${escapeHtml(domainAISourceLink)}\" target=\"_blank\" rel=\"noopener noreferrer\" style=\"color: #007bff;\">🔗 View source link</a></p>`
             : ''
           }`
        : '<p style="color: #dc3545; font-weight: bold;"><strong>NOT found</strong> as a direct source in the main AI Overview.</p>'
      }
    </div>
  `;
}

// Corrección en ui-ai-overview-modals.js
// Función createImpactSummaryHTML modificada para manejar correctamente la posición 0

function createImpactSummaryHTML(aiAnalysis, result) {
  const deltaClicks = result.delta_clicks_absolute != null 
    ? result.delta_clicks_absolute 
    : ((result.clicks_m2 - result.clicks_m1));

  const deltaPosition = result.delta_position_absolute != null
    ? (typeof result.delta_position_absolute === 'number' ? result.delta_position_absolute : null)
    : (typeof result.position_m2 === 'number' && typeof result.position_m1 === 'number' 
        ? result.position_m2 - result.position_m1 
        : null);

  return `
    <div class="ai-impact-summary" style="
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 1em;
      margin-bottom: 2em;
    ">
      <div class="impact-metric" style="text-align: center; padding: 1em; background: #f0f2f5; border-radius: 10px;">
        <div style="font-size: 1.8em; font-weight: bold; color: #007bff;">${aiAnalysis.ai_overview_detected.length}</div>
        <div style="color: #555; font-size: 0.9em;">Rich Snippets</div>
      </div>
      <div class="impact-metric" style="text-align: center; padding: 1em; background: #f0f2f5; border-radius: 10px;">
        <div style="font-size: 1.8em; font-weight: bold; color: ${(result.site_position !== null && result.site_position !== undefined) ? '#28a745' : '#6c757d'};">
          ${(result.site_position !== null && result.site_position !== undefined) 
            ? (result.site_position === 0 
                ? '#0'
                : '#' + result.site_position)
            : 'N/F'
          }
        </div>
        <div style="color: #555; font-size: 0.9em;">Pos. Orgánica</div>
      </div>
      <div class="impact-metric" style="text-align: center; padding: 1em; background: #f0f2f5; border-radius: 10px;">
        <div style="font-size: 1.8em; font-weight: bold; color: ${deltaClicks < 0 ? '#dc3545' : '#28a745'};">
          ${deltaClicks > 0 ? '+' : ''}${deltaClicks}
        </div>
        <div style="color: #555; font-size: 0.9em;">Clics Δ</div>
      </div>
      <div class="impact-metric" style="text-align: center; padding: 1em; background: #f0f2f5; border-radius: 10px;">
        <div style="font-size: 1.8em; font-weight: bold; color: ${deltaPosition != null ? (deltaPosition > 0 ? '#dc3545' : '#28a745') : '#6c757d'};">
          ${deltaPosition != null ? (deltaPosition > 0 ? '+' : '') + deltaPosition.toFixed(1) : 'N/A'}
        </div>
        <div style="color: #555; font-size: 0.9em;">Pos. Δ</div>
      </div>
    </div>
  `;
}

function createElementsListHTML(aiElements) {
  if (aiElements.length === 0) {
    return `
      <div style="text-align: center; padding: 2em; color: #28a745;">
        <i class="fas fa-check-circle" style="font-size: 2.5em; margin-bottom: 0.8em;"></i>
        <h4 style="font-size: 1.1em;">No rich snippets detected</h4>
        <p style="font-size: 0.9em;">This keyword shows no signs of AI Overview interference.</p>
      </div>
    `;
  }

  return `
    <h4 style="margin: 1.5em 0 1em 0; color: #333; font-size: 1.1em;">Detected Rich Snippets:</h4>
    <div class="ai-elements-list" style="max-height: 250px; overflow-y: auto; padding-right: 10px;">
      ${aiElements.map((element, index) => createElementCard(element, index)).join('')}
    </div>
  `;
}

function createElementCard(element, index) {
  let specificElementDomainInfo = '';
  if (element.type && element.type.includes('AI Overview') && element.domain_is_source) {
    specificElementDomainInfo = `
      <div style="font-size: 0.8em; color: #1a73e8; margin-top: 5px; padding-top: 5px; border-top: 1px dashed #ddd;">
        <em>✅ Tu dominio es fuente #${escapeHtml(String(element.domain_source_position))} en este bloque.</em>
        ${element.domain_source_link ? `<br><a href="${escapeHtml(element.domain_source_link)}" target="_blank" rel="noopener noreferrer" style="color: #007bff; font-size:0.9em;">🔗 Ver enlace específico</a>` : ''}
      </div>`;
  }

  return `
    <div class="ai-element-card" style="
      background: ${element?.type?.toLowerCase().includes('ai overview') ? 'rgba(220, 53, 69, 0.08)' : 'rgba(255, 193, 7, 0.08)'};
      border-left: 4px solid ${element?.type?.toLowerCase().includes('ai overview') ? '#dc3545' : '#ffc107'};
      padding: 1em;
      margin: 0.8em 0;
      border-radius: 8px;
    ">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5em;">
        <strong style="color: #333; font-size: 1em;">${escapeHtml(element.type || 'Unknown Type')}</strong>
        <span style="background: #007bff; color: white; padding: 3px 8px; border-radius: 10px; font-size: 0.75em;">
          Position: ${element.position != null ? element.position : index + 1}
        </span>
      </div>
      ${element.content_length ? `<div style=\"color: #555; font-size: 0.85em;\">📝 Length: ${element.content_length} characters</div>` : ''}
      ${element.sources_count ? `<div style=\"color: #555; font-size: 0.85em;\">🔗 Sources: ${element.sources_count}</div>` : ''}
      ${element.source ? `<div style=\"color: #555; font-size: 0.85em;\">📍 Source: ${escapeHtml(element.source)}</div>` : ''}
      ${element.count ? `<div style=\"color: #555; font-size: 0.85em;\">🔢 Elements: ${element.count}</div>` : ''}
      ${element.title ? `<div style=\"color: #555; font-size: 0.85em;\">📋 Title: ${escapeHtml(element.title)}</div>` : ''}
      ${specificElementDomainInfo}
    </div>
  `;
}

function createModalHTML(result, debugSection, impactSummaryHTML, elementsListHTML, domainAsSourceHTML) {
  return `
    <div class="modal-content" style="
      background: white;
      margin: 5% auto;
      padding: 0;
      border-radius: 15px;
      width: 90%;
      max-width: 900px;
      max-height: 85vh; 
      display: flex; 
      flex-direction: column; 
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    ">
      <div class="modal-header" style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5em 2em;
        border-radius: 15px 15px 0 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
      ">
        <h3 style="margin: 0; display: flex; align-items: center; font-size: 1.2em;">
          <i class="fas fa-robot" style="margin-right: 10px;"></i>
          AI Analysis: "${escapeHtml(result.keyword)}"
          ${result.analysis_successful === false ? '<span style="background: rgba(255,193,7,0.8); color: #000; padding: 2px 6px; border-radius: 10px; font-size: 0.7em; margin-left: 10px;">⚠️ CHECK</span>' : ''}
        </h3>
        <span class="close-ai-modal" style="
          font-size: 2em;
          cursor: pointer;
          opacity: 0.8;
          transition: opacity 0.3s;
        ">&times;</span>
      </div>
      <div class="modal-body" style="padding: 1.5em 2em; overflow-y: auto; flex-grow: 1;">
        ${impactSummaryHTML}
        ${elementsListHTML}
        ${domainAsSourceHTML}
        ${debugSection}
      </div>
      <div class="modal-footer" style="
        padding: 1em 2em;
        background-color: #f8f9fa;
        border-top: 1px solid #dee2e6;
        border-radius: 0 0 15px 15px;
        text-align: right;
      ">
        <button class="btn-view-serp" data-keyword="${escapeHtml(result.keyword)}" data-url="${escapeHtml(result.url || (result.site_result ? result.site_result.link : ''))}" style="
          background: #17a2b8; color: white; border: none; padding: 10px 18px; border-radius: 8px; cursor: pointer; margin-right: 10px; font-size: 0.9em;
        ">
        <i class="fas fa-search"></i> View SERP
        </button>
        <button class="btn-close-ai-modal" style="
          background: #6c757d; color: white; border: none; padding: 10px 18px; border-radius: 8px; cursor: pointer; font-size: 0.9em;
        ">
          Close
        </button>
      </div>
    </div>
  `;
}

function setupModalEventListeners(modal, result) {
  // Cerrar modal
  modal.querySelector('.close-ai-modal').addEventListener('click', () => modal.remove());
  modal.querySelector('.btn-close-ai-modal').addEventListener('click', () => modal.remove());
  
  // Ver SERP
  const viewSerpBtn = modal.querySelector('.btn-view-serp');
  if (viewSerpBtn) {
    viewSerpBtn.addEventListener('click', (e) => {
      const keyword = e.currentTarget.dataset.keyword;
      const url = e.currentTarget.dataset.url;
      if (window.openSerpModal) {
        window.openSerpModal(keyword, url);
      } else {
        console.warn('openSerpModal no está disponible globalmente.');
      }
    });
  }
  
  // Cerrar modal al hacer click fuera
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.remove();
  });
}