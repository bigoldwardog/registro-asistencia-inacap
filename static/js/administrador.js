
let sessions = [];
let filteredSessions = [];

const filtersForm = document.querySelector("#filters-form");
const typeFilter = document.querySelector("#filter-type");
const hostFilter = document.querySelector("#filter-host");
const dateFromFilter = document.querySelector("#filter-date-from");
const dateToFilter = document.querySelector("#filter-date-to");

const tableBody = document.querySelector("#sessions-table-body");
const resultsCount = document.querySelector("#results-count");
const emptyMessage = document.querySelector("#empty-message");
const filterError = document.querySelector("#filter-error");
const exportFeedback = document.querySelector("#export-feedback");

const clearFiltersButton = document.querySelector("#clear-filters");
const exportCsvButton = document.querySelector("#export-csv");
const exportXlsxButton = document.querySelector("#export-xlsx");
const logoutButton = document.querySelector("#logout-button");

const historyPanel = document.querySelector(".history-section");

const detailSection = document.querySelector("#session-detail-section");
const detailTitle = document.querySelector("#detail-session-title");
const detailInfo = document.querySelector("#detail-session-info");
const detailFeedback = document.querySelector("#detail-feedback");
const attendeesTableBody = document.querySelector("#attendees-table-body");
const attendeesEmptyMessage = document.querySelector("#attendees-empty-message");
const backToHistoryButton = document.querySelector("#back-to-history");

function normalizeDate(value) {
    if (!value) {
        return "";
    }

    // Acepta fechas como "2026-10-14 06:29:16"
    // y fechas ISO con zona horaria.
    return String(value).slice(0, 10);
}

function formatDate(dateString) {
    if (!dateString) {
        return "Sin fecha";
    }

    const [year, month, day] = dateString.split("-");

    return `${day}-${month}-${year}`;
}

async function loadSessions() {
    tableBody.replaceChildren();
    resultsCount.textContent = "Cargando sesiones...";
    emptyMessage.hidden = true;
    exportFeedback.hidden = true;

    try {
        const response = await fetch(
            "/api/administrador/historial/"
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "No se pudieron cargar las sesiones."
            );
        }

        if (!Array.isArray(data.sesiones)) {
            throw new Error(
                "La respuesta del servidor no contiene una lista válida."
            );
        }

        sessions = data.sesiones.map((sesion) => ({
            id: sesion.id,
            name: sesion.nombre || "Sin nombre",
            type: sesion.plantilla || "Sin plantilla",
            date: normalizeDate(
                sesion.fecha_inicio || sesion.fecha_cierre
            ),
            host: sesion.anfitrion || "Sin anfitrión",
            total: Number(sesion.total_asistencias) || 0,
            signed: Number(sesion.total_firmadas) || 0,
            pending: Number(sesion.total_pendientes) || 0,
            status: sesion.estado || "Desconocido"
        }));

        filteredSessions = [...sessions];

        populateFilters();
        renderSessions();

    } catch (error) {
        console.error("Error al cargar el historial:", error);

        resultsCount.textContent = "Error al cargar las sesiones";
        emptyMessage.textContent =
            "No se pudieron obtener las sesiones del servidor.";
        emptyMessage.hidden = false;

        showExportFeedback(error.message, true);
    }
}

function populateFilters() {
    // Conserva la primera opción, normalmente "Todos".
    [typeFilter, hostFilter].forEach((select) => {
        while (select.options.length > 1) {
            select.remove(1);
        }
    });

    const types = [
        ...new Set(sessions.map((session) => session.type))
    ];

    const hosts = [
        ...new Set(sessions.map((session) => session.host))
    ];

    types.sort().forEach((type) => {
        const option = document.createElement("option");
        option.value = type;
        option.textContent = type;
        typeFilter.appendChild(option);
    });

    hosts.sort().forEach((host) => {
        const option = document.createElement("option");
        option.value = host;
        option.textContent = host;
        hostFilter.appendChild(option);
    });
}

function renderSessions() {
    tableBody.replaceChildren();

    filteredSessions.forEach((session) => {
        const row = document.createElement("tr");

        const values = [
            session.name,
            session.type,
            formatDate(session.date),
            session.host,
            session.total,
            session.signed,
            session.pending
        ];

        values.forEach((value, index) => {
            const cell = document.createElement("td");
            cell.textContent = value;

            if (index >= 4) {
                cell.classList.add("status-number");
            }

            row.appendChild(cell);
        });
        
        row.classList.add("clickable-session");
        row.tabIndex = 0;
        row.setAttribute("role", "button");
        row.setAttribute(
            "aria-label",
            `Ver asistentes de la sesión ${session.name}`
        );

        row.addEventListener("click", () => {
            openSessionDetail(session);
        });

        row.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openSessionDetail(session);
            }
        });
        tableBody.appendChild(row);
    });

    const count = filteredSessions.length;

    resultsCount.textContent =
        `${count} ${count === 1 ? "Sesión" : "Sesiones"}`;

    emptyMessage.textContent = "No hay sesiones que coincidan con los filtros.";
    emptyMessage.hidden = count !== 0;
}

function applyFilters(event) {
    event.preventDefault();

    const selectedType = typeFilter.value;
    const selectedHost = hostFilter.value;
    const dateFrom = dateFromFilter.value;
    const dateTo = dateToFilter.value;

    filterError.hidden = true;
    exportFeedback.hidden = true;

    if (dateFrom && dateTo && dateFrom > dateTo) {
        filterError.textContent =
            "La fecha inicial no puede ser posterior a la fecha final.";

        filterError.hidden = false;
        return;
    }

    filteredSessions = sessions.filter((session) => {
        const matchesType =
            !selectedType || session.type === selectedType;

        const matchesHost =
            !selectedHost || session.host === selectedHost;

        // Las sesiones sin fecha no coinciden con filtros de fecha.
        const matchesDateFrom =
            !dateFrom || (
                session.date !== "" &&
                session.date >= dateFrom
            );

        const matchesDateTo =
            !dateTo || (
                session.date !== "" &&
                session.date <= dateTo
            );

        return (
            matchesType &&
            matchesHost &&
            matchesDateFrom &&
            matchesDateTo
        );
    });

    renderSessions();
}

function clearFilters() {
    filtersForm.reset();

    filteredSessions = [...sessions];

    filterError.hidden = true;
    exportFeedback.hidden = true;

    renderSessions();
}

function showExportFeedback(message, isError = false) {
    exportFeedback.textContent = message;
    exportFeedback.classList.toggle("error-message", isError);
    exportFeedback.hidden = false;
}

function getExportData() {
    return filteredSessions.map((session) => ({
        "Sesión": session.name,
        "Tipo de Sesión": session.type,
        "Fecha": session.date || "Sin fecha",
        "Anfitrión": session.host,
        "Estado": session.status,
        "Total de Asistencias": session.total,
        "Firmadas": session.signed,
        "Pendientes de firma": session.pending
    }));
}

function exportCsv() {
    if (filteredSessions.length === 0) {
        showExportFeedback(
            "No hay sesiones para exportar con los filtros seleccionados.",
            true
        );
        return;
    }

    const headers = [
        "Sesión",
        "Tipo de Sesión",
        "Fecha",
        "Anfitrión",
        "Estado",
        "Total de Asistencias",
        "Firmadas",
        "Pendientes de firma"
    ];

    const rows = filteredSessions.map((session) => [
        session.name,
        session.type,
        session.date || "Sin fecha",
        session.host,
        session.status,
        session.total,
        session.signed,
        session.pending
    ]);

    const escapeCsvValue = (value) => {
        let text = String(value ?? "");

        if (/^[\s]*[=+\-@]/.test(text)) {
            text = "'" + text;
        }

        return `"${text.replace(/"/g, '""')}"`;
    };

    const csvContent = [
        headers.map(escapeCsvValue).join(";"),
        ...rows.map((row) => row.map(escapeCsvValue).join(";"))
    ].join("\r\n");

    const blob = new Blob(
        ["\uFEFF", csvContent],
        { type: "text/csv;charset=utf-8;" }
    );

    downloadFile(blob, "historial-sesiones.csv");

    showExportFeedback("Archivo CSV generado correctamente.");
}

function exportXlsx() {
    if (filteredSessions.length === 0) {
        showExportFeedback(
            "No hay sesiones para exportar con los filtros seleccionados.",
            true
        );
        return;
    }

    if (typeof XLSX === "undefined") {
        showExportFeedback(
            "No se pudo cargar la biblioteca XLSX. Comprueba su disponibilidad.",
            true
        );
        return;
    }

    const worksheet = XLSX.utils.json_to_sheet(getExportData());
    const workbook = XLSX.utils.book_new();

    XLSX.utils.book_append_sheet(
        workbook,
        worksheet,
        "Historial de sesiones"
    );

    XLSX.writeFile(workbook, "historial-sesiones.xlsx");

    showExportFeedback("Archivo XLSX generado correctamente.");
}

function downloadFile(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);
}

function logout() {
    window.alert(
        "El cierre de sesión se implementará cuando incorporemos la autenticación."
    );
}

filtersForm.addEventListener("submit", applyFilters);
clearFiltersButton.addEventListener("click", clearFilters);
exportCsvButton.addEventListener("click", exportCsv);
exportXlsxButton.addEventListener("click", exportXlsx);
logoutButton.addEventListener("click", logout);

function formatDateTime(value) {
    if (!value) return "Sin fecha";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return date.toLocaleString("es-CL", {
        dateStyle: "short",
        timeStyle: "short"
    });
}

function showDetailFeedback(message, isError = false) {
    detailFeedback.textContent = message;
    detailFeedback.classList.toggle("error-message", isError);
    detailFeedback.hidden = false;
}

async function openSessionDetail(session) {
    historyPanel.hidden = true;
    detailSection.hidden = false;

    detailTitle.textContent = session.name;
    detailInfo.textContent =
        `Tipo: ${session.type} | Anfitrión: ${session.host} | Estado: ${session.status}`;

    attendeesTableBody.replaceChildren();
    attendeesEmptyMessage.hidden = true;
    detailFeedback.hidden = true;

    showDetailFeedback("Cargando asistentes...");

    try {
        const response = await fetch(
            `/api/sesiones/${session.id}/asistencias/lista/`
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "No se pudieron cargar los asistentes."
            );
        }

        // El endpoint debe devolver la lista bajo la clave "asistencias".
        if (!Array.isArray(data.asistencias)) {
            throw new Error(
                "La respuesta no contiene la lista de asistentes esperada."
            );
        }

        attendeesTableBody.replaceChildren();
        detailFeedback.hidden = true;

        data.asistencias.forEach((attendee) => {
            const row = document.createElement("tr");

            
            const values = [
                attendee.nombre,
                attendee.rut,
                attendee.telefono,
                attendee.correo,
                formatDateTime(attendee.fecha_registro),
                attendee.estado === "FIRMADO"
                    ? "Firmado"
                    : attendee.estado === "PENDIENTE_FIRMA"
                        ? "Pendiente de firma"
                        : attendee.estado || "Desconocido"
            ];

            values.forEach((value) => {
                const cell = document.createElement("td");
                cell.textContent = value || "—";
                row.appendChild(cell);
            });

            attendeesTableBody.appendChild(row);
        });

        attendeesEmptyMessage.hidden = data.asistencias.length !== 0;

    } catch (error) {
        console.error("Error al cargar asistentes:", error);
        showDetailFeedback(error.message, true);
    }
}

function closeSessionDetail() {
    detailSection.hidden = true;
    historyPanel.hidden = false;
}

backToHistoryButton.addEventListener("click", closeSessionDetail);

loadSessions();
