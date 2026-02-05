import './WorkflowControl.css'

function WorkflowControl({ status, onStart, onCancel, canStart }) {
  const isRunning = status?.status === 'running'
  const isCompleted = status?.status === 'completed'
  const isFailed = status?.status === 'failed'
  const isCancelled = status?.status === 'cancelled'

  const getStatusColor = () => {
    if (isRunning) return 'running'
    if (isCompleted) return 'completed'
    if (isFailed) return 'failed'
    if (isCancelled) return 'cancelled'
    return 'idle'
  }

  return (
    <div className="workflow-control">
      <div className="workflow-header">
        <h3>⚡ Workflow</h3>
        <span className={`status-badge ${getStatusColor()}`}>
          {status?.status || 'Ready'}
        </span>
      </div>

      {isRunning && (
        <div className="progress-section">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${status?.progress || 0}%` }}
            />
          </div>
          <div className="progress-info">
            <span className="progress-step">{status?.current_step}</span>
            <span className="progress-percent">{status?.progress}%</span>
          </div>
        </div>
      )}

      {isFailed && (
        <div className="error-message">
          ❌ {status?.error}
        </div>
      )}

      {isCancelled && (
        <div className="cancelled-message">
          Workflow cancelled
        </div>
      )}

      {isCompleted && (
        <div className="success-message">
          Video generated successfully!
        </div>
      )}

      {isRunning ? (
        <button
          className="stop-btn"
          onClick={onCancel}
        >
          Stop Workflow
        </button>
      ) : (
        <button
          className="start-btn"
          onClick={onStart}
          disabled={!canStart}
        >
          Start Workflow
        </button>
      )}

      {!canStart && !isRunning && (
        <p className="help-text">
          Upload a video and at least one image to start
        </p>
      )}
    </div>
  )
}

export default WorkflowControl
