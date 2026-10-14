const sessions = [
    {
        id: 1,
        name: "Seminario de Informática",
        type: "Seminario",
        date: "2026-09-23",
        host: "Juan Pérez",
        total: 35,
        signed: 32,
        pending: 3
    },
    {
        id: 2,
        name: "Reunión de Coordinación",
        type: "Reunión",
        date: "2026-09-18",
        host: "María González",
        total: 12,
        signed: 12,
        pending: 0
    },
    {
        id: 3,
        name: "Salida a Terreno",
        type: "Salida a terreno",
        date: "2026-09-12",
        host: "Juan Pérez",
        total: 24,
        signed: 21,
        pending: 3
    },
    {
        id: 4,
        name: "Capacitación Institucional",
        type: "Capacitación",
        date: "2026-08-28",
        host: "Pedro Soto",
        total: 42,
        signed: 42,
        pending: 0
    },
    {
        id: 5,
        name: "Reunión de Departamento",
        type: "Reunión",
        date: "2026-08-15",
        host: "María González",
        total: 18,
        signed: 16,
        pending: 2
    },
    {
        id: 6,
        name: "Seminario de Tecnología",
        type: "Seminario",
        date: "2026-07-20",
        host: "Pedro Soto",
        total: 30,
        signed: 29,
        pending: 1
    }
];

let filteredSessions = [...sessions];

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

function formatDate(dateString) {
    const [year, month, day] = dateString.split("-");

    return `${day}-${month}-${year}`;
}

function getExportData() {
    return filteredSessions.map((session) => ({
        "Sesión": session.name,
        "Tipo de Sesión": session.type,
        "Fecha": session.date,
        "Anfitrión": session.host,
        "Total de Asistencias": session.total,
        "Firmadas": session.signed,
        "Pendientes de firma": session.pending
    }));
}

function populateFilters() {
    const types = [...new Set(sessions.map((session) => session.type))];
    const hosts = [...new Set(sessions.map((session) => session.host))];

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

        tableBody.appendChild(row);
    });

    const count = filteredSessions.length;

    resultsCount.textContent =
        `${count} ${count === 1 ? "Sesión" : "Sesiones"}`;

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

        const matchesDateFrom =
            !dateFrom || session.date >= dateFrom;

        const matchesDateTo =
            !dateTo || session.date <= dateTo;

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

function exportCsv() {
    if (filteredSessions.length === 0) {
        showExportFeedback(
            "No hay Sesiones para exportar con los filtros seleccionados.",
            true
        );
        return;
    }

    const headers = [
        "Sesión",
        "Tipo de Sesión",
        "Fecha",
        "Anfitrión",
        "Total de Asistencias",
        "Firmadas",
        "Pendientes de firma"
    ];

    const rows = filteredSessions.map((session) => [
        session.name,
        session.type,
        session.date,
        session.host,
        session.total,
        session.signed,
        session.pending
    ]);

    const escapeCsvValue = (value) => {
        let text = String(value ?? "");

        // Evita que una celda que comienza con una fórmula
        // se interprete como tal en programas de hojas de cálculo.
        if (/^[\s]*[=+\-@]/.test(text)) {
            text = "'" + text;
        }

        return `"${text.replace(/"/g, '""')}"`;
    };

    const csvContent = [
        headers.map(escapeCsvValue).join(";"),
        ...rows.map((row) => row.map(escapeCsvValue).join(";"))
    ].join("\r\n");

    // BOM para mejorar la compatibilidad con tildes en Excel.
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
            "No hay Sesiones para exportar con los filtros seleccionados.",
            true
        );
        return;
    }

    if (typeof XLSX === "undefined") {
        showExportFeedback(
            "No se pudo cargar la biblioteca XLSX. Comprueba tu conexión a Internet.",
            true
        );
        return;
    }

    const worksheet = XLSX.utils.json_to_sheet(getExportData());
    const workbook = XLSX.utils.book_new();

    XLSX.utils.book_append_sheet(
        workbook,
        worksheet,
        "Historial de Sesiones"
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

populateFilters();
renderSessions();