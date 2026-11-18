const form = document.getElementById('attendance-form');
const title = document.getElementById('attendance-title');
const eventDate = document.getElementById('event-date');
const message = document.getElementById('form-message');
const submitButton = document.getElementById('submit-button');
const anotherButton = document.getElementById('register-another');
const signatureNotice = document.getElementById('signature-notice');
const identitySection = document.getElementById('remembered-person');
const token = new URLSearchParams(window.location.search).get('token');
const pendingKey = `asistencia_pendiente_${token}`;
const successKey = `asistencia_envio_${token}`;
const profileKey = 'asistencia_perfil_v1';
let sessionIsOpen = false;
let submissionToken = null;
let signatureState = null;
let recoveredProfile = null;
let entregaEpp = false;
let firmaTipo = 'asistencia';
let firmando = false;
const canvas = document.getElementById('participant-signature');
const firmaBoton = document.getElementById('submit-participant-signature');
const limpiarFirma = document.getElementById('clear-participant-signature');
const devolucionBoton = document.getElementById('start-return');
const firmaControles = document.getElementById('signature-controls');
const firmaTitulo = document.getElementById('signature-label');
let tieneTrazo = false;
let puntero = null;
const ctx = canvas?.getContext?.('2d');
function limpiarLienzo() {
    ctx?.clearRect(0, 0, canvas.width, canvas.height);
    tieneTrazo = false;
}
function coordenadas(event) {
    const r = canvas.getBoundingClientRect();
    return [(event.clientX-r.left)*canvas.width/r.width, (event.clientY-r.top)*canvas.height/r.height];
}
canvas?.addEventListener('pointerdown', event => {
    if (firmando || puntero !== null) return;
    puntero = event.pointerId;
    canvas.setPointerCapture(puntero);
    ctx.beginPath();
    ctx.moveTo(...coordenadas(event));
});
canvas?.addEventListener('pointermove', event => {
    if (event.pointerId !== puntero) return;
    ctx.lineWidth = 4;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.lineTo(...coordenadas(event));
    ctx.stroke();
    tieneTrazo = true;
});
for (const nombre of ['pointerup', 'pointercancel', 'lostpointercapture']) {
    canvas?.addEventListener(nombre, event => {
        if (event.pointerId === puntero) puntero = null;
    });
}
limpiarFirma?.addEventListener('click', limpiarLienzo);
function read(key) { try { return localStorage.getItem(key); } catch { return null; } }
function write(key, value) { try { localStorage.setItem(key, value); return true; } catch { return false; } }
function remove(key) { try { localStorage.removeItem(key); } catch {} }
function parse(value) { try { return JSON.parse(value); } catch { return null; } }
function newToken() {
    const bytes = new Uint8Array(16); crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    const hex = [...bytes].map(b => b.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
const rutInput = form.querySelector('#attendee-rut');

function revisarRut(formatear = false) {
    if (!rutInput) return true;
    const compacto = rutInput.value.replace(/[.-]/g, '').toUpperCase();
    rutInput.setCustomValidity('');
    if (!rutInput.value) return true;
    if (!/^[0-9]{1,9}[0-9K]$/.test(compacto) || !Number(compacto.slice(0, -1))) {
        rutInput.setCustomValidity('Ingresa un RUT con su dígito verificador.');
        return false;
    }
    const cuerpo = compacto.slice(0, -1);
    let suma = 0;
    for (let i = cuerpo.length - 1; i >= 0; i--) {
        suma += Number(cuerpo[i]) * (2 + (cuerpo.length - 1 - i) % 6);
    }
    const esperado = '0123456789K'[(11 - suma % 11) % 11];
    if (compacto.at(-1) !== esperado) {
        rutInput.setCustomValidity('El dígito verificador del RUT no es válido.');
        return false;
    }
    if (formatear) {
        rutInput.value = cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + '-' + esperado;
    }
    return true;
}

rutInput?.addEventListener('beforeinput', event => {
    if (event.data && /[^0-9kK.\-]/.test(event.data) && event.inputType === 'insertText') {
        event.preventDefault();
    }
});
rutInput?.addEventListener('input', () => {
    const limpiar = value => value.replace(/[^0-9kK.\-]/g, '').toUpperCase();
    const cursor = rutInput.selectionStart;
    const original = rutInput.value;
    const limpio = limpiar(original);
    if (original !== limpio) {
        rutInput.value = limpio;
        const posicion = limpiar(original.slice(0, cursor)).length;
        rutInput.setSelectionRange(posicion, posicion);
    }
    revisarRut();
});
rutInput?.addEventListener('blur', () => revisarRut(true));
form.addEventListener('reset', () => rutInput?.setCustomValidity(''));

function formData() { return Object.fromEntries([...form.querySelectorAll('[data-person-field]')].map(input => [input.name, input.value.trim()])); }
function fill(values) { for (const input of form.querySelectorAll('[data-person-field]')) input.value = values[input.name] || ''; }
function showRegistered(state, devolucionFirmada = false) {
    signatureState = state;
    form.hidden = identitySection.hidden = true;
    anotherButton.hidden = !sessionIsOpen;
    const firmada = state === 'FIRMADO';
    const puedeDevolver = firmada && entregaEpp && !devolucionFirmada && sessionIsOpen;
    signatureNotice.hidden = !sessionIsOpen || (firmada && !puedeDevolver);
    if (firmaControles) {
        firmaTipo = 'asistencia';
        limpiarLienzo();
        firmaControles.hidden = firmada;
        devolucionBoton.hidden = !puedeDevolver;
        firmaTitulo.textContent = puedeDevolver ? 'Devolución de EPP' : entregaEpp ? 'Firma de recepción de EPP' : 'Firma de asistencia';
    }
    message.textContent = firmada
        ? devolucionFirmada ? 'Recepción y devolución firmadas.' : entregaEpp ? 'La recepción de EPP quedó firmada.' : 'Tu asistencia está registrada y firmada.'
        : sessionIsOpen ? 'Tus datos están registrados. Firma desde este dispositivo.' : 'Tu registro quedó pendiente de firma y la sesión ya está cerrada.';
}
devolucionBoton?.addEventListener('click', () => {
    firmaTipo = 'devolucion';
    limpiarLienzo();
    devolucionBoton.hidden = true;
    firmaControles.hidden = false;
});
firmaBoton?.addEventListener('click', async () => {
    if (firmando || !submissionToken || !sessionIsOpen) return;
    if (!tieneTrazo) { message.textContent = 'Dibuja tu firma antes de confirmar.'; return; }
    const tipo = firmaTipo;
    firmando = firmaBoton.disabled = limpiarFirma.disabled = anotherButton.disabled = true;
    try {
        const response = await fetch(`/api/sesiones/${encodeURIComponent(token)}/asistencias/firma/`, {
            method: 'POST',
            headers: {'Content-Type':'application/json', 'X-CSRFToken':form.querySelector('[name="csrfmiddlewaretoken"]').value},
            body: JSON.stringify({registro_token:submissionToken, tipo, firma:canvas.toDataURL('image/png')}),
        });
        if (response.status === 403) throw new Error('Recarga la página para recuperar tu registro.');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo guardar la firma.');
        showRegistered(data.estado, data.devolucion_firmada);
    } catch (error) {
        message.textContent = error.message;
    } finally {
        firmando = firmaBoton.disabled = limpiarFirma.disabled = anotherButton.disabled = false;
    }
});
function showForm() {
    identitySection.hidden = true; form.hidden = false;
    message.textContent = 'Revisa tus datos. A continuación podrás firmar desde este dispositivo.';
}
function showIdentity(profile) {
    recoveredProfile = profile;
    const names = String(profile.nombre || '').trim().split(/\s+/);
    const visibleName = names.length > 1 ? `${names[0]} ${names[Math.floor(names.length / 2)]}` : names[0];
    const email = String(profile.correo || '');
    const [local, domain] = email.split('@');
    document.getElementById('remembered-name').textContent = visibleName || 'Persona recordada';
    document.getElementById('remembered-email').textContent = domain ? `${local.slice(0,1)}***@${domain.slice(0,1)}***` : '';
    identitySection.hidden = false; form.hidden = true;
    message.textContent = 'Confirma si deseas reutilizar tus datos en esta actividad.';
}
document.getElementById('use-profile').addEventListener('click', () => {
    fill(recoveredProfile || {}); document.getElementById('remember-profile').checked = true; showForm();
});
document.getElementById('different-person').addEventListener('click', () => { form.reset(); showForm(); });
document.getElementById('forget-profile').addEventListener('click', () => {
    remove(profileKey); recoveredProfile = null; form.reset(); showForm(); message.textContent = 'Los datos recordados se borraron de este navegador.';
});
anotherButton.addEventListener('click', () => {
    if (!sessionIsOpen || firmando) return;
    remove(successKey); remove(pendingKey); remove(`asistencia_rut_${token}`);
    submissionToken = signatureState = null;
    form.reset(); anotherButton.hidden = signatureNotice.hidden = true;
    showForm(); form.elements.nombre.focus();
});
async function loadSession() {
    if (!token) { title.textContent = 'Accede mediante el QR de una actividad'; message.textContent = 'Solicita el código al anfitrión.'; return; }
    try {
        const response = await fetch(`/api/sesiones/${encodeURIComponent(token)}/`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo cargar la actividad.');
        title.textContent = data.nombre;
        eventDate.textContent = data.estado === 'PROGRAMADA' && data.fecha_programada ? `Programada: ${new Date(data.fecha_programada).toLocaleString('es-CL', {timeZone:'America/Santiago'})}` : data.fecha_inicio ? `Inicio: ${new Date(data.fecha_inicio).toLocaleString('es-CL', {timeZone:'America/Santiago'})}` : '';
        sessionIsOpen = data.estado === 'ABIERTA';
        entregaEpp = Boolean(data.entrega_epp);
        const pending = parse(read(pendingKey));
        const identifier = read(successKey) || pending?.registro_token;
        if (identifier) {
            const check = await fetch(`/api/sesiones/${encodeURIComponent(token)}/asistencias/consultar/`, {
                method: 'POST',
                headers: {'Content-Type':'application/json', 'X-CSRFToken':form.querySelector('[name="csrfmiddlewaretoken"]').value},
                body: JSON.stringify({registro_token:identifier}),
            });
            if (!check.ok) throw new Error('No se pudo comprobar el envío anterior. Recarga antes de volver a registrarte.');
            const result = await check.json();
            if (result.registrada) {
                submissionToken = identifier;
                write(successKey, identifier);
                remove(pendingKey);
                showRegistered(result.estado, result.devolucion_firmada);
                return;
            }
            remove(successKey);
        }
        if (!sessionIsOpen) { message.textContent = data.estado === 'PROGRAMADA' ? 'Esta actividad está programada. El registro se habilitará cuando el anfitrión la inicie.' : 'Esta sesión está cerrada y no admite nuevos registros ni firmas.'; return; }
        if (pending?.datos && pending.registro_token) {
            submissionToken = pending.registro_token; fill(pending.datos); showForm();
            message.textContent = 'Se recuperó un envío pendiente. Puedes reintentarlo sin duplicar tu registro.';
            return;
        }
        const profile = parse(read(profileKey));
        if (profile?.nombre) showIdentity(profile); else showForm();
    } catch (error) { message.textContent = error.message; form.hidden = true; }
}
form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!token || !sessionIsOpen) return;
    if (!revisarRut(true)) {
        rutInput.reportValidity();
        return;
    }
    const datos = formData();
    const previous = parse(read(pendingKey));
    submissionToken = previous?.registro_token && JSON.stringify(previous.datos) === JSON.stringify(datos) ? previous.registro_token : (submissionToken || newToken());
    if (previous?.datos && JSON.stringify(previous.datos) !== JSON.stringify(datos)) submissionToken = newToken();
    // Guardar antes de transmitir permite recuperar un envío cuya respuesta se perdió.
    const persisted = write(pendingKey, JSON.stringify({registro_token: submissionToken, datos}));
    submitButton.disabled = true; message.textContent = 'Registrando asistencia…';
    try {
        const response = await fetch(`/api/sesiones/${encodeURIComponent(token)}/asistencias/`, {
            method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken':form.querySelector('[name="csrfmiddlewaretoken"]').value},
            body:JSON.stringify({...datos, registro_token:submissionToken})
        });
        if (response.status === 403) throw new Error('El formulario venció. Recarga para recuperar el envío pendiente.');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo registrar.');
        write(successKey, data.registro_token); remove(pendingKey);
        if (document.getElementById('remember-profile').checked) write(profileKey, JSON.stringify(datos));
        showRegistered(data.estado); form.reset();
    } catch (error) {
        message.textContent = `${error.message} ${persisted ? 'Tu envío está conservado para reintentarlo.' : 'Este navegador no permite conservar el envío. Evita recargar hasta comprobar con el anfitrión si se registró.'}`;
    } finally { submitButton.disabled = false; }
});
loadSession();
