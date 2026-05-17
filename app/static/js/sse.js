/**
 * SSE client for streaming DM narrative from the backend.
 *
 * Connects to GET /api/game/stream?input=... and emits events for
 * streaming tokens, final narrative, and completion.
 */
const SSEClient = {
    eventSource: null,

    /**
     * Open an SSE connection to stream the DM's response.
     *
     * @param {string} input - The player's action text.
     * @param {object} callbacks - Event callbacks.
     * @param {function} callbacks.onToken - Called with each streamed token.
     * @param {function} callbacks.onNarrative - Called with the final narrative.
     * @param {function} callbacks.onDone - Called with turn_count on completion.
     * @param {function} callbacks.onError - Called with an error message.
     */
    connect(input, callbacks) {
        this.disconnect();

        const url = `/api/game/stream?input=${encodeURIComponent(input)}`;
        this.eventSource = new EventSource(url);

        this.eventSource.addEventListener("token", (e) => {
            try {
                const data = JSON.parse(e.data);
                if (callbacks.onToken) callbacks.onToken(data.content);
            } catch (_) { /* skip malformed events */ }
        });

        this.eventSource.addEventListener("narrative", (e) => {
            try {
                const data = JSON.parse(e.data);
                if (callbacks.onNarrative) callbacks.onNarrative(data.content);
            } catch (_) { /* skip malformed events */ }
        });

        this.eventSource.addEventListener("done", (e) => {
            try {
                const data = JSON.parse(e.data);
                if (callbacks.onDone) callbacks.onDone(data.turn_count);
            } catch (_) { /* skip malformed events */ }
            this.disconnect();
        });

        this.eventSource.onerror = () => {
            if (callbacks.onError) callbacks.onError("Connection lost");
        };
    },

    /** Close the current SSE connection if any. */
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    },
};
