const main = document.querySelector('#main');
const dialog = document.querySelector('#dialog');
const people = {
  'Rodrigo Silva': ['18.342.912-6', 'Rodrigo', 'Silva', 'Rojas', '+56 9 0000 0010', 'rodrigo@example.org'],
  'Camila Torres': ['17.203.188-5', 'Camila', 'Torres', 'Díaz', '+56 9 0000 0020', 'camila@example.org'],
  'Valentina Rojas': ['20.120.631-2', 'Valentina', 'Rojas', 'Díaz', '+56 9 0000 0030', 'valentina@example.org'],
};
const labels = ['RUT', 'Nombres', 'Apellido paterno', 'Apellido materno', 'Teléfono', 'Correo'];
const sessions = [
  {title:'Introducción a redes', type:'Registro de asistencia', host:'Rodrigo Silva', day:'2026-11-11', state:'En curso', signed:58, count:60, theme:'Conceptos básicos de redes', start:'11-11-2026, 10:00', hostSignature:'demo', fields:{Lugar:'Auditorio'}},
  {title:'Coordinación docente', type:'Acta de reunión', host:'Camila Torres', day:'2026-11-12', state:'Programada', signed:0, count:0, theme:'Planificación del semestre', fields:{Lugar:'Sala 402'}},
  {title:'Seguridad en terreno', type:'Entrega de elementos de protección personal', host:'Camila Torres', day:'2026-11-10', state:'Finalizada', signed:60, count:60, theme:'Inducción y entrega de EPP', start:'10-11-2026, 09:00', end:'10-11-2026, 10:30', hostSignature:'demo', fields:{Lugar:'Taller'}},
];
sessions.forEach(s => {s.attendees = []; s.notes = {};});
sessions[0].attendees.push({name:'Valentina Rojas Díaz',rut:'20.120.631-2',state:'Firmado'},{name:'Diego Morales Soto',rut:'19.310.125-4',state:'Pendiente de firma'});
const roles = {
  Superusuario:['Gestionar roles','Crear sesiones','Exportar propias','Consultar y exportar todas'],
  Docente:['Crear sesiones','Exportar propias'],
  'Consulta general':['Consultar y exportar todas'],
  'Consulta propia':[],
};
const baseAccount = 'Coordinación académica';
const users = {
  [baseAccount]:'Superusuario',
  'Rodrigo Silva':'Docente',
  'Camila Torres':'Consulta propia',
  'Valentina Rojas':'Consulta general',
};
let inspectedUser = 'Rodrigo Silva';
let inspectedRole = 'Docente';
const account = document.querySelector('#account');
const isSuperuser = () => account.value === baseAccount;
const allowed = permission => roles[users[account.value]].includes(permission);
const canSee = s => s.host === account.value || allowed('Consultar y exportar todas');
const canExport = () => allowed('Exportar propias') || allowed('Consultar y exportar todas');
account.onchange = () => {
  scope = allowed('Consultar y exportar todas') ? 'Todas las sesiones' : 'Mis sesiones';
  filter = {};
  show('sessions');
};
let selected = sessions[0];
let tab = 'Resumen y QR';
let scope = 'Todas las sesiones';
let filter = {};
let publicRecord;
let publicSession;
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[char]);
const options = (items, selected) => items.map(item => `<option ${item===selected?'selected':''}>${esc(item)}</option>`).join('');
const button = (label, action, kind='') => `<button type="button" class="${kind}" data-action="${action}">${label}</button>`;
const heading = (crumb,title,description,action='') => `<p class="crumb">${crumb}</p><div class="heading"><div><h1>${esc(title)}</h1><p>${description}</p></div>${action}</div>`;
const badge = (label, kind='') => `<span class="tag ${kind}">${esc(label)}</span>`;
const dateLabel = day => day ? day.split('-').reverse().join('-') : '—';
const stamp = () => new Intl.DateTimeFormat('es-CL',{dateStyle:'short',timeStyle:'short',timeZone:'America/Santiago'}).format(new Date());
const fields = (type, during, values={}) => (templates[type] || []).filter(f => f.during===during).map(f => {
  const label = esc(f.label);
  const name = `name="${label}"`;
  const required = f.required ? 'required' : '';
  const val = esc(values[f.label]);
  const narrative = /objetivo|desarrollo|observaciones|minuta|compromisos|temas tratados|metodología|descripción/i.test(f.label);
  return narrative ? `<label class="wide">${label}<textarea ${name} ${required}>${val}</textarea></label>` :
    `<label>${label}<input ${name} type="${({fecha:'date',hora:'time',email:'email',numero:'number'})[f.type] || 'text'}" value="${val}" ${required}></label>`;
}).join('');

function show(view) {
  document.querySelector('#accountRole').textContent = isSuperuser() ? 'Superusuario base' : users[account.value];
  document.querySelector('[data-view="roles"]').hidden = !isSuperuser();
  if((view==='roles' && !isSuperuser()) || (view==='detail' && !canSee(selected)) || (view==='create' && !allowed('Crear sesiones'))) view='sessions';
  document.querySelectorAll('nav button').forEach(b => b.classList.toggle('active',b.dataset.view===(view==='detail'||view==='create'?'sessions':view)));
  ({sessions:showSessions, detail:showDetail, create:showCreate, roles:showRoles, public:showPublic, account:showAccount})[view]();
}

function showAccount() {
  const profile = people[account.value];
  main.innerHTML = heading('Registro de asistencia','Mi cuenta','Información de la cuenta de demostración',button('Volver a sesiones','sessions')) +
    `<section class="card"><dl>
      <div><dt>Nombre</dt><dd>${esc(account.value)}</dd></div>
      <div><dt>Rol</dt><dd>${esc(users[account.value])}</dd></div>
    </dl><details><summary>Ver datos ficticios de contacto</summary>
      <dl><div><dt>Correo</dt><dd>${esc(profile?.[5] || 'coordinacion@example.org')}</dd></div>
      <div><dt>Teléfono</dt><dd>${esc(profile?.[4] || 'Sin teléfono asociado')}</dd></div></dl>
    </details></section>`;
}

function showSessions() {
  const rows = sessions.filter(s =>
    canSee(s) &&
    (scope!=='Mis sesiones'||s.host===account.value) &&
    (scope!=='Programadas'||s.state==='Programada') &&
    (scope!=='Finalizadas'||s.state==='Finalizada') &&
    (!filter.query || [s.title,s.theme,s.host,...s.attendees.flatMap(a=>[a.name,a.rut])].some(v=>String(v).toLowerCase().includes(filter.query.toLowerCase()))) &&
    (!filter.type || s.type===filter.type) && (!filter.host || s.host===filter.host) &&
    (!filter.from || s.day>=filter.from) && (!filter.to || s.day<=filter.to));
  main.innerHTML = heading('Registro de asistencia','Sesiones','Consulta actividades, revisa las firmas y exporta los registros.',allowed('Crear sesiones')?button('+ Nueva sesión','create','primary'):'') +
    `<div class="tabs" aria-label="Vistas de sesiones">${['Todas las sesiones','Mis sesiones','Programadas','Finalizadas'].filter(x=>x!=='Todas las sesiones'||allowed('Consultar y exportar todas')).map(x=>`<button data-scope="${x}" class="${x===scope?'active':''}">${x}</button>`).join('')}</div>
    <form id="filter" class="card"><div class="fields filter-grid"><label class="wide">Persona o actividad<input name="query" value="${esc(filter.query)}" placeholder="Nombre, RUT o nombre de la sesión"></label>
    <label>Tipo de actividad<select name="type"><option value="">Todos</option>${options(Object.keys(templates),filter.type)}</select></label>
    <label>Anfitrión<select name="host"><option value="">Todos</option>${options(Object.keys(people),filter.host)}</select></label>
    <label>Desde<input name="from" type="date" value="${esc(filter.from)}"></label><label>Hasta<input name="to" type="date" value="${esc(filter.to)}"></label></div>
    <div class="actions"><button class="primary">Aplicar filtros</button>${button('Limpiar','clear-filters')}</div></form>
    <section class="card table-card"><div class="toolbar"><div class="actions">${canExport()?button('Exportar Excel','xlsx')+button('Exportar CSV','csv'):''}</div><span>${rows.length} sesiones</span></div>
    <div class="table-wrap"><table><thead><tr><th>Actividad</th><th>Tipo</th><th>Fecha</th><th>Anfitrión</th><th>Firmas</th><th>Estado</th></tr></thead><tbody>
    ${rows.map(s=>`<tr><td>${button(esc(s.title),'open-'+sessions.indexOf(s),'link')}</td><td>${esc(s.type)}</td><td>${dateLabel(s.day)}</td><td>${esc(s.host)}</td><td>${s.signed} de ${s.count}</td><td>${badge(s.state,s.state==='En curso'?'red':'')}</td></tr>`).join('') || '<tr><td colspan="6">No hay sesiones que coincidan con los filtros.</td></tr>'}</tbody></table></div></section><p class="notice" role="status"></p>`;
  document.querySelector('#filter').onsubmit = e => {e.preventDefault(); filter=Object.fromEntries(new FormData(e.target)); show('sessions');};
}

function showCreate() {
  main.innerHTML = heading('Sesiones / Nueva sesión','Nueva sesión','Puedes programar la actividad o iniciarla con la firma del anfitrión.') +
    `<form id="create" class="card"><div class="fields"><label class="wide">Título de la actividad<input name="title" required></label><label>Plantilla<select name="type">${options(Object.keys(templates),'Registro de asistencia')}</select></label>
    <label>Anfitrión previsto<select name="host">${options(Object.keys(people),account.value)}</select></label><label>Fecha prevista<input type="date" name="day" required value="2026-11-11"></label></div>
    <div id="opening" class="fields"></div><div class="actions"><button class="primary" value="start">Firmar e iniciar</button><button value="schedule">Guardar programada</button>${button('Volver','sessions')}</div></form>`;
  const form=document.querySelector('#create');
  const drawFields=()=>{document.querySelector('#opening').innerHTML=fields(form.elements.type.value,false);};
  drawFields();
  form.elements.type.onchange=drawFields;
  form.onsubmit=e=>{
    e.preventDefault();
    const {title,type,host,day,...fields}=Object.fromEntries(new FormData(form));
    selected={title,type,host,day,fields,theme:fields.Tema||fields['Tema o asunto']||'',state:'Programada',signed:0,count:0,notes:{},attendees:[]};
    sessions.unshift(selected);
    tab='Resumen y QR';
    show('detail');
    if(e.submitter.value==='start') hostDialog();
  };
}

function showDetail() {
  const s=selected;
  const list = s.attendees.map(a=>`<tr><td>${esc(a.name)}</td><td>${esc(a.rut)}</td><td>Asistente</td><td>${badge(a.state,a.state==='Firmado'?'green':'red')}</td></tr>`).join('');
  const notes = fields(s.type,true,s.notes);
  const sections={
    'Resumen y QR':`<div class="split"><section class="card"><div class="heading"><h2>Datos de la actividad</h2>${badge(s.state,s.state==='En curso'?'red':'')}</div>
    <dl><div><dt>Plantilla</dt><dd>${esc(s.type)}</dd></div><div><dt>Anfitrión a cargo</dt><dd>${esc(s.host)}</dd></div><div><dt>Inicio real</dt><dd>${esc(s.start||'Pendiente de firma del anfitrión')}</dd></div><div><dt>Término real</dt><dd>${esc(s.end||'—')}</dd></div>
    ${Object.entries(s.fields).filter(([,v])=>v).map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
    <div class="actions">${s.state==='Programada'?button('Confirmar anfitrión y firmar','host','primary'):s.state==='En curso'?button('Cerrar sesión','close-session'):''}</div></section>
    <section class="card qr"><h2>Código QR</h2><img src="qr-demo.png" alt="Código QR ilustrativo"><p class="hint">QR de muestra para revisar el afiche.</p><div class="actions">${button('Afiche PDF','poster','primary')}${button('Abrir vista del asistente','public')}</div></section></div>`,
    'Lista actual':`<section class="card table-card"><div class="toolbar"><h2>Lista actual</h2><span>${s.signed} firmados · ${s.count-s.signed} pendientes</span></div><div class="table-wrap"><table><thead><tr><th>Nombre</th><th>RUT</th><th>Participación</th><th>Firma</th></tr></thead><tbody>
    <tr><td><strong>${esc(s.host)}</strong></td><td>${esc((s.hostSnapshot||people[s.host])[0])}</td><td>Anfitrión · primera firma</td><td>${s.hostSignature?badge('Firmado','green'):badge('Pendiente de firma','red')}</td></tr>${list}</tbody></table></div>
    ${s.count>s.attendees.length?`<p class="toolbar hint">Se muestran ${s.attendees.length} registros de ejemplo del total indicado.</p>`:''}</section>`,
    'Desarrollo':`<form class="card" id="notes"><h2>Desarrollo de la actividad</h2><p>${esc(s.type)}</p><div class="fields">${notes || '<p class="wide">Esta plantilla no contiene campos de desarrollo.</p>'}</div>${notes?'<button class="primary">Guardar observaciones</button>':''}<p class="notice" role="status"></p></form>`,
    'Exportaciones':`<section class="card"><h2>Exportar esta sesión</h2><p>La firma del anfitrión encabeza la lista. El acceso depende del permiso y del alcance del rol.</p><div class="actions">${button('Exportar Excel con firmas','xlsx','primary')}${button('Exportar CSV','csv')}</div><p class="notice" role="status"></p></section>`,
  };
  if(!canExport())delete sections.Exportaciones;
  main.innerHTML=heading('Sesiones / Detalle',s.title,esc(s.theme||s.type),button('Volver a sesiones','sessions'))+
    `<div class="tabs" aria-label="Secciones de la actividad">${Object.keys(sections).map(x=>`<button data-tab="${x}" class="${x===tab?'active':''}">${x}</button>`).join('')}</div>${sections[tab]}`;
  const form=document.querySelector('#notes');
  if(form) form.onsubmit=e=>{e.preventDefault(); s.notes=Object.fromEntries(new FormData(form)); form.querySelector('.notice').textContent='Observaciones guardadas en esta demostración.';};
}

function signatureMarkup() {
  return '<canvas class="signature" aria-label="Área de firma manuscrita"></canvas><p class="notice" role="status"></p>';
}
function attachSignature(root) {
  const canvas=root.querySelector('canvas');
  const {width,height}=canvas.getBoundingClientRect();
  canvas.width=Math.round(width); canvas.height=Math.round(height);
  const pen=canvas.getContext('2d'); pen.lineWidth=2; pen.lineCap='round';
  let drawing=false, ink=false;
  canvas.onpointerdown=e=>{drawing=true; canvas.setPointerCapture(e.pointerId); pen.beginPath(); pen.moveTo(e.offsetX,e.offsetY);};
  canvas.onpointermove=e=>{if(drawing){pen.lineTo(e.offsetX,e.offsetY); pen.stroke(); ink=true;}};
  canvas.onpointerup=canvas.onpointercancel=()=>{drawing=false;};
  root.querySelector('[data-clear]').onclick=()=>{pen.clearRect(0,0,canvas.width,canvas.height); ink=false;};
  return ()=>ink ? canvas.toDataURL() : null;
}
function hostDialog() {
  document.querySelector('#dialogContent').innerHTML=`<form id="host-sign"><h2>Firma del anfitrión</h2><p>Confirma quién estará a cargo. Esta firma encabezará la lista.</p>
    <label>Anfitrión que inicia<select name="host">${options(Object.keys(people),selected.host)}</select></label><dl id="profile"></dl>${signatureMarkup()}<div class="actions"><button type="button" data-clear>Limpiar firma</button><button class="primary">Confirmar firma e iniciar</button>${button('Cancelar','dismiss')}</div></form>`;
  dialog.showModal();
  const form=document.querySelector('#host-sign');
  const profile=()=>{document.querySelector('#profile').innerHTML=labels.map((l,i)=>`<div><dt>${l}</dt><dd>${esc(people[form.elements.host.value][i])}</dd></div>`).join('');};
  profile(); form.elements.host.onchange=profile;
  const signature=attachSignature(form);
  form.onsubmit=e=>{
    e.preventDefault(); const data=signature();
    if(!data){form.querySelector('.notice').textContent='Dibuja la firma para iniciar.';return;}
    selected.host=form.elements.host.value; selected.hostSnapshot=[...people[selected.host]];
    selected.hostSignature=data; selected.start=stamp(); selected.state='En curso';
    dialog.close(); show('detail');
  };
}

function showPublic() {
  const s=publicSession||selected;
  let body;
  if(s.state!=='En curso') body=`<p>${s.state==='Programada'?'La actividad todavía no inicia.':'El registro de esta actividad está cerrado.'}</p>`;
  else if(publicRecord?.state==='Firmado') body='<p role="status">Asistencia confirmada. Tu firma quedó registrada en esta demostración.</p>';
  else if(publicRecord) body=`<form id="participant-sign"><h2>Firma de asistencia</h2><p>Dibuja tu firma en este recuadro.</p>${signatureMarkup()}<div class="signature-actions"><button type="button" data-clear>Limpiar firma</button><button class="primary">Confirmar firma</button></div></form>`;
  else body=`<form id="participant"><div class="fields">${labels.map((label,i)=>`<label>${label}<input name="field${i}" type="${i===4?'tel':i===5?'email':'text'}" ${i!==3?'required':''}></label>`).join('')}</div><button class="primary">Registrar y continuar a firma</button></form>`;
  main.innerHTML=`<div class="public"><p class="crumb">Vista del asistente</p><section class="card"><h1>${esc(s.title)}</h1><p>${esc(s.type)} · ${dateLabel(s.day)}</p>${body}</section></div>`;
  const form=document.querySelector('#participant');
  if(form) form.onsubmit=e=>{
    e.preventDefault(); const f=new FormData(form);
    publicRecord={name:[1,2,3].map(i=>f.get('field'+i).trim()).filter(Boolean).join(' '),rut:f.get('field0').trim(),state:'Pendiente de firma'};
    s.attendees.push(publicRecord); s.count++; show('public');
  };
  const sign=document.querySelector('#participant-sign');
  if(sign){
    const getSignature=attachSignature(sign);
    sign.onsubmit=e=>{
      e.preventDefault(); const image=getSignature();
      if(!image){sign.querySelector('.notice').textContent='Dibuja tu firma antes de confirmar.';return;}
      publicRecord.signature=image; publicRecord.state='Firmado'; s.signed++; show('public');
    };
  }
}

function showRoles() {
  const currentRole = users[inspectedUser];
  const permissions = roles[currentRole];
  const actions = [
    ['Consultar sesiones propias',true],
    ['Crear sesiones',permissions.includes('Crear sesiones')],
    ['Exportar sesiones propias',permissions.includes('Exportar propias') || permissions.includes('Consultar y exportar todas')],
    ['Consultar y exportar sesiones ajenas',permissions.includes('Consultar y exportar todas')],
    ['Administrar roles y permisos',inspectedUser===baseAccount],
  ];
  main.innerHTML=heading('Registro de asistencia','Roles y permisos','El superusuario base configura los roles y los asigna a otras cuentas.')+
    `<div class="split"><form id="role" class="card"><h2>Configurar rol</h2><label>Nombre del rol<input name="role" required placeholder="Ej. Docente"></label>
    <div class="fields">${roles.Superusuario.filter(permission=>permission!=='Gestionar roles').map(permission=>`<label class="check"><input type="checkbox" name="permissions" value="${permission}">${permission}</label>`).join('')}</div>
    <div class="actions"><button class="primary">Guardar rol</button></div><p class="notice" role="status"></p></form>
    <section class="card"><h2>Usuarios registrados</h2><label>Usuario<select id="inspected-user">${options(Object.keys(users),inspectedUser)}</select></label>
    <p class="hint">Rol actual: ${esc(currentRole)}</p>
    <div class="table-wrap"><table><thead><tr><th>Acción</th><th>Acceso</th></tr></thead><tbody>
    ${actions.map(([label,enabled])=>`<tr><td>${label}</td><td>${badge(enabled?'Permitido':'Sin permiso',enabled?'green':'')}</td></tr>`).join('')}
    </tbody></table></div>
    ${inspectedUser===baseAccount?'<p class="hint">Rol fijo del superusuario base.</p>':`<form id="assign"><label>Rol que se asignará<select name="role">${options(Object.keys(roles).filter(role=>role!=='Superusuario'),currentRole)}</select></label><button class="primary assign-button">Asignar rol</button></form>`}</section></div>
    <section class="card"><h2>Roles disponibles</h2>
    <div class="role-overview">
      <label>Rol<select id="inspected-role">${options(Object.keys(roles),inspectedRole)}</select></label>
      <div><h3>Permisos del rol</h3><ul id="role-permissions" aria-live="polite"></ul></div>
    </div></section>`;
  const roleSelector = document.querySelector('#inspected-role');
  const permissionList = document.querySelector('#role-permissions');
  const displayPermissions = () => {
    const granted = ['Consultar sesiones propias', ...roles[inspectedRole]];
    permissionList.innerHTML = granted.map(permission => `<li>${esc(permission)}</li>`).join('');
  };
  displayPermissions();
  roleSelector.onchange = event => {
    inspectedRole = event.target.value;
    displayPermissions();
  };
  document.querySelector('#role').onsubmit=e=>{
    e.preventDefault(); if(!isSuperuser())return;
    const data=new FormData(e.target), role=data.get('role').trim();
    if(!role || role.toLowerCase()==='superusuario'){e.target.querySelector('.notice').textContent='Escribe un nombre distinto para el rol configurable.';return;}
    const permissions=data.getAll('permissions').filter(permission=>permission!=='Gestionar roles' && roles.Superusuario.includes(permission));
    Object.defineProperty(roles,role,{value:permissions,enumerable:true,configurable:true,writable:true}); show('roles');
  };
  document.querySelector('#inspected-user').onchange=e=>{
    inspectedUser=e.target.value;
    show('roles');
    document.querySelector('#inspected-user').focus();
  };
  const assignmentForm=document.querySelector('#assign');
  if(assignmentForm)assignmentForm.onsubmit=e=>{
    e.preventDefault();
    const role=new FormData(e.target).get('role');
    if(!isSuperuser() || inspectedUser===baseAccount || role==='Superusuario' || !Object.hasOwn(roles,role))return;
    users[inspectedUser]=role;
    show('roles');
  };
}

function poster() {
  const s=selected;
  document.querySelector('.afiche')?.remove();
  const print=document.createElement('section');
  print.className='afiche';
  print.innerHTML=`<strong>INACAP · Registro de asistencia</strong><h1>${esc(s.title)}</h1><p>${esc(s.theme||s.type)}</p>
    <p>${dateLabel(s.day)} · ${esc(s.fields.Lugar||s.fields['Lugar de uso']||'')}<br>Anfitrión: ${esc(s.host)}</p>
    <img src="qr-demo.png" alt="QR ilustrativo"><p>Escanea el código, registra tus datos y firma en tu dispositivo.</p><p><small>Propuesta visual · QR de muestra</small></p>`;
  document.body.append(print);
  document.querySelector('#dialogContent').innerHTML=`<h2>Afiche de asistencia</h2><p>${esc(s.title)}</p><p>En la ventana de impresión, elige «Guardar como PDF».</p><div class="actions">${button('Imprimir o guardar PDF','print','primary')}${button('Volver','dismiss')}</div>`;
  dialog.showModal();
}

document.addEventListener('click',e=>{
  const target=e.target.closest('button');
  if(!target)return;
  const {view,action,scope:nextScope,tab:nextTab}=target.dataset;
  if(nextScope){scope=nextScope;show('sessions');return;}
  if(nextTab){tab=nextTab;show('detail');return;}
  if(view==='public'||action==='public'){
    if(publicSession!==selected){publicSession=selected;publicRecord=null;}
    show('public');return;
  }
  if(view||action==='sessions'||action==='create'){show(view||action);return;}
  if(action?.startsWith('open-')){selected=sessions[Number(action.slice(5))];tab='Resumen y QR';show('detail');return;}
  if(action==='clear-filters'){filter={};show('sessions');}
  if(action==='host')hostDialog();
  if(action==='dismiss')dialog.close();
  if(action==='poster')poster();
  if(action==='print')window.print();
  if(action==='close-session'){
    document.querySelector('#dialogContent').innerHTML=`<h2>¿Cerrar esta sesión?</h2><p>Se registrará la hora de término y se cerrará el formulario de asistencia.</p><div class="actions">${button('Cerrar sesión','confirm-close','primary')}${button('Cancelar','dismiss')}</div>`;
    dialog.showModal();
  }
  if(action==='confirm-close'){selected.state='Finalizada';selected.end=stamp();dialog.close();show('detail');}
  if((action==='xlsx'||action==='csv') && canExport())main.querySelector('.notice').textContent=`Vista previa de exportación ${action.toUpperCase()}. La descarga de registros se conectará en Django.`;
});
account.innerHTML=options(Object.keys(users),baseAccount);
show('sessions');
