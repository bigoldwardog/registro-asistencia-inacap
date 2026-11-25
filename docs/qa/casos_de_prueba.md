
# Casos de prueba - Registro de Asistencia INACAP

## 1. Objetivo

Verificar el correcto funcionamiento del sistema de registro
de asistencia, identificando errores funcionales, problemas
de validación, seguridad y usabilidad.

## 2. Alcance

- Inicio y cierre de sesión.
- Gestión de cuentas.
- Validación de RUT.
- Registro de asistencia.
- Firmas digitales.
- Generación de códigos QR.
- Roles y permisos.
- Exportación de documentos.

## 3. Matriz de casos de prueba

| ID | Módulo | Acción de prueba | Resultado esperado | Prioridad | Estado |
|---|---|---|---|---|---|
| CP-001 | Login | Ingresar credenciales correctas | Acceso permitido | Alta | Pendiente |
| CP-002 | Login | Ingresar contraseña incorrecta | Acceso rechazado | Alta | Pendiente |
| CP-003 | Login | Dejar campos vacíos | Mostrar validación | Media | Pendiente |
| CP-004 | Login | Cerrar sesión | Finalizar sesión correctamente | Alta | Pendiente |
| CP-005 | Mi cuenta | Modificar datos válidos | Guardar cambios | Media | Pendiente |
| CP-006 | Contraseña | Ingresar contraseña actual incorrecta | Rechazar modificación | Alta | Pendiente |
| CP-007 | Contraseña | Ingresar contraseñas nuevas diferentes | Mostrar error | Alta | Pendiente |
| CP-008 | RUT | Ingresar 123456785 | Formatear como 12.345.678-5 | Media | Pendiente |
| CP-009 | RUT | Ingresar 12.345.678-9 | Rechazar RUT inválido | Alta | Pendiente |
| CP-010 | Asistencia | Repetir RUT en una sesión | Impedir registro duplicado | Alta | Pendiente |
| CP-011 | Sesión | Programar sesión con datos válidos | Crear sesión correctamente | Alta | Pendiente |
| CP-012 | Sesión | Intentar iniciar sin firma del anfitrión | Impedir inicio | Alta | Pendiente |
| CP-013 | QR | Escanear QR de sesión activa | Abrir formulario correspondiente | Alta | Pendiente |
| CP-014 | Asistencia | Registrar asistentes desde dos celulares | Guardar ambos registros | Alta | Pendiente |
| CP-015 | Firma | Enviar firma vacía | Rechazar registro | Alta | Pendiente |
| CP-016 | Sesión | Registrar asistencia después del cierre | Bloquear registro | Alta | Pendiente |
| CP-017 | Permisos | Acceder a administración sin autorización | Denegar acceso | Alta | Pendiente |
| CP-018 | Exportación | Descargar archivo Excel | Generar archivo válido | Media | Pendiente |
| CP-019 | Exportación | Descargar archivo PDF | Generar documento válido | Media | Pendiente |
| CP-020 | EPP | Registrar firmas de recepción y devolución | Conservar ambas firmas | Alta | Pendiente |

## 4. Estados de evaluación

- Pendiente: prueba todavía no ejecutada.
- Aprobado: resultado obtenido coincide con el esperado.
- Fallido: resultado obtenido no coincide con el esperado.
- Bloqueado: existe una condición que impide ejecutar la prueba.

## 5. Registro de errores

| ID error | Caso asociado | Descripción | Evidencia | Severidad | Estado |
|---|---|---|---|---|---|

Los errores serán registrados después de ejecutar las pruebas
y comprobar que pueden reproducirse.

## 6. Evidencias

Las evidencias deberán incluir:

- Identificador del caso de prueba.
- Captura de pantalla.
- Fecha de ejecución.
- Resultado esperado.
- Resultado obtenido.
- Navegador y dispositivo utilizado.

## 7. Resumen inicial

- Total de casos: 20.
- Aprobados: 0.
- Fallidos: 0.
- Pendientes: 20.
- Bloqueados: 0.

## 8. Conclusión

Se establece una matriz inicial de pruebas funcionales,
negativas y de validación para facilitar la identificación
de errores y mejorar la calidad del sistema.

Los resultados se actualizarán conforme se ejecuten las pruebas.
