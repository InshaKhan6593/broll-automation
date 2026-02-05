const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  // We can add IPC bridges here later
  platform: process.platform,
});
