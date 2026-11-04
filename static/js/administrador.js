let sessions = [], filteredSessions = [], currentDetail = null;
const $ = id => document.getElementById(id);
async function api(url) {
    const response = await fetch(url);
    if (response.status === 401) { location.assign('/ingresar/'); throw new Error('Inicia sesión para continuar.'); }
    if (!response.ok) { const data = await response.json(); throw new Error(data.error || 'No se pudo completar la operación.'); }
    return response;
}
function formatDate(value) { return value ? new Date(value).toLocaleString('es-CL', {timeZone:'America/Santiago'}) : '—'; }
function appendCell(row, text) { const cell = document.createElement('td'); cell.textContent = text ?? '—'; row.append(cell); return cell; }
function populateFilters() {
    for (const [id,key] of [['filter-type','plantilla'],['filter-host','anfitrion']]) {
        const select = $(id), value = select.value;
        select.replaceChildren(new Option('Todos',''));
        [...new Set(sessions.map(s=>s[key]))].sort().forEach(v=>select.add(new Option(v,v)));
        if ([...select.options].some(option=>option.value===value)) select.value=value;
    }
}
function applyFilters() {
    const from=$('filter-date-from').value, to=$('filter-date-to').value;
    if (from && to && from>to) { $('filter-error').hidden=false; $('filter-error').textContent='La fecha inicial no puede ser posterior a la final.'; return; }
    $('filter-error').hidden=true;
    filteredSessions=sessions.filter(s=>(!$('filter-type').value||s.plantilla===$('filter-type').value)&&(!$('filter-host').value||s.anfitrion===$('filter-host').value)&&(!from||s.fecha_local>=from)&&(!to||s.fecha_local<=to));
    const body=$('sessions-table-body');body.replaceChildren();
    for(const s of filteredSessions){
        const row=document.createElement('tr');row.tabIndex=0;row.setAttribute('role','button');row.setAttribute('aria-label',`Ver ${s.nombre}`);row.className='clickable-session';
        [s.nombre,s.plantilla,s.fecha_local?s.fecha_local.split('-').reverse().join('-'):'Sin fecha',s.anfitrion,s.total_asistencias,s.total_firmadas,s.total_pendientes].forEach(v=>appendCell(row,v));
        row.addEventListener('click',()=>openSessionDetail(s));row.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();openSessionDetail(s);}});body.append(row);
    }
    $('results-count').textContent=`${filteredSessions.length} sesiones`;
    $('empty-message').hidden=filteredSessions.length>0;
}
async function loadSessions(){
    $('results-count').textContent='Cargando…';
    try{
        const response=await api(`/api/administrador/historial/?q=${encodeURIComponent($('filter-person').value.trim())}`);
        sessions=(await response.json()).sesiones;populateFilters();applyFilters();
    }catch(error){$('results-count').textContent='No se pudo cargar';$('empty-message').hidden=false;$('empty-message').textContent=error.message;}
}
$('filters-form').addEventListener('submit',event=>{event.preventDefault();loadSessions();});
$('clear-filters').addEventListener('click',()=>{$('filters-form').reset();loadSessions();});
function signatureButton(cell, attendee, type, label){
    const button=document.createElement('button');button.type='button';button.className='secondary-button';button.textContent=label;
    button.addEventListener('click',()=>{
        $('signature-preview-title').textContent=`${label}: ${attendee.nombre}`;
        $('signature-preview-image').src=`/api/asistencias/${attendee.id}/imagen/${type}/`;
        $('signature-preview-dialog').showModal();
    });cell.append(button);
}
async function openSessionDetail(session){
    currentDetail=session;
    document.querySelector('.history-section').hidden=true;$('session-detail-section').hidden=false;
    $('detail-session-title').textContent=session.nombre;
    $('detail-session-info').textContent=`${session.plantilla} · ${session.anfitrion} · ${session.estado}`;
    $('detail-feedback').hidden=false;$('detail-feedback').textContent='Cargando asistentes…';
    $('attendees-table-body').replaceChildren();
    try{
        const response=await api(`/api/sesiones/${session.id}/asistencias/lista/`);const data=await response.json();
        if(currentDetail.id!==session.id)return;
        const fields=data.sesion.campos_asistente;
        const headers=[...fields.map(f=>f.etiqueta),'Registro (Chile)','Estado','Recepción / asistencia'];
        if(data.sesion.es_epp)headers.push('Devolución EPP');
        if(data.sesion.es_panol)headers.push('Firma docente');
        const heading=$('attendees-table-head');heading.replaceChildren();
        for(const label of headers){const th=document.createElement('th');th.textContent=label;heading.append(th);}
        for(const a of data.asistencias){
            const row=document.createElement('tr');
            for(const f of fields)appendCell(row,a.campos[f.nombre]||a[f.nombre]||'—');
            appendCell(row,formatDate(a.fecha_registro));
            appendCell(row,a.estado==='FIRMADO'?'Firmado':a.estado==='ANULADO'?'Anulado':'Pendiente');
            const primary=appendCell(row,'');
            if(a.tiene_firma){signatureButton(primary,a,'recepcion','Ver firma');const date=document.createElement('p');date.textContent=formatDate(a.fecha_firma);primary.append(date);}else primary.textContent='Pendiente';
            if(data.sesion.es_epp){const cell=appendCell(row,'');if(a.devolucion_firmada){signatureButton(cell,a,'devolucion','Ver devolución');const date=document.createElement('p');date.textContent=formatDate(a.fecha_firma_devolucion);cell.append(date);}else cell.textContent='Pendiente';}
            if(data.sesion.es_panol){const cell=appendCell(row,'');if(a.docente_firmado){signatureButton(cell,a,'docente','Ver firma docente');const date=document.createElement('p');date.textContent=formatDate(a.fecha_firma_docente);cell.append(date);}else cell.textContent='Pendiente';}
            $('attendees-table-body').append(row);
        }
        const details=$('detail-activity-fields');details.replaceChildren();
        for(const [label,value] of [['Inicio',formatDate(data.sesion.fecha_inicio)],['Término',formatDate(data.sesion.fecha_cierre)],...(data.sesion.campos_definicion||[]).map(f=>[f.etiqueta,data.sesion.campos[f.nombre]])]){
            if(!value)continue;const group=document.createElement('div');const term=document.createElement('dt');term.textContent=label;const text=document.createElement('dd');text.textContent=value;group.append(term,text);details.append(group);
        }
        $('attendees-empty-message').hidden=data.asistencias.length>0;$('detail-feedback').hidden=true;
        $('admin-audit-results').replaceChildren();
    }catch(error){$('detail-feedback').textContent=error.message;}
}
$('back-to-history').addEventListener('click',()=>{$('session-detail-section').hidden=true;document.querySelector('.history-section').hidden=false;currentDetail=null;});
async function exportData(format,detail=false){
    const ids=detail&&currentDetail?[currentDetail.id]:filteredSessions.map(s=>s.id);
    const feedback=detail?$('detail-feedback'):$('export-feedback');feedback.hidden=false;
    if(!ids.length){feedback.textContent='No hay sesiones para exportar.';return;}
    feedback.textContent='Preparando el archivo con asistentes y datos de la actividad…';
    try{
        const response=await api(`/api/administrador/exportar/${format}/?sesiones=${ids.join(',')}`);
        const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');
        link.href=url;link.download=`registros-asistencia.${format}`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        feedback.textContent=format==='xlsx'?'Excel generado con datos y firmas disponibles.':'CSV generado con los datos de asistentes. Las imágenes de firmas se incluyen en Excel.';
    }catch(error){feedback.textContent=error.message;}
}
$('export-csv').addEventListener('click',()=>exportData('csv'));$('export-xlsx').addEventListener('click',()=>exportData('xlsx'));
$('detail-export-csv').addEventListener('click',()=>exportData('csv',true));$('detail-export-xlsx').addEventListener('click',()=>exportData('xlsx',true));
$('admin-load-audit').addEventListener('click',async()=>{
    if(!currentDetail)return;const id=currentDetail.id,results=$('admin-audit-results');results.textContent='Cargando…';
    try{const data=await(await api(`/api/sesiones/${id}/historial/`)).json();if(currentDetail?.id!==id)return;results.replaceChildren();
        for(const row of data.historial){const item=document.createElement('details'),title=document.createElement('summary'),text=document.createElement('pre');title.textContent=`${formatDate(row.fecha)} · ${row.usuario} · ${row.accion.replaceAll('_',' ')}`;text.textContent=JSON.stringify({antes:row.anteriores,después:row.nuevos},null,2);item.append(title,text);results.append(item);}
        if(!data.historial.length)results.textContent='Sin cambios registrados.';
    }catch(error){results.textContent=error.message;}
});
loadSessions();

// Cierre explícito para que los cuadros también funcionen en navegadores embebidos.
for (const button of document.querySelectorAll('dialog form[method="dialog"] button')) {
    button.type = 'button';
    button.addEventListener('click', () => button.closest('dialog').close(button.value || 'cancel'));
}
