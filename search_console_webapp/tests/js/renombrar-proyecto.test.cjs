/**
 * Renombrar un proyecto en AI Overview y AI Mode envía el nombre que el
 * usuario escribió.
 *
 * La plantilla tiene dos campos de nombre: el visible de Settings
 * (#modalProjectName) y uno de un bloque antiguo oculto (#projectNameEdit)
 * que se rellena con el nombre actual. Se guardaba el oculto: el servidor
 * recibía el nombre viejo y la app decía «Project updated successfully» sin
 * cambiar nada (oct-2026).
 */
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const APP = path.resolve(__dirname, '..', '..');
const MODULOS = {
  'AI Overview': ['static/js/manual-ai/manual-ai-modals.js', '/manual-ai/api/projects/7'],
  'AI Mode': ['static/js/ai-mode-projects/ai-mode-modals.js', '/ai-mode-projects/api/projects/7'],
};

for (const [panel, [fichero, url]] of Object.entries(MODULOS)) {
  test(`${panel}: guarda el nombre y la descripción de los campos visibles`, async () => {
    const campos = {
      projectNameEdit: { value: 'Nombre viejo' }, // bloque oculto
      modalProjectName: { value: '  Nombre nuevo  ' },
      modalProjectDescription: { value: 'Descripción nueva' },
      projectModalTitle: { textContent: '' },
    };
    const enviado = [];
    globalThis.document = { getElementById: (id) => campos[id] || null };
    globalThis.fetch = async (u, opts) => {
      enviado.push({ u, opts });
      return { json: async () => ({ success: true }) };
    };

    const mod = await import(pathToFileURL(path.join(APP, fichero)).href);
    const avisos = [];
    const ctx = {
      currentModalProject: { id: 7, name: 'Nombre viejo' },
      projects: [{ id: 7, name: 'Nombre viejo' }],
      assertProjectEditable: () => true,
      showProgress() {}, hideProgress() {},
      showSuccess: (m) => avisos.push(['ok', m]),
      showError: (m) => avisos.push(['error', m]),
      loadProjects: async () => {}, populateAnalyticsProjectSelect() {},
    };
    await mod.updateProjectFromModal.call(ctx);

    assert.deepStrictEqual(avisos.filter(([t]) => t === 'error'), []);
    assert.strictEqual(enviado.length, 1);
    assert.strictEqual(enviado[0].u, url);
    assert.strictEqual(enviado[0].opts.method, 'PUT');
    assert.deepStrictEqual(JSON.parse(enviado[0].opts.body), { name: 'Nombre nuevo', description: 'Descripción nueva' });
    assert.strictEqual(ctx.projects[0].name, 'Nombre nuevo');
  });
}
