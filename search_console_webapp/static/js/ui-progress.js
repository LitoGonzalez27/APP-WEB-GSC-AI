// ui-progress.js
let stepsCache = [];
let fakeTimer = null;
let thresholds = [];
let currentStep = 0;

/**
 * Obtiene porcentaje de cada bolita en la barra
 */
function computeThresholds() {
  const bar = document.getElementById('progressBar');
  const miles = document.querySelectorAll('.milestone');
  if (!bar || !miles.length) return [];
  const { left, width } = bar.getBoundingClientRect();
  return Array.from(miles).map(m => {
    const { left: ml, width: mw } = m.getBoundingClientRect();
    return ((ml + mw/2 - left) / width) * 100;
  });
}

/**
 * Arranca el progreso falso hasta 90% y gestiona hitos
 */
export function showProgress(steps) {
  stepsCache = steps;
  currentStep = 0;
  const modal = document.getElementById('progressModal');
  const fill = document.getElementById('progressFill');
  const bubble = document.getElementById('progressBubble');
  const miles = document.querySelectorAll('.milestone');
  if (!modal || !fill || !bubble || !miles.length) return;

  clearTimeout(fakeTimer);
  fill.style.transition = 'width 0.4s ease-out';  // velocidad moderada
  fill.style.width = '0%';
  miles.forEach(m => m.classList.remove('active'));
  bubble.classList.remove('show', 'pulse');

  modal.classList.add('show');
  document.body.classList.add('modal-open');
  thresholds = computeThresholds();

  // Activar la primera bolita inmediatamente
  miles[0].classList.add('active');
  bubble.textContent = stepsCache[0];
  bubble.classList.add('show');

  (function step() {
    let pct = parseFloat(fill.style.width) || 0;
    let incr;
    let delay;
    if (pct < 25) {
      incr = Math.random() * 0.8 + 0.5;    // 0.5% a 1.3%
      delay = Math.random() * 150 + 150;    // 150ms a 300ms
    } else if (pct < 65) {
      incr = Math.random() * 0.6 + 0.4;    // 0.4% a 1.0%
      delay = Math.random() * 200 + 200;   // 200ms a 400ms
    } else if (pct < 85) {
      incr = Math.random() * 0.7 + 0.5;    // 0.5% a 1.2%
      delay = Math.random() * 180 + 180;   // 180ms a 360ms
    } else {
      incr = Math.random() * 0.5 + 0.3;    // 0.3% a 0.8%
      delay = Math.random() * 150 + 150;   // 150ms a 300ms
    }
    const next = Math.min(pct + incr, 90);
    fill.style.width = `${next}%`;

    // Actualizar bolitas y mensajes basado en el progreso
    for (let i = 0; i < thresholds.length; i++) {
      if (next >= thresholds[i] && currentStep < i + 1) {
        currentStep = i + 1;
        bubble.textContent = stepsCache[i];
        bubble.classList.add('show');
        // Activar todas las bolitas hasta el paso actual
        miles.forEach((m, idx) => {
          if (idx <= i) {
            m.classList.add('active');
          }
        });
        break;
      }
    }

    if (next < 90) fakeTimer = setTimeout(step, delay);
  })();
}

/**
 * Completa al 100% con pausas en 90% y 95%
 */
export function completeProgress() {
  const modal = document.getElementById('progressModal');
  const fill = document.getElementById('progressFill');
  const bubble = document.getElementById('progressBubble');
  const miles = document.querySelectorAll('.milestone');
  if (!modal || !fill || !bubble) return;

  clearTimeout(fakeTimer);
  bubble.textContent = 'Almost there...'; 
  bubble.classList.add('show');
  fill.style.transition = 'width 0.5s ease-in-out';
  
  setTimeout(() => {
    fill.style.width = '95%';
    bubble.textContent = 'So close...';
    // Activar todas las bolitas excepto la última
    miles.forEach((m, idx) => {
      if (idx < miles.length - 1) {
        m.classList.add('active');
      }
    });
  }, 600);
  
  setTimeout(() => {
    fill.style.width = '100%';
    bubble.textContent = 'Done!';
    // Activar la última bolita
    miles.forEach(m => m.classList.add('active'));
  }, 1400);
  
  setTimeout(() => {
    modal.classList.remove('show');
    document.body.classList.remove('modal-open');
    fill.style.transition = 'width 0.3s ease-out';
    fill.style.width = '0%';
    bubble.classList.remove('show');
    bubble.textContent = '';
    miles.forEach(m => m.classList.remove('active'));
  }, 2200);
}