const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let pythonProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: "Humanitarian Video Editor",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, '../preload/index.js')
    },
    backgroundColor: '#000000'
  });

  // In development, load from the Vite dev server
  // In production, we will load the built index.html
  const isDev = !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    // Open DevTools
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function waitForBackend(retries = 30) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      attempts++;
      const req = http.get('http://127.0.0.1:8000/', (res) => {
        resolve();
      });
      req.on('error', () => {
        if (attempts >= retries) {
          reject(new Error('Backend failed to start'));
        } else {
          setTimeout(check, 1000);
        }
      });
      req.end();
    };
    check();
  });
}

function startBackend() {
  console.log('Starting Python Backend...');
  const isDev = !app.isPackaged;
  console.log(`Backend Mode: ${isDev ? 'Development' : 'Production'}`);

  let command = 'python';
  let args = [path.join(__dirname, '../../backend/main.py')];

  if (!isDev) {
    // In production, run the bundled executable (platform-aware)
    const exeName = process.platform === 'win32' ? 'backend-engine.exe' : 'backend-engine';
    command = path.join(process.resourcesPath, 'backend-dist', exeName);
    args = [];
  }

  pythonProcess = spawn(command, args, {
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1'
    }
  });

  pythonProcess.stdout.on('data', (data) => {
    const text = data.toString('utf-8');
    console.log(`Backend: ${text}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    const text = data.toString('utf-8');
    console.error(`Backend Error: ${text}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Backend process exited with code ${code}`);
  });
}

app.on('ready', async () => {
  startBackend();

  // Wait for backend to be ready before showing window
  try {
    await waitForBackend();
    console.log('Backend is ready.');
  } catch (e) {
    console.error('Backend failed to start, opening window anyway.');
  }

  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});
