const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const { webcrypto } = require('node:crypto');
const app = fs.readFileSync('static/js/app.js', 'utf8');
const host = fs.readFileSync('static/js/anfitrion.js', 'utf8');
function element() { return { hidden: true, textContent: '', checked: false, value: '', events: {}, addEventListener(t, f) { this.events[t] = f; }, focus() {}, reset() {}, querySelector() { return { value: 'csrf-token' }; } }; }
async function recovery(committed) {
    const stored = new Map(), server = new Map(); let sends = 0;
    async function browser() {
        const nodes = {}; const get = id => nodes[id] ??= element();
        const fields = [{ name: 'nombre', value: 'Persona prueba' }, { name: 'cargo', value: 'Estudiante' }];
        get('attendance-form').querySelectorAll = () => fields;
        get('attendance-form').elements = { nombre: element() };
        const context = { document: { getElementById: get }, crypto: webcrypto, URLSearchParams, Uint8Array,
            window: { location: { search: '?token=sesion' } },
            localStorage: { getItem: k => stored.get(k) || null, setItem: (k, v) => stored.set(k, v), removeItem: k => stored.delete(k) },
            fetch: async (url, options) => {
                if (url.includes('consultar')) {
                    const id = JSON.parse(options.body).registro_token;
                    return { ok: true, json: async () => ({ registrada: server.has(id), estado: 'PENDIENTE_FIRMA' }) };
                }
                if (options) {
                    sends++; const data = JSON.parse(options.body);
                    if (committed || sends > 1) server.set(data.registro_token, data);
                    if (sends === 1) throw Error('Respuesta perdida');
                    return { ok: true, json: async () => ({ registro_token: data.registro_token, estado: 'PENDIENTE_FIRMA' }) };
                }
                return { ok: true, json: async () => ({ nombre: 'Sesión', fecha_inicio: '2026-10-30T20:00:00Z', estado: 'ABIERTA' }) };
            }
        };
        vm.createContext(context); vm.runInContext(app, context); await new Promise(setImmediate);
        return get;
    }
    const first = await browser(); await first('attendance-form').events.submit({ preventDefault() {} });
    const saved = JSON.parse(stored.get('asistencia_pendiente_sesion')); assert.ok(saved.registro_token);
    const second = await browser();
    if (committed) { assert.equal(second('attendance-form').hidden, true); assert.equal(sends, 1); }
    else { assert.equal(second('attendance-form').hidden, false); await second('attendance-form').events.submit({ preventDefault() {} }); assert.ok(server.has(saved.registro_token)); }
    assert.equal(server.size, 1); assert.equal(stored.has('asistencia_pendiente_sesion'), false);
}
async function draft() {
    const dialog = { returnValue: '', shown: false, addEventListener(t, cb) { this.callback = cb; }, showModal() { this.shown = true; } };
    const context = { document: { querySelector: () => dialog }, developmentDirty: () => true, signatureHasInk: false };
    vm.createContext(context);
    const start = host.indexOf('async function discardSessionDraft()');
    vm.runInContext(host.slice(start, host.indexOf("window.addEventListener('beforeunload'", start)), context);
    let answer = vm.runInContext('discardSessionDraft()', context); assert.equal(dialog.shown, true);
    dialog.returnValue = 'cancel'; dialog.callback(); assert.equal(await answer, false);
    answer = vm.runInContext('discardSessionDraft()', context); dialog.returnValue = 'discard'; dialog.callback(); assert.equal(await answer, true);
}
(async () => { await recovery(true); await recovery(false); await draft(); console.log('OK: recuperación de envíos y conservación/descarte de borradores.'); })();
