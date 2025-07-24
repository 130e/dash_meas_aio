// Debug script for dash.js monitoring
// This script overrides console.log and save to variable
// Allow python script to access the logs

// Override console.log to capture all logs
var originalLog = console.log;
console.log = function() {
    originalLog.apply(console, arguments);
    // Also log to a global variable for us to access
    if (!window.dashDebugLogs) window.dashDebugLogs = [];
    window.dashDebugLogs.push(Array.prototype.slice.call(arguments).join(' '));
};

// Monitor network requests
var originalFetch = window.fetch;
window.fetch = function(url, options) {
    console.log('FETCH REQUEST:', url, options);
    return originalFetch.apply(this, arguments).then(function(response) {
        console.log('FETCH RESPONSE:', url, response.status, response.statusText);
        return response;
    }).catch(function(error) {
        console.log('FETCH ERROR:', url, error);
        throw error;
    });
};

// Monitor XMLHttpRequest
var originalXHROpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function(method, url, async, user, password) {
    console.log('XHR REQUEST:', method, url);
    return originalXHROpen.apply(this, arguments);
};

var originalXHRSend = XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.send = function(data) {
    console.log('XHR SEND:', data);
    return originalXHRSend.apply(this, arguments);
};

// Monitor dash.js events
if (window.dashjs && window.dashjs.MediaPlayer) {
    console.log('Dash.js found, version:', window.dashjs.VERSION || 'unknown');
    
    // Try to get player info
    try {
        var player = window.dashjs.MediaPlayer().create();
        console.log('Player created:', player);
        
        // Monitor player events
        if (player.on) {
            player.on('ready', function() { console.log('Player ready'); });
            player.on('play', function() { console.log('Player play'); });
            player.on('pause', function() { console.log('Player pause'); });
            player.on('error', function(e) { console.log('Player error:', e); });
            player.on('fragmentLoadingCompleted', function(e) { console.log('Fragment loaded:', e); });
            player.on('qualityChanged', function(e) { console.log('Quality changed:', e); });
        }
    } catch (e) {
        console.log('Error creating player:', e);
    }
} else {
    console.log('Dash.js not found');
}

console.log('Dash.js debugging enabled'); 