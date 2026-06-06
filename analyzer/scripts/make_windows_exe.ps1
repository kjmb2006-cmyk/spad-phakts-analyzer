<#
SPAD Analyzer — Packaging PowerShell helper (PyInstaller)
Usage: Exécutez depuis PowerShell en mode Administrateur si nécessaire:
  .\scripts\make_windows_exe.ps1

Le script crée un venv, installe PyInstaller et génère dist\SPAD_Analyzer.exe
#>

Write-Host "======================================================="
Write-Host "  SPAD Analyzer — Packaging for Windows (PowerShell)"
Write-Host "======================================================="

# Move to repository root (script located in scripts\)
Set-Location -Path (Split-Path -Path $MyInvocation.MyCommand.Path -Parent)
Set-Location -Path ..

# Ensure Python exists
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python introuvable. Installez Python et ajoutez-le au PATH."
    exit 1
}

# Create venv if missing
if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "→ Création de l'environnement virtuel..."
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Impossible de créer le venv."
        exit 1
    }
}

# Activate venv
Write-Host "→ Activation du venv..."
& .\venv\Scripts\Activate.ps1

if ($?) {
    Write-Host "→ Installation des dépendances et PyInstaller..."
    pip install -r requirements.txt pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Échec de l'installation des paquets."
        exit 1
    }

    Write-Host "→ Lancement de PyInstaller (cela peut prendre quelques minutes)..."
    pyinstaller --noconfirm --onefile --name SPAD_Analyzer `
        --add-data "templates;templates" `
        --add-data "static;static" `
        --add-data "modules;modules" `
        --add-data "data;data" `
        run.py

    if (Test-Path "dist\SPAD_Analyzer.exe") {
        Write-Host "✅ Build terminé : dist\SPAD_Analyzer.exe"
    } else {
        Write-Error "Build échoué. Vérifiez les logs PyInstaller dans le dossier 'build'."
        exit 1
    }

    Write-Host "→ Désactivation du venv"
    & Deactivate
} else {
    Write-Error "Impossible d'activer le venv. Exécutez PowerShell en tant qu'administrateur si nécessaire."
    exit 1
}

exit 0
