import { useEffect, useRef } from 'react'
import './LogViewer.css'

function LogViewer({ logs }) {
  const containerRef = useRef(null)

  // Auto-scroll to bottom on new logs
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs])

  const getLogClass = (level) => {
    switch (level) {
      case 'SUCCESS': return 'log-success'
      case 'WARNING': return 'log-warning'
      case 'ERROR': return 'log-error'
      case 'STEP': return 'log-step'
      default: return 'log-info'
    }
  }

  const getLogIcon = (level) => {
    switch (level) {
      case 'SUCCESS': return '✓'
      case 'WARNING': return '⚠'
      case 'ERROR': return '✗'
      case 'STEP': return '►'
      default: return '•'
    }
  }

  return (
    <div className="log-viewer">
      <div className="log-header">
        <h3>📋 Workflow Logs</h3>
        <span className="log-count">{logs.length} entries</span>
      </div>
      
      <div className="log-container" ref={containerRef}>
        {logs.length === 0 ? (
          <div className="log-empty">
            Logs will appear here when the workflow starts...
          </div>
        ) : (
          logs.map((log, idx) => (
            <div key={idx} className={`log-entry ${getLogClass(log.level)}`}>
              <span className="log-time">{log.timestamp}</span>
              <span className="log-icon">{getLogIcon(log.level)}</span>
              <span className="log-message">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default LogViewer
