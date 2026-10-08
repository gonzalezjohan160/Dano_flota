# ===========================================
# Script: start_venv.ps1
# Descripción: Crea y activa el entorno virtual con Python embebido.
# ===========================================

# Ruta al Python embebido (ajusta si lo pusiste en otro lugar)
$pythonPath = "C:\Users\em00084\Downloads\Python312\python.exe"
$venvPath = "C:\Users\em00084\Downloads\Dano_flota\venv"

# Verificar que el Python embebido existe
if (-Not (Test-Path $pythonPath)) {
    Write-Host "❌ No se encontró Python en: $pythonPath"
    Write-Host "Asegúrate de haber descomprimido el paquete embebido."
    exit
}

# Crear venv si no existe
if (-Not (Test-Path "$venvPath\Scripts\Activate.ps1")) {
    Write-Host "🧱 Creando entorno virtual..."
    & $pythonPath -m venv $venvPath
}

# Activar el entorno
Write-Host "🚀 Activando entorno virtual..."
& "$venvPath\Scripts\Activate.ps1"

# Mostrar versión de Python
python --version
