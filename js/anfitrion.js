const sessionState = {
    isOpen: true,

    attendees: [
        {
            id: 1,
            name: "Juan Pérez",
            rut: "12.345.678-9",
            status: "PENDIENTE_FIRMA"
        },
        {
            id: 2,
            name: "María González",
            rut: "11.234.567-8",
            status: "FIRMADO"
        },
        {
            id: 3,
            name: "Pedro Soto",
            rut: "15.678.901-2",
            status: "PENDIENTE_FIRMA"
        }
    ]
};


let selectedAttendee = null;
let isDrawing = false;


const attendanceList = document.querySelector("#attendance-list");
const attendanceCount = document.querySelector("#attendance-count");
const sessionStatus = document.querySelector("#session-status");

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


function renderAttendanceList() {

    attendanceList.innerHTML = "";

    sessionState.attendees.forEach((attendee) => {

        const article = document.createElement("article");

        article.className = "attendee";

        article.innerHTML = `
            <div class="attendee-info">
                <strong>${attendee.name}</strong>
                <span>${attendee.rut}</span>
            </div>

            <span class="attendance-status ${getStatusClass(attendee.status)}">
                ${getStatusText(attendee.status)}
            </span>
        `;

        if (attendee.status === "PENDIENTE_FIRMA") {

            article.style.cursor = "pointer";

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

    isDrawing = true;

    const position = getCanvasPosition(event);

    signatureContext.beginPath();

    signatureContext.moveTo(
        position.x,
        position.y
    );
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


function confirmSignature() {

    if (!selectedAttendee) {
        return;
    }

    const signatureData = signaturePad.toDataURL("image/png");

    const isEmpty =
        signatureData ===
        createEmptyCanvasData();

    if (isEmpty) {

        alert("El asistente debe realizar su firma.");

        return;
    }

    selectedAttendee.status = "FIRMADO";

    selectedAttendee.signature = signatureData;

    renderAttendanceList();

    signatureSection.hidden = true;

    selectedAttendee = null;

    clearSignature();
}


function createEmptyCanvasData() {

    const temporaryCanvas = document.createElement("canvas");

    temporaryCanvas.width = signaturePad.width;
    temporaryCanvas.height = signaturePad.height;

    return temporaryCanvas.toDataURL("image/png");
}


function closeSession() {

    if (!sessionState.isOpen) {
        return;
    }

    const confirmed = window.confirm(
        "¿Estás seguro de que deseas cerrar esta sesión?"
    );

    if (!confirmed) {
        return;
    }

    sessionState.isOpen = false;

    sessionStatus.textContent = "Sesión cerrada";

    closeSessionButton.disabled = true;

    closeSessionButton.textContent = "Sesión cerrada";
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

signaturePad.addEventListener(
    "pointerleave",
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


renderAttendanceList();