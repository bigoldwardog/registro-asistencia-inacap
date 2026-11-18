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
    for (const clave of claves) form.elements[clave].value = rol?.[clave] || (clave === 'consultar' ? 'PROPIAS' : 'NINGUNA');
});

function mostrarUsuario() {
    const usuario = usuarios.find(item => String(item.usuario_id) === selectorUsuario.value);
    if (!usuario) return;
    const rol = roles.find(item => item.id === usuario.rol_id);
    document.getElementById('rol-actual').textContent = 'Rol actual · ' +
        (usuario.superusuario ? 'Superusuario' : rol.nombre);
    asignacion.value = String(rol.id);
    asignacion.disabled = usuario.superusuario;
    document.getElementById('asignar-boton').disabled = usuario.superusuario;
    const lista = document.getElementById('permisos-usuario');
    lista.replaceChildren();
    const permisos = [];
    claves.forEach((clave, indice) => {
        const alcance = usuario.superusuario ? 'TODAS' : rol[clave];
        permisos.push(etiquetas[indice] + ' · ' + alcances[alcance]);
    });
    if (usuario.superusuario) permisos.push('Crear cuentas y administrar roles y permisos');
    for (const permiso of permisos) {
        const item = document.createElement('li');
        item.textContent = permiso;
        lista.append(item);
    }
}
selectorUsuario.addEventListener('change', mostrarUsuario);
mostrarUsuario();
