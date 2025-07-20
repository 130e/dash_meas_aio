// Video element status checker
// Returns detailed information about the HTML video element

function getVideoStatus() {
    var video = document.getElementById('videoPlayer');
    if (video) {
        return {
            src: video.src,
            currentSrc: video.currentSrc,
            readyState: video.readyState,
            networkState: video.networkState,
            paused: video.paused,
            currentTime: video.currentTime,
            duration: video.duration,
            buffered: video.buffered ? video.buffered.length : 0,
            error: video.error ? video.error.message : null
        };
    }
    return { error: 'video element not found' };
}

// Execute and return the status
getVideoStatus(); 