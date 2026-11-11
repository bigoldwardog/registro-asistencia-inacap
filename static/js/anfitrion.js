let signatureSaving = false;
let currentSessionData = null;
let developmentBaseline = {};
let signatureHasInk = false;
let currentStartTime = null;

const sessionState = {
    currentSessionId: null,
    isOpen: false,
    attendees: []
};


let selectedAttendee = null;
let signatureMode = "recepcion";
let isDrawing = false;

const sessionQr = document.querySelector("#session-qr");

const attendanceList = document.querySelector("#attendance-list");
const attendanceCount = document.querySelector("#attendance-count");
const sessionStatus = document.querySelector("#session-status");

const sessionSelector = document.querySelector("#session-selector");
const sessionTitle = document.querySelector("#selected-session-title");
const sessionDate = document.querySelector(".session-date");

const closeSessionButton = document.querySelector(
    '[data-action="close-session"]'
);

const logoutButton = document.querySelector(
    '[data-action="logout"]'
);

const signatureSection = document.querySelector(
    "#signature-section"
);

const signatureAttendeeName = document.querySelector(
    "#signature-attendee-name"
);

const signatureAttendeeRut = document.querySelector(
    "#signature-attendee-rut"
);

const signaturePad = document.querySelector(
    "#signature-pad"
);

const clearSignatureButton = document.querySelector(
    "#clear-signature"
);

const confirmSignatureButton = document.querySelector(
    "#confirm-signature"
);

const signatureContext = signaturePad.getContext("2d");


async function loadAttendanceList() {
    if (!sessionState.currentSessionId) {
        resetSessionView();
        return;
    }

    const requestedSessionId = sessionState.currentSessionId;
    try {
        const response = await apiFetch(
            `/api/sesiones/${requestedSessionId}/asistencias/lista/`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "No se pudieron cargar las asistencias."
            );
        }

        if (requestedSessionId !== sessionState.currentSessionId) return;

        sessionState.isOpen = data.sesion.estado === "ABIERTA";
        sessionState.esEpp = Boolean(data.sesion.es_epp);
        sessionState.esPanol = Boolean(data.sesion.es_panol);
        if (!sessionState.isOpen) {
            signatureSection.hidden = true;
            selectedAttendee = null;
        }
        const selectedOption = sessionSelector.selectedOptions[0];
        if (selectedOption) selectedOption.textContent = `${data.sesion.nombre} — ${data.sesion.estado}`;

        sessionState.attendees = data.asistencias.map((item) => ({
            id: item.id,
            name: item.nombre,
            rut: item.rut,
            cargo: item.cargo,
            returned: item.devolucion_firmada,
            returnedAt: item.fecha_firma_devolucion,
            teacherSigned: item.docente_firmado,
            hasSignature: item.tiene_firma,
            status: item.estado
        }));

        sessionStatus.textContent = sessionState.isOpen
            ? "Sesión abierta"
            : "Sesión cerrada";

        closeSessionButton.disabled = !sessionState.isOpen;

        closeSessionButton.textContent = sessionState.isOpen
            ? "Cerrar sesión"
            : "Sesión cerrada";

        renderAttendanceList();

    } catch (error) {
        console.error("Error al cargar las asistencias:", error);

        attendanceList.textContent =
            "No se pudieron cargar las asistencias.";
    }
}

async function loadSessions(preferredSessionId = null) {
    sessionSelector.disabled = true;
    const manageTab = document.getElementById("tab-manage");
    const emptyMessage = document.getElementById("no-sessions");
    emptyMessage.hidden = true;

    try {
        const response = await apiFetch("/api/sesiones/");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "No se pudieron cargar las sesiones."
            );
        }

        // Acepta tanto un arreglo directo como { sesiones: [...] }.
        const sessions = Array.isArray(data)
            ? data
            : data.sesiones;

        if (!Array.isArray(sessions)) {
            console.error("Respuesta inesperada de /api/sesiones/:", data);
            throw new Error(
                "La respuesta del servidor no contiene una lista de sesiones."
            );
        }

        sessionSelector.innerHTML = "";

        manageTab.disabled = sessions.length === 0;
        emptyMessage.hidden = !manageTab.disabled;
        if (manageTab.disabled) {
            sessionSelector.add(
                new Option("No hay sesiones disponibles", "")
            );

            resetSessionView();
            activateDashboardTab("new");
            return;
        }

        sessions.forEach((session) => {
            sessionSelector.add(
                new Option(
                    `${session.nombre} — ${session.estado}`,
                    session.id
                )
            );
        });

        const firstOpenSession = sessions.find(
            (session) => session.estado === "ABIERTA"
        );

        const initialSession = sessions.find((item) => Number(item.id) === Number(preferredSessionId)) || firstOpenSession || sessions[0];

        sessionSelector.disabled = false;
        sessionSelector.value = String(initialSession.id);

        sessionSelector.onchange = async () => {
            const selectedId = Number(sessionSelector.value);

            if (selectedId) {
                await selectSession(selectedId, sessions);
            } else {
                resetSessionView();
            }
        };

        await selectSession(initialSession.id, sessions);

    } catch (error) {
        console.error("Error al cargar las sesiones:", error);

        sessionSelector.innerHTML = "";
        sessionSelector.add(
            new Option("Error al cargar las sesiones", "")
        );

        resetSessionView();
        manageTab.disabled = true;
        if (manageTab.getAttribute("aria-selected") === "true") activateDashboardTab("new");
    } finally {
        sessionSelector.disabled =
            sessionSelector.options.length <= 1 &&
            sessionSelector.options[0]?.value === "";
    }
}


async function selectSession(sessionId, sessions) {
    if (signatureSaving) { sessionSelector.value = String(sessionState.currentSessionId); return; }
    if (sessionState.currentSessionId && Number(sessionId) !== Number(sessionState.currentSessionId) && !(await discardSessionDraft())) {
        sessionSelector.value = String(sessionState.currentSessionId);
        return;
    }
    document.querySelector('#session-audit').open = false;
    document.querySelector('#audit-results').replaceChildren();
    signatureHasInk = false;
    sessionState.currentSessionId = sessionId;
    document.querySelector("#download-poster").disabled = !sessionId;
    document.querySelectorAll("[data-export-format]").forEach(button => { button.disabled = !sessionId; });
    sessionState.isOpen = false;
    sessionState.attendees = [];
    selectedAttendee = null;

    signatureSection.hidden = true;

    const session = sessions.find(
        (item) => Number(item.id) === Number(sessionId)
    );

    renderSessionQr(session);

    console.log(
        "QR generado:",
        sessionQr.querySelector("canvas, img") !== null
    );
    
    if (session) {
        sessionTitle.textContent = session.nombre;
        showSessionTimes(session);
        currentSessionData = session;
        renderDevelopment(session);
        renderSessionDetails(session);
    }

    attendanceList.innerHTML = "";
    attendanceCount.textContent = "Cargando asistentes...";
    sessionStatus.textContent = "Cargando sesión...";
    closeSessionButton.disabled = true;

    await loadAttendanceList();
}

function renderSessionQr(session) {
    sessionQr.replaceChildren();
    const link = document.querySelector('#session-link');
    link.parentElement.hidden = !session?.token_qr;
    if (!session?.token_qr) { sessionQr.textContent = 'Selecciona una sesión'; return; }
    const registrationUrl = new URL('/', window.location.origin);
    registrationUrl.searchParams.set('token', session.token_qr);
    link.href = registrationUrl.toString(); link.textContent = 'Abrir formulario del asistente';
    link.title = registrationUrl.toString();
    document.querySelector('#qr-local-warning').hidden = !['localhost','127.0.0.1','[::1]'].includes(location.hostname);
    const image = document.createElement('img'); image.alt = 'QR de acceso al formulario'; image.width = image.height = 220;
    image.src = `/api/sesiones/${session.id}/qr.png`;
    image.addEventListener('error', () => { sessionQr.textContent = 'No se pudo cargar el QR. Usa el enlace o recarga.'; });
    sessionQr.append(image);
}

function resetSessionView() {
    sessionQr.innerHTML = "";
    sessionQr.textContent = "Selecciona una sesión";
    document.querySelector('#session-link').parentElement.hidden = true;
    document.querySelector('#development-section').hidden = true;
    document.querySelector('#session-template-details').replaceChildren();
    developmentBaseline = {}; currentSessionData = null; signatureHasInk = false;

    sessionState.currentSessionId = null;
    document.querySelector("#download-poster").disabled = true;
    document.querySelectorAll("[data-export-format]").forEach(button => { button.disabled = true; });
    sessionState.isOpen = false;
    sessionState.attendees = [];
    selectedAttendee = null;

    sessionTitle.textContent = "No hay una sesión seleccionada";
    sessionDate.textContent = "";
    sessionStatus.textContent = "Selecciona una sesión.";
    attendanceList.innerHTML = "";
    updateAttendanceCount();
    closeSessionButton.disabled = true;
    closeSessionButton.textContent = "Cerrar sesión";
    signatureSection.hidden = true;
}

function renderAttendanceList() {
    attendanceList.innerHTML = "";

    sessionState.attendees.forEach((attendee) => {
        const article = document.createElement("article");
        article.className = "attendance-item";

        const info = document.createElement("div");
        info.className = "attendance-info";

        const name = document.createElement("strong");
        name.textContent = attendee.name;

        const rut = document.createElement("span");
        rut.textContent = [attendee.rut, attendee.cargo].filter(Boolean).join(" · ");

        info.appendChild(name);
        info.appendChild(rut);

        const status = document.createElement("span");
        status.className =
            `attendance-state ${getStatusClass(attendee.status)}`;
        status.textContent = getStatusText(attendee.status);

        article.appendChild(info);
        article.appendChild(status);
        if (sessionState.esEpp) {
            status.textContent = attendee.status === "FIRMADO" ? "Recepción firmada" : getStatusText(attendee.status);
            if (attendee.returned) {
                const returned = document.createElement("span"); returned.className = "return-confirmed";
                returned.textContent = "Devolución firmada";
                returned.title = new Date(attendee.returnedAt).toLocaleString("es-CL", {timeZone: "America/Santiago"});
                article.append(returned);
            } else if (attendee.status === "FIRMADO") {
                const pending = document.createElement("span");
                pending.textContent = "Devolución pendiente";
                article.append(pending);
            }
        }

        if (sessionState.esPanol && attendee.status === 'FIRMADO') {
            if (attendee.teacherSigned) {
                const signed = document.createElement('span'); signed.textContent = 'Docente firmado'; article.append(signed);
            } else if (sessionState.isOpen) {
                const sign = document.createElement('button'); sign.type = 'button'; sign.textContent = 'Firma docente';
                sign.addEventListener('click', () => selectAttendee(attendee.id, 'docente')); article.append(sign);
            }
        }
        if (attendee.hasSignature) addSignatureLink(article, attendee, 'recepcion', 'Ver firma');
        if (attendee.returned) addSignatureLink(article, attendee, 'devolucion', 'Ver devolución');
        if (attendee.teacherSigned) addSignatureLink(article, attendee, 'docente', 'Ver firma docente');
        attendanceList.appendChild(article);
    });

    if (sessionState.attendees.length === 0) {
        const empty = document.createElement("li"); empty.className = "empty-attendance";
        empty.textContent = sessionState.isOpen ? "Los participantes aparecerán aquí cuando envíen el formulario del QR." : "Esta sesión no tiene participantes registrados.";
        attendanceList.append(empty);
    }
    updateAttendanceCount();
}


function updateAttendanceCount() {

    const count = sessionState.attendees.length;
    document.querySelector("#metric-total").textContent = count;
    document.querySelector("#metric-signed").textContent = sessionState.attendees.filter((item) => item.status === "FIRMADO").length;
    document.querySelector("#metric-pending").textContent = sessionState.attendees.filter((item) => item.status === "PENDIENTE_FIRMA").length;

    attendanceCount.textContent =
        `${count} ${count === 1 ? "asistente" : "asistentes"}`;
}


function getStatusClass(status) {

    switch (status) {

        case "FIRMADO":
            return "signed";

        case "PENDIENTE_FIRMA":
            return "pending";

        default:
            return "";
    }
}


function getStatusText(status) {

    switch (status) {

        case "FIRMADO":
            return "Firmado";

        case "PENDIENTE_FIRMA":
            return "Pendiente de firma";

        default:
            return "Estado desconocido";
    }
}


async function selectAttendee(attendeeId, mode = "recepcion") {
    if (signatureSaving) return;
    if (!sessionState.isOpen) {
        return;
    }

    const attendee = sessionState.attendees.find(
        (item) => item.id === attendeeId
    );

    if (!attendee) {
        return;
    }

    if (mode === "devolucion") {
        if (!sessionState.esEpp || attendee.status !== "FIRMADO" || attendee.returned) return;
    } else if (mode === "docente") {
        if (!sessionState.esPanol || attendee.status !== "FIRMADO" || attendee.teacherSigned) return;
    } else if (attendee.status !== "PENDIENTE_FIRMA") return;
    if (signatureHasInk && !(await askDiscardDraft())) return;
    signatureMode = mode;
    document.querySelector("#signature-title").textContent = mode === "devolucion" ? "Firma de devolución de EPP" : (sessionState.esEpp ? "Firma de recepción de EPP" : "Firma del asistente");
    document.querySelector("#signature-purpose").textContent = mode === "devolucion" ? "Firma para confirmar la devolución de los elementos recibidos. Se guardará por separado con su fecha y hora." : "Firma para confirmar la recepción o asistencia a esta actividad.";
    confirmSignatureButton.textContent = mode === "devolucion" ? "Confirmar devolución" : "Confirmar firma";
    if (mode === 'docente') {
        document.querySelector('#signature-title').textContent = 'Firma del docente';
        document.querySelector('#signature-purpose').textContent = 'El docente firma la solicitud de materiales, por separado de la firma del alumno.';
        confirmSignatureButton.textContent = 'Confirmar firma docente';
    }
    selectedAttendee = attendee;

    signatureAttendeeName.textContent = attendee.name;
    signatureAttendeeRut.textContent = attendee.cargo || attendee.rut || "";

    clearSignature();

    signatureSection.hidden = false;

    signatureSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


function clearSignature() {
    signatureHasInk = false;

    signatureContext.clearRect(
        0,
        0,
        signaturePad.width,
        signaturePad.height
    );
}


function getCanvasPosition(event) {

    const rectangle = signaturePad.getBoundingClientRect();

    return {
        x:
            (event.clientX - rectangle.left) *
            (signaturePad.width / rectangle.width),

        y:
            (event.clientY - rectangle.top) *
            (signaturePad.height / rectangle.height)
    };
}


function startDrawing(event) {
    event.preventDefault();

    signaturePad.setPointerCapture(event.pointerId);

    isDrawing = true;

    const position = getCanvasPosition(event);

    signatureContext.beginPath();
    signatureContext.moveTo(position.x, position.y);
}


function draw(event) {

    if (!isDrawing) {
        return;
    }

    event.preventDefault();

    const position = getCanvasPosition(event);

    signatureContext.lineTo(
        position.x,
        position.y
    );

    signatureContext.stroke();
    signatureHasInk = true;
}


function stopDrawing() {

    if (!isDrawing) {
        return;
    }

    isDrawing = false;

    signatureContext.closePath();
}



async function confirmSignature() {
    if (!selectedAttendee) {
        return;
    }

    const signatureData = signaturePad.toDataURL("image/png");

    if (signatureData === createEmptyCanvasData()) {
        alert("El asistente debe realizar su firma.");
        return;
    }

    signatureSaving = true;
    confirmSignatureButton.disabled = true;

    try {
        const response = await apiFetch(
            signatureMode === "devolucion" ? `/api/asistencias/${selectedAttendee.id}/devolucion/firma/` : signatureMode === "docente" ? `/api/asistencias/${selectedAttendee.id}/docente/firma/` : `/api/asistencias/${selectedAttendee.id}/firma/`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector('[name="csrfmiddlewaretoken"]').value
                },
                body: JSON.stringify({
                    firma: signatureData
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "No se pudo guardar la firma."
            );
        }

        signatureSection.hidden = true;
        selectedAttendee = null;
        clearSignature();

        await loadAttendanceList();

    } catch (error) {
        alert(error.message);
    } finally {
        signatureSaving = false;
        confirmSignatureButton.disabled = false;
    }
}


function createEmptyCanvasData() {

    const temporaryCanvas = document.createElement("canvas");

    temporaryCanvas.width = signaturePad.width;
    temporaryCanvas.height = signaturePad.height;

    return temporaryCanvas.toDataURL("image/png");
}

async function closeSession() {
    if (signatureSaving) return;
    if (!sessionState.isOpen) {
        return;
    }

    const closingSessionId = sessionState.currentSessionId;
    const confirmed = await requestSessionClose();

    if (!confirmed || closingSessionId !== sessionState.currentSessionId || !sessionState.isOpen) {
        return;
    }

    closeSessionButton.disabled = true;

    try {
        const response = await apiFetch(
            `/api/sesiones/${sessionState.currentSessionId}/cerrar/`,
            {
                method: "POST",
                headers: {"X-CSRFToken": document.querySelector('[name="csrfmiddlewaretoken"]').value}
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "No se pudo cerrar la sesión."
            );
        }

        sessionState.isOpen = false;
        showSessionTimes({fecha_inicio: currentStartTime, fecha_cierre: data.fecha_cierre});
        sessionStatus.textContent = "Sesión cerrada";
        closeSessionButton.textContent = "Sesión cerrada";

        await loadAttendanceList();

    } catch (error) {
        alert(error.message);

    } finally {
        closeSessionButton.disabled = !sessionState.isOpen;
    }
}


function logout() {

    alert("Aquí posteriormente se cerrará la sesión del anfitrión.");
}


signaturePad.width = 800;
signaturePad.height = 400;

signatureContext.strokeStyle = "#222";
signatureContext.lineWidth = 3;
signatureContext.lineCap = "round";
signatureContext.lineJoin = "round";

signaturePad.addEventListener(
    "pointerdown",
    startDrawing
);

signaturePad.addEventListener(
    "pointermove",
    draw
);

signaturePad.addEventListener(
    "pointerup",
    stopDrawing
);

signaturePad.addEventListener(
    "pointercancel",
    stopDrawing
);

clearSignatureButton.addEventListener(
    "click",
    clearSignature
);

confirmSignatureButton.addEventListener(
    "click",
    confirmSignature
);

closeSessionButton.addEventListener(
    "click",
    closeSession
);

if (logoutButton) {

    logoutButton.addEventListener(
        "click",
        logout
    );
}


loadSessions();
// Esperar a que termine cada consulta evita acumular peticiones lentas.
async function refreshAttendance() {
    try {
        if (!document.hidden && sessionState.currentSessionId) {
            await loadAttendanceList();
        }
    } finally {
        window.setTimeout(refreshAttendance, 3000);
    }
}
window.setTimeout(refreshAttendance, 3000);

const createForm = document.querySelector("#create-session-form");
const createButton = document.querySelector("#create-session-button");
const createFeedback = document.querySelector("#create-session-feedback");
let availableTemplates = [];
function renderTemplateFields() {
    const template = availableTemplates.find((item) => String(item.id) === document.querySelector("#new-session-template").value);
    document.querySelector("#template-description").textContent = template?.descripcion || "";
    const container = document.querySelector("#template-fields");
    container.replaceChildren();
    for (const field of (template?.campos || []).filter((item) => item.etapa !== "desarrollo")) {
        const group = document.createElement("div"); group.className = "form-group";
        const label = document.createElement("label"); label.htmlFor = `template-${field.nombre}`;
        label.textContent = field.etiqueta + (field.obligatorio ? " *" : " (opcional)");
        const multiline = /temas|acuerdos|desarrollo|descripcion|minuta|objetivo|metodologia|materiales|elementos|responsables|observaciones/.test(field.nombre);
        const input = document.createElement(multiline ? "textarea" : "input");
        input.id = label.htmlFor; input.dataset.templateField = field.nombre;
        input.required = Boolean(field.obligatorio); input.maxLength = 10000;
        if (multiline) input.rows = 3;
        else input.type = ({fecha: "date", hora: "time", email: "email", numero: "number"})[field.tipo] || "text";
        group.append(label, input); container.append(group);
    }
}
document.querySelector("#new-session-template").addEventListener("change", renderTemplateFields);
async function loadSessionOptions() {
    try {
        const response = await apiFetch("/api/configuracion-sesiones/");
        if (!response.ok) throw new Error("No se pudieron cargar las opciones. Recarga la página para reintentar.");
        const data = await response.json();
        availableTemplates = data.plantillas;
        for (const [selector, items] of [["#new-session-template", data.plantillas], ["#new-session-host", data.anfitriones]]) {
            const select = document.querySelector(selector);
            select.replaceChildren(new Option(items.length ? "Selecciona una opción" : "No hay opciones disponibles", ""));
            items.forEach((item) => select.add(new Option(item.nombre, item.id)));
            if (items.length === 1) select.value = String(items[0].id);
        }
        renderTemplateFields();
        createButton.disabled = !data.plantillas.length || !data.anfitriones.length;
        if (createButton.disabled) createFeedback.textContent = "Se necesita al menos una plantilla activa y un anfitrión activo.";
    } catch (error) { createFeedback.textContent = error.message; }
}
createForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (signatureSaving || !(await discardSessionDraft())) return;
    developmentBaseline = developmentValues(); signatureHasInk = false;
    createButton.disabled = true;
    createFeedback.textContent = "Creando sesión...";
    try {
        const response = await apiFetch("/api/sesiones/crear/", {
            method: "POST",
            headers: {"Content-Type": "application/json", "X-CSRFToken": createForm.querySelector('[name="csrfmiddlewaretoken"]').value},
            body: JSON.stringify({
                nombre: document.querySelector("#new-session-name").value,
                plantilla_id: document.querySelector("#new-session-template").value,
                anfitrion_id: document.querySelector("#new-session-host").value,
                campos: Object.fromEntries([...document.querySelectorAll("[data-template-field]")].map((input) => [input.dataset.templateField, input.value]))
            })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "No se pudo crear la sesión.");
        document.querySelector("#new-session-name").value = "";
        await loadSessions(data.id);
        renderTemplateFields();
        createFeedback.textContent = "";
        const dashboardFeedback = document.querySelector("#dashboard-feedback");
        dashboardFeedback.hidden = false;
        dashboardFeedback.textContent = "Sesión creada. Comparte el QR para recibir a los asistentes.";
        activateDashboardTab("manage", true);
        document.querySelector(".dashboard").scrollIntoView({behavior: "smooth", block: "start"});
    } catch (error) { createFeedback.textContent = error.message; }
    finally { createButton.disabled = false; }
});
loadSessionOptions();


function showSessionTimes(session) {
    currentStartTime = session.fecha_inicio;
    const format = (value) => value ? new Date(value).toLocaleString("es-CL", {timeZone: "America/Santiago"}) : "Pendiente de cierre";
    sessionDate.replaceChildren();
    for (const [label, value] of [["Inicio", session.fecha_inicio], ["Término", session.fecha_cierre]]) {
        const item = document.createElement("div"); item.className = "session-time";
        const caption = document.createElement("span"); caption.textContent = label;
        const timestamp = document.createElement("strong"); timestamp.textContent = format(value);
        item.append(caption, timestamp); sessionDate.append(item);
    }
}
function renderDevelopment(session) {
    developmentBaseline = {...(session.campos || {})};
    const section = document.querySelector("#development-section");
    const container = document.querySelector("#development-fields");
    container.replaceChildren();
    document.querySelector("#development-feedback").textContent = "";
    const fields = (Array.isArray(session.campos_definicion) ? session.campos_definicion : []).filter((item) => item.etapa === "desarrollo");
    section.hidden = fields.length === 0;
    for (const field of fields) {
        const group = document.createElement("div"); group.className = "form-group";
        const label = document.createElement("label"); label.htmlFor = `development-${field.nombre}`; label.textContent = field.etiqueta;
        const input = document.createElement(field.tipo === "fecha" ? "input" : "textarea");
        if (field.tipo === "fecha") input.type = "date"; else input.rows = 3;
        input.id = label.htmlFor; input.dataset.developmentField = field.nombre;
        input.value = session.campos?.[field.nombre] || ""; input.maxLength = 10000;
        group.append(label, input); container.append(group);
    }
}
document.querySelector("#development-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const requestedId = sessionState.currentSessionId;
    const button = document.querySelector("#save-development");
    const feedback = document.querySelector("#development-feedback");
    button.disabled = true;
    try {
        const response = await apiFetch(`/api/sesiones/${requestedId}/desarrollo/`, {
            method: "POST",
            headers: {"Content-Type": "application/json", "X-CSRFToken": event.currentTarget.querySelector('[name="csrfmiddlewaretoken"]').value},
            body: JSON.stringify({campos: developmentValues(), base: developmentBaseline})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "No se pudo guardar.");
        if (requestedId !== sessionState.currentSessionId) return;
        feedback.textContent = data.mensaje;
        developmentBaseline = {...data.campos};
        if (currentSessionData) { currentSessionData.campos = data.campos; renderSessionDetails(currentSessionData); }
    } catch (error) { if (requestedId === sessionState.currentSessionId) feedback.textContent = error.message; }
    finally { button.disabled = false; }
});


// Cambiar de pestaña conserva los formularios y la firma en curso.
function activateDashboardTab(name, focus = false) {
    const requested = document.querySelector(`[data-dashboard-tab="${name}"]`);
    if (!requested || requested.disabled) return;
    for (const tab of document.querySelectorAll("[data-dashboard-tab]")) {
        const active = tab.dataset.dashboardTab === name;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        document.getElementById(tab.getAttribute("aria-controls")).hidden = !active;
        if (active && focus) tab.focus();
    }
}
for (const tab of document.querySelectorAll("[data-dashboard-tab]")) {
    tab.addEventListener("click", () => activateDashboardTab(tab.dataset.dashboardTab));
    tab.addEventListener("keydown", (event) => {
        const tabs = [...document.querySelectorAll("[data-dashboard-tab]:not(:disabled)")];
        const index = tabs.indexOf(tab);
        let next;
        if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
        else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault();
        activateDashboardTab(tabs[next].dataset.dashboardTab, true);
    });
}

function requestSessionClose() {
    const dialog = document.querySelector("#close-session-dialog");
    document.querySelector("#close-session-name").textContent = sessionTitle.textContent;
    const pending = sessionState.attendees.filter((item) => item.status === "PENDIENTE_FIRMA").length;
    const returns = sessionState.esEpp ? sessionState.attendees.filter((item) => item.status === "FIRMADO" && !item.returned).length : 0;
    const teachers = sessionState.esPanol ? sessionState.attendees.filter(item => item.status === "FIRMADO" && !item.teacherSigned).length : 0;
    const notes = [];
    if (pending) notes.push(`${pending} participante(s) pendiente(s) de firma.`);
    if (teachers) notes.push(`${teachers} firma(s) del docente pendiente(s).`);
    if (developmentDirty()) notes.push("Hay observaciones sin guardar; podrás guardarlas después, sin cambiar los horarios.");
    if (returns) notes.push(`${returns} devolución(es) de EPP pendiente(s) de firma.`);
    document.querySelector("#close-session-pending").textContent = notes.join(" ");
    dialog.returnValue = "cancel";
    return new Promise((resolve) => {
        dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), {once: true});
        dialog.showModal();
    });
}

function developmentValues() {
    return Object.fromEntries([...document.querySelectorAll('[data-development-field]')].map(input => [input.dataset.developmentField, input.value.trim()]));
}
function developmentDirty() {
    return Object.entries(developmentValues()).some(([key,value]) => value !== (developmentBaseline[key] || ''));
}
async function discardSessionDraft() {
    return !(developmentDirty() || signatureHasInk) || await askDiscardDraft();
}
function askDiscardDraft() {
    const dialog = document.querySelector('#discard-draft-dialog');
    dialog.returnValue = 'cancel';
    return new Promise(resolve => {
        dialog.addEventListener('close', () => resolve(dialog.returnValue === 'discard'), {once:true});
        dialog.showModal();
    });
}
window.addEventListener('beforeunload', event => {
    const creating = document.querySelector('#new-session-name').value.trim() || [...document.querySelectorAll('[data-template-field]')].some(input => input.value.trim());
    if (developmentDirty() || signatureHasInk || creating) { event.preventDefault(); event.returnValue = ''; }
});
function renderSessionDetails(session) {
    const details = document.querySelector('#session-template-details'); details.replaceChildren();
    const fields = Array.isArray(session.campos_definicion) ? session.campos_definicion : [];
    for (const field of [{nombre:'plantilla',etiqueta:'Tipo de actividad'}, ...fields]) {
        const value = field.nombre === 'plantilla' ? session.plantilla : session.campos?.[field.nombre];
        if (!value) continue;
        const group = document.createElement('div'); group.className = 'session-detail';
        const label = document.createElement('dt'); label.textContent = field.etiqueta;
        const text = document.createElement('dd'); text.textContent = value; group.append(label,text); details.append(group);
    }
}
async function apiFetch(...args) {
    const response = await fetch(...args);
    if (response.status === 401) { window.location.assign('/ingresar/'); throw new Error('La sesión de acceso venció.'); }
    if (response.status === 403 && !response.headers.get('Content-Type')?.includes('application/json')) throw new Error('El formulario venció. Recarga el panel antes de volver a guardar.');
    return response;
}
function addSignatureLink(parent, attendee, type, text) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = text;
    button.addEventListener('click', event => {
        event.stopPropagation();
        document.querySelector('#signature-preview-title').textContent = `${text}: ${attendee.name}`;
        document.querySelector('#signature-preview-image').src = `/api/asistencias/${attendee.id}/imagen/${type}/`;
        document.querySelector('#signature-preview-dialog').showModal();
    }); parent.append(button);
}
document.querySelector('#load-audit').addEventListener('click', async () => {
    const id = sessionState.currentSessionId; const results = document.querySelector('#audit-results');
    if (!id) return;
    results.textContent = 'Cargando historial…';
    try {
        const response = await apiFetch(`/api/sesiones/${id}/historial/`); const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo cargar el historial.');
        if (id !== sessionState.currentSessionId) return;
        results.replaceChildren();
        for (const row of data.historial) {
            const details = document.createElement('details'); const label = document.createElement('summary');
            label.textContent = `${new Date(row.fecha).toLocaleString('es-CL')} · ${row.usuario} · ${row.accion.replaceAll('_',' ')}`;
            const text = document.createElement('pre'); text.textContent = JSON.stringify({antes:row.anteriores,después:row.nuevos},null,2);
            details.append(label,text); results.append(details);
        }
        if (!data.historial.length) results.textContent = 'Sin cambios registrados.';
    } catch (error) { results.textContent = error.message; }
});

// Cierre explícito para que los cuadros también funcionen en navegadores embebidos.
for (const button of document.querySelectorAll('dialog form[method="dialog"] button')) {
    button.type = 'button';
    button.addEventListener('click', () => button.closest('dialog').close(button.value || 'cancel'));
}


for (const button of document.querySelectorAll("[data-export-format]")) {
    button.addEventListener("click", () => {
        if (!sessionState.currentSessionId) return;
        const ids = encodeURIComponent(sessionState.currentSessionId);
        window.location.assign(`/api/sesiones/exportar/${button.dataset.exportFormat}/?sesiones=${ids}`);
    });
}


document.querySelector('#download-poster').addEventListener('click', () => {
    const id = sessionState.currentSessionId;
    if (id) window.location.assign(`/api/sesiones/${encodeURIComponent(id)}/afiche.pdf`);
});
