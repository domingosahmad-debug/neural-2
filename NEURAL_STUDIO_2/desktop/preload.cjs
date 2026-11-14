const {contextBridge, ipcRenderer} = require('electron');
contextBridge.exposeInMainWorld('neuralDesktop', {
  selectMedia: () => ipcRenderer.invoke('editor:media'),
  saveExport: id => ipcRenderer.invoke('editor:save-output', id)
});
