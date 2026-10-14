
const sessionState = {
    currentSessionId: null,
    isOpen: false,
    attendees: []
};


let selectedAttendee = null;
let isDrawing = false;

const sessionQr = document.querySelector("#session-qr");

const createSessionForm = document.querySelector("#create-session-form");
const newSessionName = document.querySelector("#new-session-name");
const newSessionTemplate = document.querySelector("#new-session-template");
const newSessionHost = document.querySelector("#new-session-host");
const createSessionButton = document.querySelector("#create-session-button");
const createSessionFeedback = document.querySelector("#create-session-feedback");

const attendanceList = document.querySelector("#attendance-list");
const attendanceCount = document.querySelector("#attendance-count");
const sessionStatus = document.querySelector("#session-status");

const sessionSelector = document.querySelector("#session-selector");
const sessionTitle = document.querySelector(".session-info h2");
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

    try {
        const response = await fetch(
            `/api/sesiones/${sessionState.currentSessionId}/asistencias/lista/`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "No se pudieron cargar las asistencias."
            );
        }

        sessionState.isOpen = data.sesion.estado === "ABIERTA";

        sessionState.attendees = data.asistencias.map((item) => ({
            id: item.id,
            name: item.nombre,
            rut: item.rut,
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

    try {
        const response = await fetch("/api/sesiones/");
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

        if (sessions.length === 0) {
            sessionSelector.add(
                new Option("No hay sesiones disponibles", "")
            );

            resetSessionView();
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

        const preferredSession = sessions.find(
        (session) => Number(session.id) === Number(preferredSessionId)
        );

        const initialSession =
            preferredSession || firstOpenSession || sessions[0];

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
    } finally {
        sessionSelector.disabled =
            sessionSelector.options.length <= 1 &&
            sessionSelector.options[0]?.value === "";
    }
}


async function selectSession(sessionId, sessions) {
    sessionState.currentSessionId = sessionId;
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
        sessionDate.textContent = session.fecha_inicio || "";
    }

    attendanceList.innerHTML = "";
    attendanceCount.textContent = "Cargando asistentes...";
    sessionStatus.textContent = "Cargando sesión...";
    closeSessionButton.disabled = true;

    await loadAttendanceList();
}

function renderSessionQr(session) {
    sessionQr.innerHTML = "";

    if (!session || !session.token_qr) {
        sessionQr.textContent = "QR no disponible";
        return;
    }

    if (typeof QRCode === "undefined") {
        sessionQr.textContent = "No se pudo cargar la biblioteca QR";
        return;
    }

    const registrationUrl = new URL(
    "/",
    window.location.origin
    );

    registrationUrl.searchParams.set("token", session.token_qr);

    new QRCode(sessionQr, {
        text: registrationUrl.toString(),
        width: 220,
        height: 220,
        correctLevel: QRCode.CorrectLevel.M
    });
}

function resetSessionView() {
    sessionQr.innerHTML = "";
    sessionQr.textContent = "Selecciona una sesión";

    sessionState.currentSessionId = null;
    sessionState.isOpen = false;
    sessionState.attendees = [];
    selectedAttendee = null;

    sessionTitle.textContent = "No hay una sesión seleccionada";
    sessionDate.textContent = "";
    sessionStatus.textContent = "Selecciona una sesión.";
    attendanceList.innerHTML = "";
    attendanceCount.textContent = "0 asistentes";
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
        rut.textContent = attendee.rut;

        info.appendChild(name);
        info.appendChild(rut);

        const status = document.createElement("span");
        status.className =
            `attendance-state ${getStatusClass(attendee.status)}`;
        status.textContent = getStatusText(attendee.status);

        article.appendChild(info);
        article.appendChild(status);

        if (
            attendee.status === "PENDIENTE_FIRMA" &&
            sessionState.isOpen
        ) {
            article.classList.add("attendance-item-clickable");
            article.addEventListener("click", () => {
                selectAttendee(attendee.id);
            });
        }

        attendanceList.appendChild(article);
    });

    updateAttendanceCount();
}


function updateAttendanceCount() {

    const count = sessionState.attendees.length;

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


function selectAttendee(attendeeId) {
    if (!sessionState.isOpen) {
        return;
    }

    const attendee = sessionState.attendees.find(
        (item) => item.id === attendeeId
    );

    if (!attendee) {
        return;
    }

    if (attendee.status !== "PENDIENTE_FIRMA") {
        return;
    }

    selectedAttendee = attendee;

    signatureAttendeeName.textContent = attendee.name;
    signatureAttendeeRut.textContent = attendee.rut;

    clearSignature();

    signatureSection.hidden = false;

    signatureSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


function clearSignature() {

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

    confirmSignatureButton.disabled = true;

    try {
        const response = await fetch(
            `/api/asistencias/${selectedAttendee.id}/firma/`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
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
    if (!sessionState.isOpen) {
        return;
    }

    const confirmed = window.confirm(
        "¿Estás seguro de que deseas cerrar esta sesión?"
    );

    if (!confirmed) {
        return;
    }

    closeSessionButton.disabled = true;

    try {
        const response = await fetch(
            `/api/sesiones/${sessionState.currentSessionId}/cerrar/`,
            {
                method: "POST"
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "No se pudo cerrar la sesión."
            );
        }

        sessionState.isOpen = false;
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


async function loadCreationOptions() {
    try {
        const response = await fetch("/api/plantillas/");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "No se pudieron cargar las opciones.");
        }

        newSessionTemplate.replaceChildren();
        newSessionHost.replaceChildren();

        newSessionTemplate.add(new Option("Selecciona una plantilla", ""));
        newSessionHost.add(new Option("Selecciona un anfitrión", ""));

        data.plantillas.forEach((item) => {
            newSessionTemplate.add(new Option(item.nombre, item.id));
        });

        data.anfitriones.forEach((item) => {
            newSessionHost.add(new Option(item.nombre, item.id));
        });

        createSessionButton.disabled =
            data.plantillas.length === 0 ||
            data.anfitriones.length === 0;

        if (data.plantillas.length === 0 || data.anfitriones.length === 0) {
            createSessionFeedback.textContent =
                "Necesitas al menos una plantilla activa y un anfitrión activo.";
        }
    } catch (error) {
        createSessionFeedback.textContent = error.message;
        createSessionButton.disabled = true;
    }
}

createSessionForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    createSessionButton.disabled = true;
    createSessionFeedback.textContent = "Creando sesión...";

    try {
        const response = await fetch("/api/sesiones/crear/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                nombre: newSessionName.value.trim(),
                plantilla_id: newSessionTemplate.value,
                anfitrion_id: newSessionHost.value
            })
        });

        const respuestaTexto = await response.text();
        console.log("Estado HTTP:", response.status);
        console.log("Respuesta del servidor:", respuestaTexto);

        let data;

        try {
            data = JSON.parse(respuestaTexto);
        } catch {
            throw new Error(
                `El servidor devolvió HTML en vez de JSON. Código HTTP: ${response.status}. Revisa la consola y la terminal de Django.`
            );
        }

        if (!response.ok) {
            throw new Error(data.error || "No se pudo crear la sesión.");
        }
        

        createSessionFeedback.textContent = "Sesión creada correctamente.";
        createSessionForm.reset();

        await loadSessions(data.sesion.id);
    } catch (error) {
        createSessionFeedback.textContent = error.message;
    } finally {
        createSessionButton.disabled = false;
    }
});

loadCreationOptions();
loadSessions();