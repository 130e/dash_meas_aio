// Video playback control script
// Handles starting video playback with autoplay bypass and retry logic

function startVideoPlayback() {
    try {
        var video = document.getElementById('videoPlayer');
        if (video) {
            // Set muted to true to bypass autoplay restrictions
            video.muted = true;
            video.volume = 0;
            
            // Try to play the video
            var playPromise = video.play();
            if (playPromise !== undefined) {
                playPromise.then(function() {
                    console.log('Video started playing successfully');
                }).catch(function(error) {
                    console.log('Video play failed:', error);
                    // Try again with a different approach
                    setTimeout(function() {
                        video.play().catch(function(e) {
                            console.log('Second play attempt failed:', e);
                        });
                    }, 1000);
                });
            }
            return { success: true, message: 'Play command sent' };
        }
        return { error: 'Video element not found' };
    } catch (e) {
        return { error: 'Failed to start video: ' + e.message };
    }
}

function retryVideoPlayback() {
    var video = document.getElementById('videoPlayer');
    if (video) {
        video.muted = true;
        video.volume = 0;
        video.play().catch(function(e) {
            console.log('Final play attempt failed:', e);
        });
    }
}

function getPlaybackStatus() {
    var video = document.getElementById('videoPlayer');
    if (video) {
        return {
            paused: video.paused,
            currentTime: video.currentTime,
            readyState: video.readyState,
            networkState: video.networkState
        };
    }
    return { error: 'Video element not found' };
}

// Export functions for use
window.videoControl = {
    startPlayback: startVideoPlayback,
    retryPlayback: retryVideoPlayback,
    getStatus: getPlaybackStatus
}; 