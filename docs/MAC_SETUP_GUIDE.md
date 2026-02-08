# Mac Installation Guide

## Download
1. Go to **[GitHub Releases](https://github.com/YOUR_USERNAME/broll-automation/releases)** (or GitHub Actions artifacts if not published)
2. Download `Humanitarian Video Editor-1.0.0-macOS-Universal.dmg`

## Install
1. **Open the DMG** file
2. **Drag** the app to your Applications folder
3. **Eject** the DMG

## First Launch (Important!)

Since the app is not signed with an Apple Developer certificate, macOS will block it initially.

### Method 1: Right-Click Open
1. Open **Finder** → **Applications**
2. **Right-click** (or Control-click) on "Humanitarian Video Editor"
3. Select **"Open"**
4. Click **"Open"** in the dialog that appears

### Method 2: System Settings
If Method 1 doesn't work:
1. Try opening the app normally (it will be blocked)
2. Go to **System Settings** → **Privacy & Security**
3. Scroll down to find the message about the blocked app
4. Click **"Open Anyway"**
5. Enter your password if prompted

## Requirements
- **macOS 10.15 (Catalina)** or later
- Works on both **Intel** and **Apple Silicon** Macs (M1/M2/M3)
- ~500MB disk space
- Internet connection (for AI processing)

## Environment Setup
Before using the app, you need API keys. Create a `.env` file in your home directory or the app will prompt you:

```
OLLAMA_API_KEY=your_ollama_key
OLLAMA_HOST=https://ollama.com
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
```

## Troubleshooting

### "App is damaged and can't be opened"
Run this in Terminal:
```bash
xattr -cr /Applications/Humanitarian\ Video\ Editor.app
```

### Backend won't start
Check Console.app for error logs, or run from Terminal to see output:
```bash
/Applications/Humanitarian\ Video\ Editor.app/Contents/MacOS/Humanitarian\ Video\ Editor
```

### App crashes on launch
- Ensure you're running macOS 10.15+
- Try reinstalling the app
- Check if antivirus software is blocking it
