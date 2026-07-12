// ─────────────────────────────────────────────────────────────────────────────
//  SPAD PHAKTS Analyzer — Electron Main Process
//  Orchestrates two backend servers:
//    • Express API (Node)  → PHAKTS conception / XLSForm
//    • Flask  (Python)     → SPAD statistical analysis
// ─────────────────────────────────────────────────────────────────────────────

const { app, BrowserWindow, shell, dialog, ipcMain } = require("electron");
const path = require("path");
const fs = require("fs");
const net = require("net");
const http = require("http");
const { spawn } = require("child_process");

// ── Debug log file (always available, even in .app where stdout is dropped) ──
const _debugLogPath = path.join(app.getPath("userData"), "main-process.log");
try { fs.mkdirSync(path.dirname(_debugLogPath), { recursive: true }); } catch (_) {}
const _debugLog = fs.createWriteStream(_debugLogPath, { flags: "a" });
const _origLog = console.log.bind(console);
const _origErr = console.error.bind(console);
console.log = (...args) => { try { _debugLog.write("[log] " + args.join(" ") + "\n"); } catch (_) {} _origLog(...args); };
console.error = (...args) => { try { _debugLog.write("[err] " + args.join(" ") + "\n"); } catch (_) {} _origErr(...args); };
console.log(`=== boot ${new Date().toISOString()} ===`);

// ── Paths ────────────────────────────────────────────────────────────────────
// In packaged mode, electron-main.js lives inside app.asar; using __dirname is
// the only path that asar's fs hook resolves correctly.
const IS_PACKAGED = app.isPackaged;
const APP_ROOT = __dirname;

// extraResources (analyzer, python-embed, .env) sit alongside app.asar
const RES_ROOT = IS_PACKAGED ? process.resourcesPath : APP_ROOT;
const ANALYZER_DIR = path.join(RES_ROOT, "analyzer");

// Load .env: in packaged mode it lives in resources/ (bundled at build time);
// in dev it lives at the repo root.
const envPath = IS_PACKAGED
  ? path.join(process.resourcesPath, ".env")
  : path.join(APP_ROOT, ".env");

// override:true so values in .env beat empty/stale shell vars inherited from
// whichever terminal the user launched the app from.
if (fs.existsSync(envPath)) {
  require("dotenv").config({ path: envPath, override: true });
} else {
  require("dotenv").config({ path: path.join(APP_ROOT, ".env"), override: true });
}

// ── Port management ──────────────────────────────────────────────────────────
let nodePort = parseInt(process.env.PORT, 10) || 8080;
let flaskPort = parseInt(process.env.SPAD_PORT, 10) || 5050;

function isPortFree(port) {
  return new Promise((resolve) => {
    const tester = net.createServer()
      .once("error", () => resolve(false))
      .once("listening", () => { tester.close(); resolve(true); })
      .listen(port, "127.0.0.1");
  });
}

async function findFreePort(startPort) {
  for (let p = startPort; p < startPort + 20; p++) {
    if (await isPortFree(p)) return p;
  }
  return startPort + 100;
}

function waitForHttp(url, timeoutMs = 20000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(url, (res) => {
        res.resume();
        // Any HTTP response means the server is up
        resolve();
      });
      req.on("error", () => {
        if (Date.now() - start > timeoutMs) {
          reject(new Error(`Timeout waiting for ${url}`));
        } else {
          setTimeout(tick, 400);
        }
      });
      req.setTimeout(2000, () => req.destroy());
    };
    tick();
  });
}

// ── Express (Node) server — in-process ───────────────────────────────────────
function startNodeServer() {
  return new Promise(async (resolve, reject) => {
    try {
      nodePort = await findFreePort(nodePort);
      process.env.PORT = String(nodePort);
      process.env.HOST = "127.0.0.1";

      // User-writable data dirs (asar is read-only when packaged)
      const userData = app.getPath("userData");
      const dataDir = path.join(userData, "data");
      const uploadDir = path.join(userData, "uploads");
      try { fs.mkdirSync(dataDir, { recursive: true }); } catch (_) {}
      try { fs.mkdirSync(uploadDir, { recursive: true }); } catch (_) {}
      process.env.PHAKTS_DATA_DIR = dataDir;
      process.env.PHAKTS_UPLOAD_DIR = uploadDir;

      const serverPath = path.join(APP_ROOT, "api", "server.js");
      try {
        require(serverPath);
      } catch (e) {
        console.error("[node] require failed:", e.stack || e.message);
        return reject(e);
      }

      waitForHttp(`http://127.0.0.1:${nodePort}/`)
        .then(() => resolve(nodePort))
        .catch(reject);
    } catch (err) {
      reject(err);
    }
  });
}

// ── Flask (Python) server — sub-process ──────────────────────────────────────
let flaskProcess = null;

function resolvePythonBin() {
  const isWin = process.platform === "win32";

  // 1. Explicit override via PYTHON_BIN in .env (works packaged + dev)
  const envBin = process.env.PYTHON_BIN;
  if (envBin && fs.existsSync(envBin)) return envBin;

  // 2. Packaged mode: try bundled python-embed
  if (IS_PACKAGED) {
    const embeddedPy = isWin
      ? path.join(RES_ROOT, "python", "python.exe")
      : path.join(RES_ROOT, "python", "bin", "python3");
    if (fs.existsSync(embeddedPy)) return embeddedPy;

    // 3. Fallback: common macOS/Linux Python locations
    const fallbacks = isWin ? [] : [
      "/opt/homebrew/bin/python3.12",
      "/usr/local/bin/python3.12",
      "/opt/homebrew/bin/python3",
      "/usr/local/bin/python3",
      "/usr/bin/python3",
    ];
    for (const p of fallbacks) {
      if (fs.existsSync(p)) return p;
    }
    return "python3";
  }

  // Dev mode: prefer the venv inside analyzer/, then fall back to system python3
  const venvPython = isWin
    ? path.join(ANALYZER_DIR, "venv", "Scripts", "python.exe")
    : path.join(ANALYZER_DIR, "venv", "bin", "python3");
  if (fs.existsSync(venvPython)) return venvPython;
  return "python3";
}

function startFlaskServer() {
  return new Promise(async (resolve, reject) => {
    try {
      flaskPort = await findFreePort(flaskPort);
      const pythonBin = resolvePythonBin();
      const runScript = path.join(ANALYZER_DIR, "run.py");

      if (!fs.existsSync(runScript)) {
        return reject(new Error(`Analyzer entry point not found: ${runScript}`));
      }

      // User-writable data dir for SPAD uploads/reports (asar / read-only bundles)
      const spadUserData = path.join(app.getPath("userData"), "spad");
      try { fs.mkdirSync(spadUserData, { recursive: true }); } catch (_) {}

      // -u forces unbuffered I/O (more reliable than PYTHONUNBUFFERED on
      // Python 3.12 when stdout is a pipe, not a TTY)
      flaskProcess = spawn(pythonBin, ["-u", runScript], {
        cwd: ANALYZER_DIR,
        env: {
          ...process.env,
          PORT: String(flaskPort),
          HEADLESS: "1",                  // skip the auto-open-browser block
          PYTHONUNBUFFERED: "1",
          PYTHONIOENCODING: "utf-8",
          SPAD_USER_DATA_DIR: spadUserData,
        },
      });

      // Route Flask output through console so it appears in main-process.log
      flaskProcess.stdout.on("data", (d) => console.log(`[Flask] ${d.toString().trimEnd()}`));
      flaskProcess.stderr.on("data", (d) => console.error(`[Flask:err] ${d.toString().trimEnd()}`));
      flaskProcess.on("error", (err) => { console.error(`[Flask] spawn error: ${err.message}`); reject(err); });
      flaskProcess.on("exit", (code, signal) => {
        console.error(`[Flask] exited — code=${code} signal=${signal}`);
      });

      waitForHttp(`http://127.0.0.1:${flaskPort}/`, 30000)
        .then(() => resolve(flaskPort))
        .catch(reject);
    } catch (err) {
      reject(err);
    }
  });
}

function stopFlaskServer() {
  if (flaskProcess && !flaskProcess.killed) {
    try {
      if (process.platform === "win32") {
        spawn("taskkill", ["/pid", String(flaskProcess.pid), "/f", "/t"]);
      } else {
        flaskProcess.kill("SIGTERM");
        // Hard-kill fallback after 3 s
        setTimeout(() => {
          if (flaskProcess && !flaskProcess.killed) flaskProcess.kill("SIGKILL");
        }, 3000);
      }
    } catch (_) {}
  }
}

// ── Renderer window ──────────────────────────────────────────────────────────
let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1340,
    height: 860,
    minWidth: 480,
    minHeight: 600,
    title: "SPAD PHAKTS Analyzer",
    icon: path.join(APP_ROOT, "public", "icons", "icon-512.png"),
    webPreferences: {
      preload: path.join(APP_ROOT, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
    backgroundColor: "#070b14",
    titleBarStyle: "hiddenInset",
    trafficLightPosition: { x: 14, y: 14 },
  });

  mainWindow.loadURL(`http://127.0.0.1:${nodePort}`);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http")) shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => { mainWindow = null; });
}

// ── IPC: expose ports to the renderer ────────────────────────────────────────
ipcMain.handle("get-ports", () => ({
  nodePort,
  flaskPort,
  spadUrl: `http://127.0.0.1:${flaskPort}`,
}));

// ── App lifecycle ────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  try {
    // Launch both servers in parallel — they're independent
    const [n, f] = await Promise.all([
      startNodeServer(),
      startFlaskServer(),
    ]);
    console.log(`[main] Node API on :${n} | Flask SPAD on :${f}`);
    createWindow();
  } catch (err) {
    dialog.showErrorBox(
      "SPAD PHAKTS Analyzer — Erreur de démarrage",
      `Impossible de démarrer un des services :\n\n${err.message}\n\n` +
      `Vérifiez :\n` +
      `  • le fichier .env (clé ANTHROPIC_API_KEY)\n` +
      `  • que Python 3 et les dépendances de analyzer/ sont installés\n` +
      `    (cd analyzer && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt)`
    );
    app.quit();
  }

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      // Flask may have been killed between sessions; restart it if needed
      const flaskDead = !flaskProcess || flaskProcess.killed || flaskProcess.exitCode !== null;
      if (flaskDead) {
        console.log("[main] activate: Flask is not running — restarting…");
        try {
          const f = await startFlaskServer();
          console.log(`[main] activate: Flask restarted on :${f}`);
        } catch (err) {
          console.error(`[main] activate: Flask restart failed: ${err.message}`);
          dialog.showErrorBox(
            "SPAD PHAKTS Analyzer — Erreur Flask",
            `Impossible de redémarrer l'analyseur SPAD :\n\n${err.message}`
          );
          return;
        }
      }
      createWindow();
    }
  });
});

app.on("before-quit", () => { stopFlaskServer(); });
app.on("window-all-closed", () => {
  // On macOS keep Flask alive — the app stays in the Dock and the user
  // may reopen the window via activate; killing Flask here causes
  // ERR_CONNECTION_REFUSED when the window reopens.
  if (process.platform !== "darwin") {
    stopFlaskServer();
    app.quit();
  }
});
