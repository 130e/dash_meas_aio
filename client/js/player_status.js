// Player status checker for dash.js
// Returns detailed information about the current player state

function getPlayerStatus() {
    try {
        if (window.dashjs && window.dashjs.MediaPlayer) {
            // Try to get the player from the global setup
            var player = null;
            
            // First try to get from getAllMediaPlayers (dash.js 2.3.0+)
            if (window.dashjs.MediaPlayer().getAllMediaPlayers) {
                var players = window.dashjs.MediaPlayer().getAllMediaPlayers();
                if (players.length > 0) {
                    player = players[0];
                }
            }
            
            // If no player found, try to create one (fallback)
            if (!player) {
                try {
                    player = window.dashjs.MediaPlayer().create();
                } catch (e) {
                    console.log('Could not create new player instance:', e);
                }
            }
            
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
        }
        return { error: 'dashjs not found or player not initialized' };
    } catch (e) {
        return { error: 'JavaScript error: ' + e.message };
    }
}

// Execute and return the status
getPlayerStatus(); 