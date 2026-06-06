# SPAD Analyzer — PowerShell Startup Script (Windows)
# Utilisez ce script si start.bat ne fonctionne pas
# Exécutez avec : powershell -ExecutionPolicy Bypass -File start.ps1

param(
    [switch]$NoBrowser
)

Write-Host "======================================================="
Write-Host "  SPAD Analyzer — Démarrage (PowerShell)"
Write-Host "======================================================="
Write-Host ""

# Change to script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Check if venv exists
$venvPython = Join-Path $scriptDir "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "→ Création de l'environnement virtuel..."

    # Try different Python commands
    $pythonCmd = $null
    $pythonCandidates = @(
        @{ cmd = "python"; args = "--version" },
        @{ cmd = "py"; args = "--version" },
        @{ cmd = "py"; args = "-3 --version" },
        @{ cmd = "python3"; args = "--version" },
        @{ cmd = "python3.12"; args = "--version" },
        @{ cmd = "python3.11"; args = "--version" }
    )

    $pythonArgs = @()
    foreach ($candidate in $pythonCandidates) {
        try {
            $cmd = $candidate.cmd
            $args = $candidate.args.Split(' ')
            $process = & $cmd @args 2>$null
            if ($LASTEXITCODE -eq 0) {
                $pythonCmd = $cmd
                $pythonArgs = $args
                Write-Host "→ Utilisation de : $cmd $($args -join ' ') ($process)"
                break
            }
        } catch {
            continue
        }
    }

    if (-not $pythonCmd) {
        Write-Host "ERREUR: Python n'est pas trouvé dans le PATH." -ForegroundColor Red
        Write-Host ""
        Write-Host "Solutions :" -ForegroundColor Yellow
        Write-Host "1. Installez Python 3.10+ depuis https://www.python.org"
        Write-Host "2. Cochez 'Add Python to PATH' pendant l'installation"
        Write-Host "3. Ou exécutez manuellement :"
        Write-Host "   python -m venv venv"
        Write-Host "   venv\Scripts\activate"
        Write-Host "   pip install -r requirements.txt"
        Write-Host "   python run.py"
        Read-Host "Appuyez sur Entrée pour quitter"
        exit 1
    }

    # Create venv
    $venvArgs = $pythonArgs + @('-m', 'venv', 'venv')
    & $pythonCmd @venvArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERREUR: Impossible de créer l'environnement virtuel." -ForegroundColor Red
        Read-Host "Appuyez sur Entrée pour quitter"
        exit 1
    }

    # Install dependencies
    Write-Host "→ Installation des dépendances (patientez ~2 min)..."
    & "venv\Scripts\pip" install -r requirements.txt -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERREUR: Impossible d'installer les dépendances." -ForegroundColor Red
        Write-Host "→ Essayez manuellement : venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
        Read-Host "Appuyez sur Entrée pour quitter"
        exit 1
    }
}

# Check if run.py exists
if (-not (Test-Path "run.py")) {
    Write-Host "ERREUR: Fichier run.py introuvable dans $scriptDir" -ForegroundColor Red
    Read-Host "Appuyez sur Entrée pour quitter"
    exit 1
}

Write-Host ""
Write-Host "======================================================="
Write-Host "  SPAD Analyzer — Démarrage"
Write-Host "======================================================="
if (-not $NoBrowser) {
    Write-Host "  → Navigateur s'ouvre automatiquement..."
}
Write-Host "  → Appuyez sur Ctrl+C pour arrêter"
Write-Host "======================================================="
Write-Host ""

# Launch the application
try {
    & "venv\Scripts\python" run.py
} catch {
    Write-Host "ERREUR: Impossible de lancer l'application : $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Appuyez sur Entrée pour quitter"
}

Read-Host "Appuyez sur Entrée pour quitter"