// Preload — exposes a minimal, safe bridge between renderer and main.
// The renderer can ask for the SPAD URL to load the Analyzer in an iframe.

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("spadPhakts", {
  getPorts: () => ipcRenderer.invoke("get-ports"),
});
