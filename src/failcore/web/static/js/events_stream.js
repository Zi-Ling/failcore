// events_stream.js - SSE event stream client for real-time notifications

(function() {
    let eventSource = null;
    let currentRunId = null;
    
    /**
     * Connect to SSE event stream for a run
     * @param {string} runId - Run ID to stream events for
     */
    window.connectEventStream = function(runId) {
        // Disconnect existing stream if any
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        
        if (!runId) {
            console.warn('No run ID provided for event stream');
            return;
        }
        
        currentRunId = runId;
        
        // Create EventSource for SSE
        const streamUrl = `/api/runs/${encodeURIComponent(runId)}/events`;
        eventSource = new EventSource(streamUrl);
        
        // Handle connection
        eventSource.onopen = function() {
            console.log('Event stream connected for run:', runId);
        };
        
        // Handle messages
        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                
                // Handle different event types
                if (data.type === 'connected') {
                    console.log('Event stream connected:', data);
                } else if (data.type === 'end') {
                    console.log('Event stream ended:', data.message);
                    eventSource.close();
                    eventSource = null;
                } else if (data.type === 'error') {
                    console.error('Event stream error:', data.error);
                    eventSource.close();
                    eventSource = null;
                } else {
                    // This is a real event (blocked, budget_exceeded, etc.)
                    // Only show toast for BLOCKED events (to avoid spam)
                    if (data.type === 'blocked' || 
                        data.type === 'budget_exceeded' || 
                        data.type === 'burn_rate_exceeded') {
                        if (window.showToast) {
                            window.showToast(data, 8000); // Show for 8 seconds
                        }
                    }
                }
            } catch (e) {
                console.error('Error parsing event data:', e);
            }
        };
        
        // Handle errors
        eventSource.onerror = function(error) {
            console.error('Event stream error:', error);
            // Close and cleanup on error
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
        };
    };
    
    /**
     * Disconnect from event stream
     */
    window.disconnectEventStream = function() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
            currentRunId = null;
            console.log('Event stream disconnected');
        }
    };
    
    // Auto-connect on page load if we're on a run detail page
    document.addEventListener('DOMContentLoaded', function() {
        // Try to get run_id from page
        const runDetailPage = document.querySelector('.run-detail-page');
        const replayPage = document.querySelector('.replay-page');
        
        let runId = null;
        if (runDetailPage) {
            runId = runDetailPage.dataset.runId;
        } else if (replayPage) {
            runId = replayPage.dataset.runId;
        }
        
        // Only connect if we have a run_id and we're on a relevant page
        // Don't auto-connect on overview/runs list pages
        if (runId && (runDetailPage || replayPage)) {
            // Small delay to ensure page is fully loaded
            setTimeout(() => {
                window.connectEventStream(runId);
            }, 500);
        }
    });
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        window.disconnectEventStream();
    });
})();
