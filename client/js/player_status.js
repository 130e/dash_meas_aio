// Player status checker for dash.js
// Returns detailed information about the current player state

function getPlayerStatus() {
    try {
        var player = window.dashPlayer;
        if (player) {
            return {
                isReady: player.isReady ? player.isReady() : 'unknown',
                isPlaying: player.isPlaying ? player.isPlaying() : 'unknown',
                currentTime: player.time ? player.time() : 'unknown',
                duration: player.duration ? player.duration() : 'unknown',
                abrAlgorithm: player.getAbrAlgorithm ? player.getAbrAlgorithm() : 'unknown',
                currentQuality: player.getTopQualityIndexFor ? player.getTopQualityIndexFor('video') : 'unknown',
                bufferLength: player.getBufferLength ? player.getBufferLength('video') : 'unknown',
                playerInstance: 'found'
            };
        }
        return { error: 'dashPlayer not found or not initialized' };
    } catch (e) {
        return { error: 'JavaScript error: ' + e.message };
    }
}
getPlayerStatus(); 