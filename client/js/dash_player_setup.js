// Dash.js player setup script
// This replaces the inline script in the HTML file

function setupDashPlayer(config = {}) {
    // Default configuration
    const defaultConfig = {
        manifestUrl: "chunks/manifest.mpd",
        abrAlgorithm: 0,
        enableRLABR: false,
        bufferTimeAtTopQuality: 60,
        stableBufferTime: 60,
        bufferToKeep: 60,
        bufferPruningInterval: 60,
        enableBufferOccupancyABR: false
    };
    
    // Merge with provided config
    const finalConfig = { ...defaultConfig, ...config };
    
    // ABR algorithm mapping
    const abrAlgorithms = {
        0: 'Default', 
        1: 'Fixed Rate (0)', 
        2: 'Buffer Based', 
        3: 'Rate Based', 
        4: 'MPC', 
        5: 'Festive', 
        6: 'Bola'
    };
    
    try {
        // Create the player
        var player = dashjs.MediaPlayer().create();
        
        // Enable rlABR if needed
        if (finalConfig.abrAlgorithm > 1 && finalConfig.abrAlgorithm != 6) {
            player.enablerlABR(finalConfig.enableRLABR);
        }
        
        // Set buffer configuration
        player.setBufferTimeAtTopQuality(finalConfig.bufferTimeAtTopQuality);
        player.setStableBufferTime(finalConfig.stableBufferTime);
        player.setBufferToKeep(finalConfig.bufferToKeep);
        player.setBufferPruningInterval(finalConfig.bufferPruningInterval);
        
        // Initialize the player
        player.initialize(document.querySelector("#videoPlayer"), finalConfig.manifestUrl, true);
        
        // Enable buffer occupancy ABR for BOLA
        if (finalConfig.abrAlgorithm == 6) {
            player.enableBufferOccupancyABR(finalConfig.enableBufferOccupancyABR);
        }
        
        // Set the ABR algorithm
        player.setAbrAlgorithm(finalConfig.abrAlgorithm);
        
        // Update document title
        if (finalConfig.abrAlgorithm in abrAlgorithms) {
            document.title = abrAlgorithms[finalConfig.abrAlgorithm];
        } else {
            document.title = "Unknown ABR Algorithm";
        }
        
        console.log('Dash.js player initialized successfully');
        console.log('ABR Algorithm:', abrAlgorithms[finalConfig.abrAlgorithm] || 'Unknown');
        console.log('Manifest URL:', finalConfig.manifestUrl);
        
        return { success: true, player: player, config: finalConfig };
        
    } catch (error) {
        console.error('Error setting up Dash.js player:', error);
        return { success: false, error: error.message };
    }
}

// Export the function globally
window.setupDashPlayer = setupDashPlayer; 