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
function formData() { return Object.fromEntries([...form.querySelectorAll('[data-person-field]')].map(input => [input.name, input.value.trim()])); }
function fill(values) { for (const input of form.querySelectorAll('[data-person-field]')) input.value = values[input.name] || ''; }
function showRegistered(state) {
    signatureState = state;
    form.hidden = identitySection.hidden = true;
    anotherButton.hidden = !sessionIsOpen;
    signatureNotice.hidden = state === 'FIRMADO' || !sessionIsOpen;
    message.textContent = state === 'FIRMADO' ? 'Tu asistencia está registrada y firmada.' : sessionIsOpen ? 'Tus datos están registrados. Dirígete a la tablet del anfitrión para firmar.' : 'Tu registro quedó pendiente de firma, pero la sesión ya está cerrada. Consulta al anfitrión.';
}
function showForm() {
    identitySection.hidden = true; form.hidden = false;
    message.textContent = 'Revisa tus datos. La firma se realiza en la tablet del anfitrión.';
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
    if (!sessionIsOpen) return;
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
        eventDate.textContent = data.fecha_inicio ? `Inicio: ${new Date(data.fecha_inicio).toLocaleString('es-CL', {timeZone:'America/Santiago'})}` : '';
        sessionIsOpen = data.estado === 'ABIERTA';
        const pending = parse(read(pendingKey));
        const identifier = read(successKey) || pending?.registro_token;
        if (identifier) {
            const check = await fetch(`/api/sesiones/${encodeURIComponent(token)}/asistencias/consultar/?registro_token=${encodeURIComponent(identifier)}`);
            if (!check.ok) throw new Error('No se pudo comprobar el envío anterior. Recarga antes de volver a registrarte.');
            const result = await check.json();
            if (result.registrada) { write(successKey, identifier); remove(pendingKey); showRegistered(result.estado); return; }
            remove(successKey);
        }
        if (!sessionIsOpen) { message.textContent = 'Esta sesión está cerrada y no admite nuevos registros ni firmas.'; return; }
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
