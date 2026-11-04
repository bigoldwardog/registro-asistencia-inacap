$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno virtual.' }
}
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'asistencia.db')) {
    & $pythonPath -c "import sqlite3, datetime; from pathlib import Path; p=Path('asistencia.db'); b=p.with_name('asistencia-respaldo-instalacion-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db'); src=sqlite3.connect(str(p)); dst=sqlite3.connect(str(b)); src.backup(dst); dst.close(); src.close(); print('Respaldo creado:', b)"
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo respaldar la base. No se continuara.' }
}
& $pythonPath -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
& $pythonPath manage.py preparar_sistema
if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar el esquema.' }
Write-Host 'Instalacion completa. Ejecuta .\INICIAR_LOCAL.ps1.'
Write-Host 'En el primer uso abre http://127.0.0.1:8000/configuracion-inicial/ desde este computador.'
