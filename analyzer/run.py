#!/usr/bin/env python3
"""
SPAD Analyzer — Script de démarrage
Usage : venv/bin/python run.py  ou  double-clic sur start.command (macOS) / start.bat (Windows)
"""
import sys, os, threading, time, subprocess, platform

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

from app import app


def open_browser(port):
    """Attend que Flask soit prêt puis ouvre un navigateur (multiplateforme)."""
    time.sleep(2)
    url = f"http://127.0.0.1:{port}"
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            # Essayer d'ouvrir un nouvel onglet Chrome via AppleScript
            try:
                script = f'''
                tell application "Google Chrome"
                    activate
                    if (count of windows) = 0 then
                        make new window
                    end if
                    set newTab to make new tab at end of tabs of front window
                    set URL of newTab to "{url}"
                    set active tab index of front window to index of newTab
                end tell
                '''
                subprocess.run(["osascript", "-e", script],
                               capture_output=True, timeout=10)
            except Exception:
                # Fallback : ouvre avec la commande open de macOS
                subprocess.run(["open", "-a", "Google Chrome", url],
                               capture_output=True, timeout=10)
        elif system == "Windows":  # Windows
            os.startfile(url)
        else:  # Linux et autres
            try:
                subprocess.Popen(["xdg-open", url])
            except Exception:
                try:
                    subprocess.Popen(["sensible-browser", url])
                except Exception:
                    pass
    except Exception:
        # Dernière tentative : utiliser webbrowser (très fiable)
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    headless = os.environ.get('HEADLESS', '0') == '1'

    print()
    print("=" * 55)
    print("  SPAD Analyzer — Analyse des données d'enquête")
    print("=" * 55)
    print(f"  → http://127.0.0.1:{port}")
    if headless:
        print("  → Mode embarqué (Electron) — pas d'ouverture navigateur")
    else:
        print("  → Ctrl+C pour arrêter")
    print("=" * 55)
    print()

    if not headless:
        t = threading.Thread(target=open_browser, args=(port,), daemon=True)
        t.start()

    app.run(debug=False, port=port, host='127.0.0.1', use_reloader=False)

