import './VideoPlayer.css'

function VideoPlayer({ src, title }) {
  const handleDownload = () => {
    const link = document.createElement('a')
    link.href = src
    link.download = 'output_video.mp4'
    link.click()
  }

  return (
    <div className="video-player">
      <div className="video-header">
        <h3>🎬 {title}</h3>
        <button className="download-btn" onClick={handleDownload}>
          ⬇️ Download
        </button>
      </div>
      
      <div className="video-container">
        <video 
          controls 
          autoPlay={false}
          src={src}
        >
          Your browser does not support the video tag.
        </video>
      </div>
    </div>
  )
}

export default VideoPlayer
