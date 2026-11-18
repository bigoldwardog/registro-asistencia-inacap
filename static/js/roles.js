const roles = JSON.parse(document.getElementById('roles-datos').textContent);
const usuarios = JSON.parse(document.getElementById('usuarios-datos').textContent);
const form = document.getElementById('rol-form');
const selectorRol = document.getElementById('editar-rol');
const selectorUsuario = document.getElementById('usuario-select');
const asignacion = document.getElementById('asignar-rol');
const claves = ['consultar', 'crear', 'observaciones', 'cerrar', 'exportar'];
const etiquetas = ['Consultar sesiones', 'Crear sesiones', 'Modificar observaciones', 'Cerrar sesiones', 'Exportar sesiones'];
const alcances = {NINGUNA: 'Ninguna', PROPIAS: 'Propias', TODAS: 'Todas'};

selectorRol.addEventListener('change', () => {
    const rol = roles.find(item => String(item.id) === selectorRol.value);
    document.getElementById('rol-id').value = rol?.id || '';
    document.getElementById('rol-nombre').value = rol?.nombre || '';
    document.getElementById('rol-superusuario').checked = Boolean(rol?.superusuario);
    actualizarDescripcionSuperusuario();
    for (const clave of claves) {
        form.elements[clave].value = rol?.[clave] || (clave === 'consultar' ? 'PROPIAS' : 'NINGUNA');
        const ambito = rol?.ambitos?.[clave];
        for (const dimension of ['sedes', 'areas']) {
            const modo = form.elements[clave + '_' + dimension + '_modo'];
            modo.value = ambito?.[dimension + '_modo'] || (rol ? 'TODAS' : 'PERFIL');
            const opciones = form.querySelectorAll('input[name="' + clave + '_' + dimension + '"]');
            for (const opcion of opciones) opcion.checked = (ambito?.[dimension] || []).includes(Number(opcion.value));
            actualizarAmbito(modo);
        }
    }
});

function mostrarUsuario() {
    const usuario = usuarios.find(item => String(item.usuario_id) === selectorUsuario.value);
    if (!usuario) return;
    const rol = roles.find(item => item.id === usuario.rol_id);
    const organizacion = document.getElementById('organizacion-form');
    document.getElementById('organizacion-usuario').value = usuario.usuario_id;
    document.getElementById('asignacion-usuario').value = usuario.usuario_id;
    organizacion.elements.sede.value = usuario.sede_id || '';
    organizacion.elements.area.value = usuario.area_id || '';
    document.getElementById('rol-actual').textContent = 'Rol actual · ' +
        (usuario.superusuario ? 'Superusuario inicial' : rol.nombre);
    asignacion.value = String(rol.id);
    asignacion.disabled = usuario.superusuario;
    document.getElementById('asignar-boton').disabled = usuario.superusuario;
    const lista = document.getElementById('permisos-usuario');
    lista.replaceChildren();
    if (usuario.superusuario || rol.superusuario) {
        const item = document.createElement('li');
        item.className = 'permiso-total';
        const titulo = document.createElement('strong');
        titulo.textContent = 'Acceso completo';
        const detalle = document.createElement('span');
        detalle.textContent = 'Todas las sesiones, sedes y áreas. Puede crear cuentas y administrar roles y permisos.';
        item.append(titulo, detalle);
        lista.append(item);
        return;
    }
    claves.forEach((clave, indice) => {
        const alcance = rol[clave];
        const ambito = rol.ambitos?.[clave];
        const item = document.createElement('li');
        item.className = 'permiso-resumen';
        const cabecera = document.createElement('div');
        const titulo = document.createElement('strong');
        titulo.textContent = etiquetas[indice];
        const estado = document.createElement('span');
        estado.className = 'permiso-alcance' + (alcance === 'NINGUNA' ? ' sin-acceso' : '');
        estado.textContent = alcance === 'NINGUNA' ? 'Sin acceso' : alcances[alcance];
        cabecera.append(titulo, estado);
        item.append(cabecera);
        if (alcance !== 'NINGUNA') {
            for (const dimension of ['sedes', 'areas']) {
                const modo = ambito?.[dimension + '_modo'] || 'PERFIL';
                let texto = modo === 'PERFIL' ? 'Del perfil' : 'Todas';
                if (modo === 'SELECCION') {
                    const opciones = form.querySelectorAll('input[name="' + clave + '_' + dimension + '"]');
                    texto = [...opciones].filter(opcion => ambito[dimension].includes(Number(opcion.value))).map(opcion => opcion.closest('label').textContent.trim()).join(', ') || 'Sin selección';
                }
                const detalle = document.createElement('span');
                detalle.className = 'permiso-dimension';
                detalle.textContent = (dimension === 'sedes' ? 'Sedes: ' : 'Áreas: ') + texto;
                item.append(detalle);
            }
        }
        lista.append(item);
    });
}
selectorUsuario.addEventListener('change', mostrarUsuario);
mostrarUsuario();


function listaAmbito(selector) {
    return document.querySelector('[data-ambito-lista="' + selector.dataset.ambitoModo + '"]');
}
function actualizarBotonAmbito(selector) {
    const lista = listaAmbito(selector);
    const boton = document.querySelector('[data-ambito-boton="' + selector.dataset.ambitoModo + '"]');
    const cantidad = lista.querySelectorAll('input:checked').length;
    boton.hidden = selector.value !== 'SELECCION';
    boton.textContent = (lista.hidden ? 'Elegir opciones' : 'Cerrar lista') + ' (' + cantidad + ' seleccionadas)';
    boton.setAttribute('aria-expanded', String(!lista.hidden));
}
function actualizarAmbito(selector) {
    listaAmbito(selector).hidden = selector.value !== 'SELECCION';
    actualizarBotonAmbito(selector);
}
function cerrarListasAmbito(excepto = null) {
    for (const selector of document.querySelectorAll('[data-ambito-modo]')) {
        if (selector === excepto) continue;
        listaAmbito(selector).hidden = true;
        actualizarBotonAmbito(selector);
    }
}
for (const selector of document.querySelectorAll('[data-ambito-modo]')) {
    const lista = listaAmbito(selector);
    const boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'ambito-selector-boton';
    boton.dataset.ambitoBoton = selector.dataset.ambitoModo;
    lista.id = 'lista-' + selector.dataset.ambitoModo;
    boton.setAttribute('aria-controls', lista.id);
    lista.before(boton);
    boton.addEventListener('click', () => {
        const abrir = lista.hidden;
        cerrarListasAmbito(selector);
        lista.hidden = !abrir;
        actualizarBotonAmbito(selector);
    });
    lista.addEventListener('change', () => actualizarBotonAmbito(selector));
    selector.addEventListener('change', () => {
        cerrarListasAmbito(selector);
        actualizarAmbito(selector);
    });
    actualizarBotonAmbito(selector);
}
document.addEventListener('click', event => {
    if (!event.target.closest('[data-ambito-lista], [data-ambito-boton], [data-ambito-modo]')) {
        cerrarListasAmbito();
    }
});
document.addEventListener('keydown', event => {
    if (event.key === 'Escape') cerrarListasAmbito();
});

const rolGuardado = new URLSearchParams(window.location.search).get('rol');
if (roles.some(rol => String(rol.id) === rolGuardado)) {
    selectorRol.value = rolGuardado;
    selectorRol.dispatchEvent(new Event('change'));
}

function actualizarDescripcionSuperusuario() {
    document.getElementById('descripcion-superusuario').hidden = !document.getElementById('rol-superusuario').checked;
}
document.getElementById('rol-superusuario').addEventListener('change', actualizarDescripcionSuperusuario);
actualizarDescripcionSuperusuario();

const navegacionRoles = document.querySelectorAll('[data-roles-seccion]');
const panelesRoles = document.querySelectorAll('[data-roles-panel]');
function mostrarSeccionRoles(clave, animar = false) {
    if (![...panelesRoles].some(panel => panel.dataset.rolesPanel === clave)) clave = 'configuracion';
    for (const boton of navegacionRoles) {
        boton.disabled = boton.dataset.rolesSeccion === clave;
        boton.setAttribute('aria-current', String(boton.dataset.rolesSeccion === clave));
    }
    for (const panel of panelesRoles) {
        panel.hidden = panel.dataset.rolesPanel !== clave;
        if (!panel.hidden && animar && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            panel.animate([{opacity: 0, transform: 'translateY(8px)'}, {opacity: 1, transform: 'translateY(0)'}], {duration: 180, easing: 'ease-out'});
        }
    }
}
for (const boton of navegacionRoles) {
    boton.addEventListener('click', () => {
        const clave = boton.dataset.rolesSeccion;
        mostrarSeccionRoles(clave, true);
        history.replaceState(null, '', '#' + clave);
    });
}
mostrarSeccionRoles(location.hash.slice(1) || document.querySelector('.roles-secciones').dataset.seccionInicial);
window.addEventListener('hashchange', () => mostrarSeccionRoles(location.hash.slice(1), true));
