import { useRef } from 'react'
import './FileUpload.css'

function FileUpload({ title, accept, multiple, onUpload, files, onClear, icon, uploadProgress }) {
  const inputRef = useRef(null)
  const isUploading = uploadProgress !== null && uploadProgress !== undefined

  const handleDrop = (e) => {
    e.preventDefault()
    if (isUploading) return
    const droppedFiles = Array.from(e.dataTransfer.files)
    if (multiple) {
      onUpload(droppedFiles)
    } else {
      onUpload(droppedFiles[0])
    }
  }

  const handleChange = (e) => {
    if (isUploading) return
    const selectedFiles = Array.from(e.target.files)
    if (multiple) {
      onUpload(selectedFiles)
    } else {
      onUpload(selectedFiles[0])
    }
    e.target.value = ''
  }

  const handleDragOver = (e) => {
    e.preventDefault()
  }

  return (
    <div className="file-upload">
      <div className="file-upload-header">
        <span className="file-upload-icon">{icon}</span>
        <h3>{title}</h3>
        {files.length > 0 && onClear && !isUploading && (
          <button className="clear-btn" onClick={onClear}>
            Clear All
          </button>
        )}
      </div>

      <div
        className={`drop-zone${isUploading ? ' uploading' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={() => !isUploading && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleChange}
          hidden
        />
        {isUploading ? (
          <div className="upload-progress">
            <p>Uploading... {uploadProgress}%</p>
            <div className="upload-progress-bar">
              <div
                className="upload-progress-fill"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        ) : (
          <p>
            {multiple ? 'Drop files here or click to upload' : 'Drop file here or click to upload'}
          </p>
        )}
      </div>

      {files.length > 0 && (
        <div className="file-list">
          {files.map((file, idx) => (
            <div key={idx} className="file-item">
              <span className="file-name">{file.filename || file.name}</span>
            </div>
          ))}
        </div>
      )}

      <div className="file-count">
        {files.length} file{files.length !== 1 ? 's' : ''} uploaded
      </div>
    </div>
  )
}

export default FileUpload
