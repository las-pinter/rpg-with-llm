"use strict";
/**
 * SSE client using fetch (POST) instead of EventSource (GET).
 *
 * Sends input and config as a JSON body to avoid HTTP 414 URL-too-long
 * errors when the story log grows large. Reads the SSE response via
 * ReadableStream with manual chunk buffering and event parsing.
 */
const SSEClient = {
    reader: null,
    controller: null,
    decoder: new TextDecoder(),
    buffer: "", // Accumulates partial SSE data across chunks
    /**
     * Connect to the streaming endpoint via POST + JSON body.
     *
     * @param {string} input - The player's action text.
     * @param {object|null} provider - Main provider config.
     * @param {object} callbacks - Event callback handlers.
     * @param {function} callbacks.onToken - Called with each streamed token.
     * @param {function} callbacks.onNarrative - Called with the final narrative.
     * @param {function} callbacks.onNpcThinking - Called with {npc_id, hint}.
     * @param {function} callbacks.onStateUpdate - Called with state update data.
     * @param {function} callbacks.onTokenUsage - Called with token usage info.
     * @param {function} callbacks.onDone - Called when stream finishes.
     * @param {function} callbacks.onError - Called on network or server error.
     * @param {object|null} state - Current world state dict (for continuity).
     * @param {object|null} character - Current character creation data.
     * @param {object|null} npcProvider - NPC subagent provider config.
     * @param {object|null} summarizerProvider - Summarizer provider config.
     */
    connect(input, provider, callbacks, state, character, npcProvider, summarizerProvider) {
        this.disconnect(); // Always clean up before connecting
        this.controller = new AbortController();
        const body = { input };
        if (provider)
            body.provider = provider;
        if (state)
            body.state = state;
        if (character)
            body.character = character;
        if (npcProvider)
            body.npc_provider = npcProvider;
        if (summarizerProvider)
            body.summarizer_provider = summarizerProvider;
        fetch("/api/game/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            signal: this.controller.signal,
        })
            .then(async (response) => {
            if (!response.ok)
                throw new Error(`HTTP ${response.status}`);
            const reader = response.body.getReader();
            this.reader = reader;
            while (true) {
                const { done, value } = await reader.read();
                if (done)
                    break;
                this.buffer += this.decoder.decode(value, { stream: true });
                this._processBuffer(callbacks);
            }
        })
            .catch((err) => {
            if (err.name === "AbortError")
                return; // Clean disconnect
            if (callbacks.onError)
                callbacks.onError(err.message || "Connection lost");
        })
            .finally(() => {
            this.disconnect();
        });
    },
    /** Parse complete SSE blocks from the accumulated buffer. */
    _processBuffer(callbacks) {
        let lineBreak = this.buffer.indexOf("\n\n");
        while (lineBreak !== -1) {
            const block = this.buffer.slice(0, lineBreak);
            this.buffer = this.buffer.slice(lineBreak + 2);
            // Parse event: and data: lines from the block
            let eventType = "";
            let eventData = "";
            const lines = block.split("\n");
            for (const line of lines) {
                if (line.startsWith("event: ")) {
                    eventType = line.slice(7).trim();
                }
                else if (line.startsWith("data: ")) {
                    // SSE spec: multiple data: lines joined with \n
                    eventData += (eventData ? "\n" : "") + line.slice(6);
                }
            }
            if (!eventType || !eventData)
                continue;
            try {
                const parsed = JSON.parse(eventData);
                this._dispatchEvent(eventType, parsed, callbacks);
            }
            catch (_) { /* skip malformed events */ }
            lineBreak = this.buffer.indexOf("\n\n");
        }
    },
    /** Dispatch a parsed SSE event to the appropriate callback. */
    _dispatchEvent(type, data, callbacks) {
        switch (type) {
            case "token":
                if (callbacks.onToken)
                    callbacks.onToken(data.content);
                break;
            case "narrative":
                if (callbacks.onNarrative)
                    callbacks.onNarrative(data.content);
                break;
            case "npc_thinking":
                if (callbacks.onNpcThinking)
                    callbacks.onNpcThinking(data);
                break;
            case "state_update":
                if (callbacks.onStateUpdate)
                    callbacks.onStateUpdate(data);
                break;
            case "done":
                if (callbacks.onDone)
                    callbacks.onDone(data.turn_count);
                this.disconnect(); // Close after done
                break;
            case "token_usage":
                if (callbacks.onTokenUsage)
                    callbacks.onTokenUsage(data);
                break;
            case "error":
                if (callbacks.onError)
                    callbacks.onError(data.message || "Server error");
                this.disconnect();
                break;
        }
    },
    /** Close the current connection and clean up all resources. */
    disconnect() {
        if (this.reader) {
            this.reader.cancel().catch(() => { });
            this.reader = null;
        }
        if (this.controller) {
            this.controller.abort();
            this.controller = null;
        }
        this.buffer = "";
    },
};
//# sourceMappingURL=sse.js.map