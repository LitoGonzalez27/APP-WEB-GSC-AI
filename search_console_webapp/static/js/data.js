// data.js - Actualizado para manejar fechas específicas y URLs
export async function fetchData(formData) {
  console.log('📤 Enviando datos con fechas específicas:', [...formData.entries()]);
  
  const resp = await fetch('/get-data', { method: 'POST', body: formData });
  if (!resp.ok) {
    const errorText = await resp.text().catch(() => 'Unknown error');
    throw new Error(`Error al obtener datos del backend: ${resp.status} ${resp.statusText} - ${errorText}`);
  }
  
  const data = await resp.json();
  
  // ✅ NUEVO: Validar estructura de respuesta con períodos
  if (data && data.periods) {
    console.log('📅 Períodos recibidos:', data.periods);
    
    if (data.periods.has_comparison) {
      console.log('📊 Datos incluyen comparación de períodos');
    }
  }
  
  return data;
}

// ✅ NUEVA función para construir resumen basado en períodos específicos
export function buildPeriodSummary(pages, periods) {
  const summary = {};
  
  if (!pages || !Array.isArray(pages)) {
    console.warn('No hay datos de páginas para procesar');
    return summary;
  }
  
  pages.forEach(item => {
    if (!item.Metrics || !Array.isArray(item.Metrics)) {
      console.warn('Página sin métricas válidas:', item);
      return;
    }
    
    item.Metrics.forEach(metric => {
      // Usar el período como clave
      const periodKey = metric.Period || `${metric.StartDate} to ${metric.EndDate}`;
      
      if (!summary[periodKey]) {
        summary[periodKey] = {
          Clicks: 0,
          Impressions: 0,
          PosImprsSum: 0,
          StartDate: metric.StartDate,
          EndDate: metric.EndDate
        };
      }
      
      const s = summary[periodKey];
      s.Clicks += metric.Clicks || 0;
      s.Impressions += metric.Impressions || 0;
      s.PosImprsSum += (metric.Position || 0) * (metric.Impressions || 0);
    });
  });

  // Calcular CTR y Posición media
  Object.keys(summary).forEach(periodKey => {
    const s = summary[periodKey];
    s.CTR = s.Impressions > 0 ? (s.Clicks / s.Impressions) : 0;
    s.Position = s.Impressions > 0 ? (s.PosImprsSum / s.Impressions) : 0;
    
    // Agregar información de duración
    if (s.StartDate && s.EndDate) {
      const start = new Date(s.StartDate);
      const end = new Date(s.EndDate);
      s.Duration = Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1;
    }
  });

  console.log('📊 Resumen de períodos construido:', summary);
  return summary;
}

// ✅ NUEVA función para procesar datos de URLs y estructurarlos para comparación
export function processUrlsForComparison(pages, periods) {
  const urlsData = [];
  
  if (!pages || !Array.isArray(pages)) {
    console.warn('No hay datos de páginas para procesar URLs');
    return urlsData;
  }
  
  pages.forEach(item => {
    const url = item.URL || 'N/A';
    const metrics = item.Metrics || [];
    
    if (metrics.length === 1) {
      // Período único - ✅ CORREGIDO: Datos van a P1 (período actual)
      const metric = metrics[0];
      urlsData.push({
        url: url,
        clicks_p1: metric.Clicks || 0,
        clicks_p2: 0,
        impressions_p1: metric.Impressions || 0,
        impressions_p2: 0,
        ctr_p1: (metric.CTR || 0) * 100,
        ctr_p2: 0,
        position_p1: metric.Position || null,
        position_p2: null,
        delta_clicks_percent: 'New',
        delta_impressions_percent: 'New',
        delta_ctr_percent: 'New',
        delta_position_absolute: 'New',
        period_info: {
          current: {
            start_date: metric.StartDate,
            end_date: metric.EndDate,
            label: metric.Period || `${metric.StartDate} - ${metric.EndDate}`
          }
        }
      });
    } else if (metrics.length >= 2) {
      // Múltiples períodos - ordenar por fecha y usar el último como actual (P1) y el primero como comparativo (P2)
      const sortedMetrics = metrics.sort((a, b) => {
        if (a.StartDate && b.StartDate) {
          return new Date(a.StartDate) - new Date(b.StartDate);
        }
        return 0;
      });
      const p2Metric = sortedMetrics[0]; // Comparativo (más antiguo)
      const p1Metric = sortedMetrics[sortedMetrics.length - 1]; // Actual (más reciente)
      
      // Calcular deltas: P1 sobre P2
      const deltaClicks = calculatePercentageChange(p1Metric.Clicks, p2Metric.Clicks);
      const deltaImpressions = calculatePercentageChange(p1Metric.Impressions, p2Metric.Impressions);
      const deltaCTR = ((p1Metric.CTR || 0) * 100) - ((p2Metric.CTR || 0) * 100);
      const deltaPosition = (p1Metric.Position && p2Metric.Position)
        ? p1Metric.Position - p2Metric.Position
        : (p1Metric.Position ? 'New' : 'Lost');
      
      urlsData.push({
        url: url,
        clicks_p1: p1Metric.Clicks || 0,      // P1 = actual
        clicks_p2: p2Metric.Clicks || 0,      // P2 = comparativo
        impressions_p1: p1Metric.Impressions || 0,
        impressions_p2: p2Metric.Impressions || 0,
        ctr_p1: (p1Metric.CTR || 0) * 100,
        ctr_p2: (p2Metric.CTR || 0) * 100,
        position_p1: p1Metric.Position || null,
        position_p2: p2Metric.Position || null,
        delta_clicks_percent: deltaClicks,
        delta_impressions_percent: deltaImpressions,
        delta_ctr_percent: deltaCTR,
        delta_position_absolute: deltaPosition,
        period_info: {
          comparison: {
            start_date: p2Metric.StartDate,
            end_date: p2Metric.EndDate,
            label: p2Metric.Period || `${p2Metric.StartDate} - ${p2Metric.EndDate}`
          },
          current: {
            start_date: p1Metric.StartDate,
            end_date: p1Metric.EndDate,
            label: p1Metric.Period || `${p1Metric.StartDate} - ${p1Metric.EndDate}`
          }
        }
      });
    }
  });
  
  console.log('📋 URLs procesadas para comparación:', urlsData.length);
  return urlsData;
}

// ✅ FUNCIÓN auxiliar para calcular cambio porcentual
function calculatePercentageChange(p1, p2) {
  if (p1 === null || p2 === null || typeof p1 === 'undefined' || typeof p2 === 'undefined') {
    return 'N/A';
  }
  if (p2 === 0) {
    if (p1 > 0) return "Infinity";
    if (p1 < 0) return "-Infinity";
    return 0;
  }
  return ((p1 / p2) - 1) * 100;
}

// ✅ NUEVA función para determinar si hay comparación en los datos de URLs
export function hasUrlComparison(pages) {
  if (!pages || !Array.isArray(pages)) return false;
  
  return pages.some(item => 
    item.Metrics && Array.isArray(item.Metrics) && item.Metrics.length > 1
  );
}

// ✅ MANTENER buildMonthlySummary para compatibilidad (deprecado)
export function buildMonthlySummary(pages) {
  console.warn('⚠️ buildMonthlySummary está deprecado, usa buildPeriodSummary');
  
  // Convertir a formato de períodos para mantener compatibilidad
  const summary = {};
  
  pages.forEach(item => {
    item.Metrics.forEach(metric => {
      const m = metric.Month || metric.Period || 'Unknown Period';
      if (!summary[m]) {
        summary[m] = {
          Clicks: 0,
          Impressions: 0,
          PosImprsSum: 0
        };
      }
      const s = summary[m];
      s.Clicks += metric.Clicks || 0;
      s.Impressions += metric.Impressions || 0;
      s.PosImprsSum += (metric.Position || 0) * (metric.Impressions || 0);
    });
  });

  Object.keys(summary).forEach(m => {
    const s = summary[m];
    s.CTR = s.Impressions > 0 ? (s.Clicks / s.Impressions) : 0;
    s.Position = s.Impressions > 0 ? (s.PosImprsSum / s.Impressions) : 0;
  });

  return summary;
}

// ✅ NUEVA función utilitaria para formatear fechas
export function formatDateRange(startDate, endDate) {
  if (!startDate || !endDate) return 'Período no definido';
  
  const start = new Date(startDate);
  const end = new Date(endDate);
  
  const options = { 
    day: '2-digit', 
    month: '2-digit', 
    year: 'numeric' 
  };
  
  if (startDate === endDate) {
    return start.toLocaleDateString('es-ES', options);
  }
  
  return `${start.toLocaleDateString('es-ES', options)} - ${end.toLocaleDateString('es-ES', options)}`;
}

// ✅ NUEVA función para validar datos de períodos
export function validatePeriodData(data) {
  const errors = [];
  
  if (!data) {
    errors.push('No data to validate');
    return { isValid: false, errors };
  }
  
  if (!data.periods) {
    errors.push('Missing period information');
  } else {
    if (!data.periods.current || !data.periods.current.start_date || !data.periods.current.end_date) {
      errors.push('Main period incomplete');
    }
    
    if (data.periods.has_comparison && (!data.periods.comparison || !data.periods.comparison.start_date)) {
      errors.push('Comparison period incomplete');
    }
  }
  
  if (!data.pages || !Array.isArray(data.pages)) {
    errors.push('Invalid page data');
  }
  
  return {
    isValid: errors.length === 0,
    errors,
    warnings: []
  };
}

// ✅ NUEVA función para generar estadísticas de URLs
export function generateUrlsStats(urlsData) {
  const stats = {
    total_urls: urlsData.length,
    with_clicks: urlsData.filter(url => (url.clicks_p2 || 0) > 0).length,
    with_improvements: urlsData.filter(url => 
      typeof url.delta_clicks_percent === 'number' && url.delta_clicks_percent > 0
    ).length,
    with_declines: urlsData.filter(url => 
      typeof url.delta_clicks_percent === 'number' && url.delta_clicks_percent < 0
    ).length,
    new_urls: urlsData.filter(url => url.delta_clicks_percent === 'New').length,
    lost_urls: urlsData.filter(url => url.delta_clicks_percent === 'Lost').length
  };
  
  console.log('📊 Estadísticas de URLs:', stats);
  return stats;
}

// ✅ NUEVA función para detectar URLs solapadas
export function detectOverlappingURLs(urls, matchType) {
  const overlaps = [];
  
  if (matchType === 'equals') {
    // En modo equals no hay solapamiento posible ya que cada URL es exacta
    return overlaps;
  }
  
  if (matchType === 'contains') {
    // Detectar URLs que pueden ser subconjuntos de otras
    for (let i = 0; i < urls.length; i++) {
      for (let j = i + 1; j < urls.length; j++) {
        const url1 = urls[i].toLowerCase();
        const url2 = urls[j].toLowerCase();
        
        if (url1.includes(url2)) {
          overlaps.push({
            warning: `"${urls[j]}" está contenida en "${urls[i]}" - esto puede causar datos duplicados`,
            urls: [urls[i], urls[j]]
          });
        } else if (url2.includes(url1)) {
          overlaps.push({
            warning: `"${urls[i]}" está contenida en "${urls[j]}" - esto puede causar datos duplicados`,
            urls: [urls[i], urls[j]]
          });
        }
      }
    }
  }
  
  if (matchType === 'notContains') {
    // Para notContains, advertir si hay patrones muy genéricos que podrían excluir demasiado
    const genericPatterns = ['/', 'http', 'www', '.com', '.es', '.org'];
    
    urls.forEach(url => {
      const urlLower = url.toLowerCase();
      if (genericPatterns.some(pattern => urlLower === pattern)) {
        overlaps.push({
          warning: `El patrón "${url}" es muy genérico y podría excluir muchas páginas`,
          urls: [url]
        });
      }
    });
    
    // Advertir sobre URLs que podrían excluir URLs principales del sitio
    urls.forEach(url => {
      if (url.includes('/')) {
        overlaps.push({
          warning: `Usar "Not Contains" con "${url}" excluirá todas las páginas que contengan este texto`,
          urls: [url]
        });
      }
    });
  }
  
  return overlaps;
}

// ✅ NUEVA función para validar integridad de datos
export function validateDataIntegrity(data) {
  const issues = [];
  
  if (!data) {
    issues.push('No data provided');
    return issues;
  }
  
  // Validar estructura básica
  if (!data.pages && !data.keywords && !data.summary) {
    issues.push('Data structure is incomplete - missing pages, keywords, and summary');
  }
  
  // Validar páginas
  if (data.pages) {
    if (!Array.isArray(data.pages)) {
      issues.push('Pages data should be an array');
    } else {
      data.pages.forEach((page, index) => {
        if (!page.URL) {
          issues.push(`Page ${index + 1} is missing URL`);
        }
        if (!page.Metrics || !Array.isArray(page.Metrics)) {
          issues.push(`Page ${index + 1} is missing metrics data`);
        } else {
          page.Metrics.forEach((metric, metricIndex) => {
            if (typeof metric.Clicks === 'undefined' || typeof metric.Impressions === 'undefined') {
              issues.push(`Page ${index + 1}, metric ${metricIndex + 1} is missing clicks or impressions`);
            }
            if (metric.Clicks < 0 || metric.Impressions < 0) {
              issues.push(`Page ${index + 1}, metric ${metricIndex + 1} has negative values`);
            }
          });
        }
      });
    }
  }
  
  // Validar keywords si están presentes
  if (data.keywords) {
    if (!Array.isArray(data.keywords)) {
      issues.push('Keywords data should be an array');
    } else if (data.keywords.length === 0) {
      issues.push('No keyword data found');
    }
  }
  
  // Validar datos de períodos
  if (data.periods) {
    if (!data.periods.current) {
      issues.push('Missing current period information');
    }
    if (data.periods.has_comparison && !data.periods.comparison) {
      issues.push('Comparison period is indicated but missing data');
    }
  }
  
  return issues;
}