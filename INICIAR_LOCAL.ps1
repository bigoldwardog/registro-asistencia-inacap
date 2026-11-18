$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'No se encuentra .venv\Scripts\python.exe. Debes configurar el entorno virtual del proyecto.'
}
& $pythonPath manage.py preparar_sistema
if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar la base de datos. No se inicio el servidor.' }
$addresses = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' -and $_.AddressState -eq 'Preferred'
} | Select-Object -ExpandProperty IPAddress -Unique)
$env:DJANGO_ALLOWED_HOSTS = (@($env:DJANGO_ALLOWED_HOSTS) + $addresses) -join ','
Write-Host 'Primer acceso: http://127.0.0.1:8000/configuracion-inicial/ (crear administrador)'
Write-Host 'Conecta el celular y el computador a la misma red.'
Write-Host 'Abre el panel usando la IP de tu conexion Wi-Fi o Ethernet:'
foreach ($address in $addresses) {
    Write-Host "http://${address}:8000/anfitrion/"
}
Write-Host 'Evita localhost al generar el QR. Deten el servidor con Ctrl+C.'
& $pythonPath manage.py runserver 0.0.0.0:8000
