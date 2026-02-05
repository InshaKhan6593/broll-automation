import { useState, useEffect, useRef } from 'react'
import FileUpload from './components/FileUpload'
import WorkflowControl from './components/WorkflowControl'
import LogViewer from './components/LogViewer'
import VideoPlayer from './components/VideoPlayer'
import Settings from './components/Settings'
import './App.css'

const API_BASE = 'http://localhost:8000/api'

function App() {
  const [video, setVideo] = useState(null)
  const [images, setImages] = useState([])
  const [workflowStatus, setWorkflowStatus] = useState(null)
  const [logs, setLogs] = useState([])
  const [outputVideo, setOutputVideo] = useState(null)
  const [apiKeys, setApiKeys] = useState({})
  const [videoUploadProgress, setVideoUploadProgress] = useState(null)
  const [imageUploadProgress, setImageUploadProgress] = useState(null)
  const eventSourceRef = useRef(null)

  // Fetch images list
  const fetchImages = async () => {
    try {
      const res = await fetch(`${API_BASE}/images`)
      const data = await res.json()
      setImages(data.images || [])
    } catch (err) {
      console.error('Failed to fetch images:', err)
    }
  }

  // Fetch workflow status
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/workflow/status`)
      const data = await res.json()
      setWorkflowStatus(data)
      
      // If completed, fetch output video
      if (data.status === 'completed' && data.output_video) {
        setOutputVideo(`http://localhost:8000/outputs/${data.output_video}`)
      }
    } catch (err) {
      console.error('Failed to fetch status:', err)
    }
  }

  // Poll status while running
  useEffect(() => {
    fetchImages()
    fetchStatus()
    
    const interval = setInterval(() => {
      if (workflowStatus?.status === 'running') {
        fetchStatus()
      }
    }, 2000)
    
    return () => clearInterval(interval)
  }, [workflowStatus?.status])

  // Handle video upload with progress
  const handleVideoUpload = (file) => {
    const formData = new FormData()
    formData.append('file', file)
    setVideoUploadProgress(0)

    const xhr = new XMLHttpRequest()
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setVideoUploadProgress(Math.round((e.loaded / e.total) * 100))
      }
    }
    xhr.onload = () => {
      setVideoUploadProgress(null)
      if (xhr.status >= 200 && xhr.status < 300) {
        const data = JSON.parse(xhr.responseText)
        setVideo(data)
      } else {
        console.error('Video upload failed:', xhr.statusText)
      }
    }
    xhr.onerror = () => {
      setVideoUploadProgress(null)
      console.error('Video upload failed')
    }
    xhr.open('POST', `${API_BASE}/upload/video`)
    xhr.send(formData)
  }

  // Handle image uploads with progress
  const handleImagesUpload = (files) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    setImageUploadProgress(0)

    const xhr = new XMLHttpRequest()
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setImageUploadProgress(Math.round((e.loaded / e.total) * 100))
      }
    }
    xhr.onload = () => {
      setImageUploadProgress(null)
      if (xhr.status >= 200 && xhr.status < 300) {
        fetchImages()
      } else {
        console.error('Image upload failed:', xhr.statusText)
      }
    }
    xhr.onerror = () => {
      setImageUploadProgress(null)
      console.error('Image upload failed')
    }
    xhr.open('POST', `${API_BASE}/upload/images`)
    xhr.send(formData)
  }

  // Close any active log stream
  const closeLogStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
  }

  // Start workflow
  const handleStartWorkflow = async () => {
    closeLogStream()
    setLogs([])
    setOutputVideo(null)

    try {
      await fetch(`${API_BASE}/workflow/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(apiKeys)
      })
      fetchStatus()

      // Start log streaming
      const es = new EventSource(`${API_BASE}/workflow/logs`)
      eventSourceRef.current = es

      es.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.type === 'clear') {
          setLogs([])
        } else if (data.type === 'log') {
          setLogs(prev => [...prev, data.data])
        }
      }

      es.onerror = () => {
        es.close()
        eventSourceRef.current = null
        fetchStatus()
      }

    } catch (err) {
      console.error('Failed to start workflow:', err)
    }
  }

  // Cancel running workflow
  const handleCancel = async () => {
    try {
      closeLogStream()
      await fetch(`${API_BASE}/workflow/cancel`, { method: 'POST' })
      fetchStatus()
    } catch (err) {
      console.error('Failed to cancel workflow:', err)
    }
  }

  // Clear images
  const handleClearImages = async () => {
    try {
      await fetch(`${API_BASE}/upload/images`, { method: 'DELETE' })
      fetchImages()
    } catch (err) {
      console.error('Failed to clear images:', err)
    }
  }

  // Handle Full Reset - cleans everything except image_index.json (captions)
  const handleReset = async () => {
    try {
      // Close SSE log stream
      closeLogStream()

      // Clear video player FIRST so browser releases the file handle
      setOutputVideo(null)
      setWorkflowStatus(null)
      setLogs([])
      setVideo(null)

      // Wait for browser to unmount the <video> element and release file
      await new Promise(r => setTimeout(r, 300))

      // Backend reset: deletes video, transcript, segments, EDL, outputs, ChromaDB
      // Backend preserves: image_index.json, uploaded images
      await fetch(`${API_BASE}/workflow/reset`, { method: 'POST' })

      setImages([])
      // Refresh images list (still on disk with caption status)
      fetchImages()
    } catch (err) {
      console.error('Failed to reset:', err)
    }
  }

  const isRunning = workflowStatus?.status === 'running'
  const hasAnyState = !isRunning && (video || images.length > 0 || outputVideo || workflowStatus?.status === 'completed' || workflowStatus?.status === 'failed' || workflowStatus?.status === 'cancelled')

  return (
    <div className="app">
      <header className="header">
        <div className="header-top">
          <h1>🎬 AI Video Editor</h1>
          {hasAnyState && (
            <button className="reset-btn header-reset-btn" onClick={handleReset}>
              Start New Project 🔄
            </button>
          )}
        </div>
        <p>Upload a video and images to create an illustrated documentary</p>
      </header>

      <main className="main">
        <div className="upload-section">
          <FileUpload
            title="Source Video"
            accept="video/*"
            multiple={false}
            onUpload={handleVideoUpload}
            files={video ? [video] : []}
            icon="🎥"
            uploadProgress={videoUploadProgress}
          />

          <FileUpload
            title="Images"
            accept="image/*"
            multiple={true}
            onUpload={handleImagesUpload}
            files={images}
            onClear={handleClearImages}
            icon="🖼️"
            uploadProgress={imageUploadProgress}
          />
        </div>

        <Settings onKeysChange={setApiKeys} />

        <WorkflowControl
          status={workflowStatus}
          onStart={handleStartWorkflow}
          onCancel={handleCancel}
          canStart={video && images.length > 0}
        />

        <div className="output-section">
          <LogViewer logs={logs} />

          {outputVideo && (
            <div className="output-video-container">
              <VideoPlayer
                src={outputVideo}
                title="Generated Video"
              />
            </div>
          )}

        </div>
      </main>
    </div>
  )
}

export default App
