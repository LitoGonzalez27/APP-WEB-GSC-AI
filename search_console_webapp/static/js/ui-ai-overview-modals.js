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
  const ctrAnalysisHTML = createCTRAnalysisHTML(result);
  const aioPreviewHTML = createAIOPreviewSection(aiAnalysis, debugInfo, result);
  const elementsListHTML = createElementsListHTML(aiElements);

  modal.innerHTML = createModalHTML(result, debugSection, impactSummaryHTML, ctrAnalysisHTML, aioPreviewHTML, elementsListHTML, domainAsSourceHTML);
  
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

// 🆕 CTR Benchmark Analysis section for the detail modal
function createCTRAnalysisHTML(result) {
  const ctr = result._ctr_analysis;
  if (!ctr || ctr.expected_ctr === null || ctr.actual_ctr === null) {
    return ''; // No CTR data available — graceful fallback
  }

  const expectedPct = (ctr.expected_ctr * 100).toFixed(1);
  const actualPct = (ctr.actual_ctr * 100).toFixed(1);
  const gapPct = ctr.ctr_gap !== null ? (ctr.ctr_gap * 100).toFixed(1) : null;
  const absorbed = ctr.clicks_absorbed || 0;
  const isUnderperforming = ctr.ctr_gap > 0;
  const position = result.position_m2 != null ? Math.round(result.position_m2) : '?';

  const gapColor = isUnderperforming ? '#dc3545' : '#28a745';
  const gapLabel = isUnderperforming ? 'below benchmark' : 'above benchmark';

  return `
    <div class="ctr-benchmark-section" style="
      margin: 1.5em 0;
      padding: 1.2em;
      background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
      border-radius: 10px;
      border-left: 4px solid ${gapColor};
    ">
      <h5 style="margin-bottom: 0.8em; color: #333; font-size: 1em;">
        <i class="fas fa-chart-bar" style="margin-right: 6px; color: #6f42c1;"></i>
        CTR Benchmark Analysis
      </h5>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1em; margin-bottom: 0.8em;">
        <div style="text-align: center; padding: 0.8em; background: white; border-radius: 8px;">
          <div style="font-size: 0.75em; color: #888; margin-bottom: 0.3em;">Expected CTR (pos #${position})</div>
          <div style="font-size: 1.6em; font-weight: bold; color: #6c757d;">${expectedPct}%</div>
        </div>
        <div style="text-align: center; padding: 0.8em; background: white; border-radius: 8px;">
          <div style="font-size: 0.75em; color: #888; margin-bottom: 0.3em;">Actual CTR (GSC)</div>
          <div style="font-size: 1.6em; font-weight: bold; color: ${isUnderperforming ? '#dc3545' : '#28a745'};">${actualPct}%</div>
        </div>
      </div>
      ${gapPct !== null ? `
        <div style="text-align: center; margin-bottom: 0.6em;">
          <span style="
            display: inline-block;
            padding: 4px 14px;
            border-radius: 20px;
            background: ${gapColor}15;
            color: ${gapColor};
            font-weight: 700;
            font-size: 0.95em;
          ">
            CTR Gap: ${isUnderperforming ? '+' : ''}${gapPct}% ${gapLabel}
          </span>
        </div>
      ` : ''}
      ${absorbed > 0 ? `
        <div style="text-align: center; margin-bottom: 0.5em;">
          <span style="color: #dc3545; font-weight: 600; font-size: 0.9em;">
            ≈ ${absorbed} clicks/month absorbed
          </span>
        </div>
      ` : ''}
      <p style="color: #666; font-size: 0.78em; line-height: 1.5; margin: 0.5em 0 0 0; text-align: center;">
        At position #${position}, the industry benchmark CTR is ${expectedPct}%.
        Your actual CTR is ${actualPct}%.
        ${isUnderperforming
          ? `This ${gapPct}% gap represents approximately ${absorbed} clicks that may be absorbed by SERP features.`
          : `Your CTR exceeds the benchmark, suggesting strong click performance despite SERP features.`
        }
      </p>
      ${_createSerpFeaturesDetailHTML(ctr)}
    </div>
  `;
}

/**
 * Creates the AI Overview Preview section for the keyword detail modal.
 * Shows: content preview, cited sources with indicators, position mockup.
 */
function createAIOPreviewSection(aiAnalysis, debugInfo, result) {
  if (!aiAnalysis.has_ai_overview) return '';

  const contentPreview = debugInfo.aio_content_preview || '';
  const references = debugInfo.references_found || [];
  const isDomainSource = aiAnalysis.domain_is_ai_source || false;
  const domainPos = aiAnalysis.domain_ai_source_position;
  const serpPosition = debugInfo.aio_serp_position || 'unknown';
  const totalBlocks = debugInfo.total_text_blocks || 0;

  // Get site URL for matching
  const siteUrl = debugInfo.site_url_normalized || '';

  // --- 1. Content preview ---
  let contentHTML = '';
  if (contentPreview) {
    const truncated = contentPreview.length >= 490
      ? contentPreview.substring(0, 300) + '...'
      : contentPreview;
    contentHTML = `
      <div style="margin-bottom: 1.2em;">
        <div style="
          display: flex; align-items: center; gap: 6px;
          margin-bottom: 0.5em;
          font-size: 0.82em; font-weight: 600; color: #444;
        ">
          <i class="fas fa-align-left" style="color: #6f42c1;"></i>
          AI Overview Content
          <span style="font-weight: 400; color: #888; font-size: 0.9em;">(${totalBlocks} block${totalBlocks !== 1 ? 's' : ''})</span>
        </div>
        <div style="
          background: #f8f9fa; border-radius: 8px; padding: 0.9em 1em;
          font-size: 0.85em; line-height: 1.65; color: #333;
          border-left: 3px solid #6f42c1;
          max-height: 120px; overflow-y: auto;
        ">
          <i class="fas fa-robot" style="color: #6f42c1; margin-right: 4px; opacity: 0.6;"></i>
          ${escapeHtml(truncated)}
        </div>
      </div>
    `;
  }

  // --- 2. Cited sources list ---
  let sourcesHTML = '';
  if (references.length > 0) {
    const sourceItems = references.map((ref, i) => {
      const refLink = ref.link || '';
      const refSource = ref.source || '';
      const refTitle = ref.title || refSource || refLink;

      // Check if this is the user's domain
      let isUserDomain = false;
      if (siteUrl) {
        const normalizedRef = (refLink + ' ' + refSource).toLowerCase();
        const normalizedSite = siteUrl.toLowerCase().replace(/^www\./, '');
        isUserDomain = normalizedRef.includes(normalizedSite);
      }

      const pos = i + 1;
      const bgColor = isUserDomain ? 'rgba(40, 167, 69, 0.08)' : 'transparent';
      const borderColor = isUserDomain ? '#28a745' : '#e9ecef';
      const indicator = isUserDomain
        ? '<span style="color: #28a745; font-weight: 700; font-size: 0.85em; white-space: nowrap;"><i class="fas fa-check-circle"></i> You</span>'
        : '<span style="color: #aaa; font-size: 0.85em;"><i class="fas fa-external-link-alt"></i></span>';

      // Extract domain from link
      let displayDomain = refSource || '';
      if (!displayDomain && refLink) {
        try { displayDomain = new URL(refLink).hostname; } catch (e) { displayDomain = refLink; }
      }

      return `
        <div style="
          display: flex; align-items: center; gap: 10px;
          padding: 8px 10px; border-radius: 8px;
          background: ${bgColor}; border: 1px solid ${borderColor};
          ${isUserDomain ? 'box-shadow: 0 0 0 1px rgba(40, 167, 69, 0.15);' : ''}
        ">
          <div style="
            min-width: 28px; height: 28px;
            background: ${isUserDomain ? '#28a745' : '#6c757d'};
            color: white; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 0.78em;
          ">${pos}</div>
          <div style="flex: 1; min-width: 0;">
            <div style="font-size: 0.82em; font-weight: 600; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
              title="${escapeHtml(refTitle)}"
            >${escapeHtml(refTitle.length > 55 ? refTitle.substring(0, 55) + '...' : refTitle)}</div>
            <div style="font-size: 0.72em; color: #888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              ${escapeHtml(displayDomain)}
            </div>
          </div>
          ${indicator}
        </div>
      `;
    }).join('');

    sourcesHTML = `
      <div style="margin-bottom: 1.2em;">
        <div style="
          display: flex; align-items: center; gap: 6px;
          margin-bottom: 0.5em;
          font-size: 0.82em; font-weight: 600; color: #444;
        ">
          <i class="fas fa-quote-right" style="color: #17a2b8;"></i>
          Cited Sources
          <span style="font-weight: 400; color: #888; font-size: 0.9em;">(${references.length})</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px; max-height: 220px; overflow-y: auto; padding-right: 4px;">
          ${sourceItems}
        </div>
      </div>
    `;
  }

  // --- 3. Position mini-mockup ---
  let positionMockupHTML = '';
  if (references.length > 0) {
    const maxShow = Math.min(references.length, 6);
    const slots = [];
    for (let i = 0; i < maxShow; i++) {
      const ref = references[i];
      const refLink = ref.link || '';
      const refSource = ref.source || '';
      let displayName = refSource || '';
      if (!displayName && refLink) {
        try { displayName = new URL(refLink).hostname.replace(/^www\./, ''); } catch (e) { displayName = refLink; }
      }
      if (displayName.length > 20) displayName = displayName.substring(0, 18) + '...';

      let isUser = false;
      if (siteUrl) {
        const normalizedRef = (refLink + ' ' + refSource).toLowerCase();
        const normalizedSite = siteUrl.toLowerCase().replace(/^www\./, '');
        isUser = normalizedRef.includes(normalizedSite);
      }

      slots.push({ pos: i + 1, name: displayName, isUser });
    }

    const slotsHTML = slots.map(s => {
      if (s.isUser) {
        return `
          <div style="
            display: flex; align-items: center; gap: 6px;
            padding: 6px 12px; border-radius: 8px;
            background: linear-gradient(135deg, #28a74520, #28a74510);
            border: 2px solid #28a745;
            font-size: 0.82em; font-weight: 700; color: #28a745;
          ">
            <span style="
              background: #28a745; color: white; border-radius: 50%;
              min-width: 22px; height: 22px; display: flex; align-items: center; justify-content: center;
              font-size: 0.78em;
            ">${s.pos}</span>
            <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              <i class="fas fa-check-circle" style="margin-right: 2px;"></i>${escapeHtml(s.name)}
            </span>
          </div>`;
      }
      return `
        <div style="
          display: flex; align-items: center; gap: 6px;
          padding: 6px 12px; border-radius: 8px;
          background: #f1f3f5; border: 1px solid #dee2e6;
          font-size: 0.82em; color: #555;
        ">
          <span style="
            background: #6c757d; color: white; border-radius: 50%;
            min-width: 22px; height: 22px; display: flex; align-items: center; justify-content: center;
            font-size: 0.78em;
          ">${s.pos}</span>
          <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(s.name)}</span>
        </div>`;
    }).join('');

    const extraCount = references.length - maxShow;
    const serpPosBadge = serpPosition !== 'unknown'
      ? `<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;background:#6f42c120;color:#6f42c1;font-size:0.72em;font-weight:600;">
           <i class="fas fa-map-pin"></i> AIO position: ${escapeHtml(serpPosition)}
         </span>`
      : '';

    positionMockupHTML = `
      <div>
        <div style="
          display: flex; align-items: center; gap: 6px;
          margin-bottom: 0.5em;
          font-size: 0.82em; font-weight: 600; color: #444;
        ">
          <i class="fas fa-list-ol" style="color: #fd7e14;"></i>
          AI Overview Source Ranking
          ${serpPosBadge}
        </div>
        <div style="
          background: #fafbfc; border-radius: 10px; padding: 10px;
          border: 1px solid #e9ecef;
        ">
          <div style="display: flex; flex-direction: column; gap: 5px;">
            ${slotsHTML}
          </div>
          ${extraCount > 0 ? `<div style="text-align:center;color:#888;font-size:0.75em;margin-top:6px;">+${extraCount} more source${extraCount > 1 ? 's' : ''}</div>` : ''}
        </div>
      </div>
    `;
  }

  // --- Combine all ---
  if (!contentHTML && !sourcesHTML && !positionMockupHTML) return '';

  return `
    <div style="
      margin: 1.5em 0;
      padding: 1.2em;
      background: white;
      border-radius: 12px;
      border: 1px solid #e0e4e8;
      box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    ">
      <h5 style="margin-bottom: 1em; color: #333; font-size: 1.05em; display: flex; align-items: center; gap: 8px;">
        <span style="
          display: flex; align-items: center; justify-content: center;
          width: 30px; height: 30px; border-radius: 8px;
          background: linear-gradient(135deg, #667eea, #764ba2);
        ">
          <i class="fas fa-eye" style="color: white; font-size: 0.8em;"></i>
        </span>
        What Google Shows in AI Overview
      </h5>
      ${contentHTML}
      <div style="display: grid; grid-template-columns: ${references.length > 0 ? '1fr 1fr' : '1fr'}; gap: 1em;">
        ${sourcesHTML}
        ${positionMockupHTML}
      </div>
    </div>
  `;
}

function _createSerpFeaturesDetailHTML(ctr) {
  const features = ctr.serp_features || [];
  if (features.length === 0) return '';

  const absorbedBySerpFeatures = ctr.clicks_absorbed_by_serp_features || 0;
  const impactPct = ctr.serp_features_impact ? (ctr.serp_features_impact * 100).toFixed(0) : '0';

  const pills = features.map(f => `
    <span style="
      display: inline-flex; align-items: center; gap: 4px;
      padding: 3px 10px; border-radius: 12px; font-size: 0.78em;
      background: ${f.color}15; color: ${f.color}; border: 1px solid ${f.color}25;
    ">
      <i class="fas ${f.icon}" style="font-size: 0.85em;"></i>
      ${f.label}
    </span>
  `).join('');

  return `
    <div style="margin-top: 0.8em; padding-top: 0.8em; border-top: 1px solid #dee2e6;">
      <div style="font-size: 0.78em; color: #555; font-weight: 600; margin-bottom: 0.4em;">
        <i class="fas fa-layer-group" style="margin-right: 4px; color: #6f42c1;"></i>
        Other SERP Features Detected
      </div>
      <div style="display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 0.4em;">
        ${pills}
      </div>
      ${absorbedBySerpFeatures > 0 ? `
        <p style="color: #888; font-size: 0.72em; margin: 0.3em 0 0 0;">
          These features reduce expected CTR by ~${impactPct}%, absorbing ≈${absorbedBySerpFeatures} additional clicks beyond AI Overview.
        </p>
      ` : `
        <p style="color: #888; font-size: 0.72em; margin: 0.3em 0 0 0;">
          These features may reduce organic visibility (~${impactPct}% estimated CTR impact).
        </p>
      `}
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

function createModalHTML(result, debugSection, impactSummaryHTML, ctrAnalysisHTML, aioPreviewHTML, elementsListHTML, domainAsSourceHTML) {
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
        ${ctrAnalysisHTML}
        ${aioPreviewHTML}
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