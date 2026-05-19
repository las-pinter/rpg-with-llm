/**
 * LLM-Powered RPG — Game View
 *
 * The main gameplay interface: narrative display, status sidebar, and
 * action input.  Communicates with the DM backend via POST /api/turn.
 */
const GameView = {
    /** Runtime game state. */
    state: {
        worldState: null,
        turnCount: 0,
        isThinking: false,
        hasStarted: false,
        autoScroll: true,
    },

    /** DOM element references. */
    els: {},

    // ------------------------------------------------------------------
    // Initialisation
    // ------------------------------------------------------------------

    init() {
        this.els = {
            container: document.getElementById("view-game"),

            // Narrative
            narrativeContent: document.getElementById("narrative-content"),
            narrativePane: document.getElementById("narrative-pane"),
            thinkingIndicator: document.getElementById("thinking-indicator"),
            npcThinkingIndicator: document.getElementById("npc-thinking-indicator"),
            npcThinkingText: document.querySelector("#npc-thinking-indicator .npc-thinking-text"),

            // Sidebar
            sidebarName: document.getElementById("sidebar-name"),
            sidebarClassLevel: document.getElementById("sidebar-class-level"),
            hpFill: document.getElementById("hp-fill"),
            hpText: document.getElementById("hp-text"),
            statsList: document.getElementById("stats-list"),
            inventoryList: document.getElementById("inventory-list"),
            locationText: document.getElementById("location-text"),
            collapseBtn: document.getElementById("sidebar-collapse"),

            // Input
            playerInput: document.getElementById("player-input"),
            submitBtn: document.getElementById("submit-action"),
            quickActions: document.getElementById("quick-actions"),
            newGameBtn: document.getElementById("new-game-btn"),
            saveGameBtn: document.getElementById("save-game-btn"),
        };

        // Submit action
        this.els.submitBtn.addEventListener("click", () => this._submit());
        this.els.playerInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                this._submit();
            }
        });

        // New Game button
        this.els.newGameBtn.addEventListener("click", () => this._newGame());

        // Save Game button
        this.els.saveGameBtn.addEventListener("click", () => this._saveGame());

        // Sidebar collapse
        this.els.collapseBtn.addEventListener("click", () => {
            const sidebar = document.getElementById("status-sidebar");
            sidebar.classList.toggle("collapsed");
            this.els.collapseBtn.textContent = sidebar.classList.contains("collapsed") ? "\u25B6" : "\u25C0";

            // Toggle game grid layout
            const gameView = document.getElementById("view-game");
            gameView.classList.toggle("sidebar-collapsed");
        });

        // Auto-scroll detection — pause on manual scroll-up
        this.els.narrativePane.addEventListener("scroll", () => {
            const el = this.els.narrativePane;
            const atBottom =
                el.scrollHeight - el.scrollTop - el.clientHeight < 80;
            this.state.autoScroll = atBottom;
        });

        // Watch for view changes to initialise game on first show
        window.addEventListener("hashchange", () => {
            if (window.location.hash === "#game") {
                this._onShow();
            }
        });
    },

    // ------------------------------------------------------------------
    // View Lifecycle
    // ------------------------------------------------------------------

    /** Called when the game view becomes active. */
    _onShow() {
        this._loadState();
        this._renderSidebar();

        if (!this.state.hasStarted && App.state.character) {
            this.state.hasStarted = true;
            this._enableInput();
            // Send an initial action to start the story
            this._sendTurn(
                "I look around, taking in my surroundings. Where am I, and what do I see?",
            );
        } else if (App.state.character) {
            this._enableInput();
        } else {
            // No character — redirect
            App.navigate("character");
        }
    },

    // ------------------------------------------------------------------
    // Input Management
    // ------------------------------------------------------------------

    /** Enable the player input field and submit button. */
    _enableInput() {
        this.els.playerInput.disabled = false;
        this.els.submitBtn.disabled = false;
        this.els.playerInput.focus();
    },

    /** Disable the input field and button (during DM thinking). */
    _disableInput() {
        this.els.playerInput.disabled = true;
        this.els.submitBtn.disabled = true;
    },

    /** Submit the current player action. */
    _submit() {
        const input = this.els.playerInput.value.trim();
        if (!input || this.state.isThinking) return;

        this.els.playerInput.value = "";
        this._sendTurn(input);
    },

    // ------------------------------------------------------------------
    // Turn Processing
    // ------------------------------------------------------------------

    /** Send a player action to the DM and process the response. */
    async _sendTurn(input) {
        if (this.state.isThinking) return;

        this.state.isThinking = true;
        this._disableInput();
        this._hideNpcThinking();
        this._showThinking(true);

        // Add the player's action to the narrative
        this._addPlayerAction(input);

        // Try SSE streaming first; fall back to fetch-based POST
        try {
            await this._sendTurnSSE(input);
        } catch (_sseErr) {
            // SSE failed — fall back to synchronous fetch
            try {
                await this._sendTurnFetch(input);
            } catch (fetchErr) {
                let msg = fetchErr.message;
                if (fetchErr.name === "TimeoutError") {
                    msg = "The DM is taking too long — check your connection and try again.";
                } else if (fetchErr.message === "Failed to fetch") {
                    msg = "Cannot reach the game server. Is it running?";
                }
                this._addNarrative(`[${msg}]`, { isError: true });
                this._addTurnSeparator();
            }
        } finally {
            this.state.isThinking = false;
            this._showThinking(false);
            this._enableInput();
        }
    },

    /**
     * Process a turn via SSE streaming (primary path).
     * Resolves on successful completion, rejects on error.
     */
    _sendTurnSSE(input) {
        return new Promise((resolve, reject) => {
            // Create a streaming text element that tokens fill in real time
            const streamDiv = document.createElement("div");
            streamDiv.className = "turn-narrative turn-streaming";
            const streamP = document.createElement("p");
            streamDiv.appendChild(streamP);
            this.els.narrativeContent.appendChild(streamDiv);
            this._scrollToBottom();

            let tokenBuffer = "";

            const removeStreamDiv = () => {
                if (streamDiv.parentNode) {
                    streamDiv.parentNode.removeChild(streamDiv);
                }
            };

            SSEClient.connect(input, App.state.provider, {
                onToken: ((token) => {
                    tokenBuffer += token;
                    streamP.textContent = this._stripXmlTags(tokenBuffer);
                    // Throttle scroll to avoid layout thrash on fast streams
                    if (tokenBuffer.length % 32 < token.length) {
                        this._scrollToBottom();
                    }
                }).bind(this),

                onNpcThinking: ((npcData) => {
                    this._showNpcThinking(npcData);
                }).bind(this),

                onNarrative: ((narrative) => {
                    // Replace streaming content with the properly
                    // formatted narrative (paragraphs, etc.)
                    this._hideNpcThinking();
                    removeStreamDiv();
                    this._addNarrative(narrative);
                    this._scrollToBottom();
                }).bind(this),

                onDone: ((turnCount) => {
                    this._hideNpcThinking();
                    this.state.turnCount = turnCount ?? this.state.turnCount + 1;
                    this._renderSidebar();
                    this._addTurnSeparator();
                    resolve();
                }).bind(this),

                onError: ((msg) => {
                    this._hideNpcThinking();
                    SSEClient.disconnect();
                    removeStreamDiv();
                    reject(new Error(msg || "SSE connection failed"));
                }).bind(this),
            });
        });
    },

    /**
     * Fallback: process a turn via the synchronous POST /api/turn endpoint.
     * Used when SSE is unavailable or fails.
     */
    async _sendTurnFetch(input) {
        this._hideNpcThinking();
        const provider = App.state.provider;

        const resp = await fetch("/api/turn", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                input: input,
                provider: provider
                    ? {
                        base_url: provider.base_url,
                        model: provider.model,
                        provider_type: provider.provider_type || "ollama",
                        api_key: provider.api_key || undefined,
                    }
                    : undefined,
                npc_provider: App.state.npcProvider
                    ? {
                        base_url: App.state.npcProvider.base_url,
                        model: App.state.npcProvider.model,
                        provider_type: App.state.npcProvider.provider_type || "ollama",
                        api_key: App.state.npcProvider.api_key || undefined,
                    }
                    : undefined,
                summarizer_provider: App.state.summarizerProvider
                    ? {
                        base_url: App.state.summarizerProvider.base_url,
                        model: App.state.summarizerProvider.model,
                        provider_type: App.state.summarizerProvider.provider_type || "ollama",
                        api_key: App.state.summarizerProvider.api_key || undefined,
                    }
                    : undefined,
                character: App.state.character || undefined,
                state: this.state.worldState || undefined,
            }),
            signal: AbortSignal.timeout(60000),
        });

        const data = await resp.json();

        if (data.ok) {
            this._addNarrative(data.narrative);

            if (data.state_changes && data.state_changes.length > 0) {
                this._applyStateChanges(data.state_changes);
            }

            if (data.tool_results && data.tool_results.length > 0) {
                this._showToolResults(data.tool_results);
            }

            this.state.turnCount = data.turn_count ?? this.state.turnCount + 1;
            this._renderSidebar();
            this._addTurnSeparator();
        } else {
            this._addNarrative(
                `[The fabric of reality wavers... An error occurred: ${data.error || "Unknown error"
                }]`,
                { isError: true },
            );
            this._addTurnSeparator();
        }
    },

    // ------------------------------------------------------------------
    // Narrative Display
    // ------------------------------------------------------------------

    /** Add the player's action bubble to the narrative. */
    _addPlayerAction(action) {
        const div = document.createElement("div");
        div.className = "turn-player";
        div.textContent = action;
        this.els.narrativeContent.appendChild(div);
        this._scrollToBottom();
    },

    /** Append DM narrative text to the narrative pane. */
    _addNarrative(text, opts) {
        opts = opts || {};
        const div = document.createElement("div");
        div.className = "turn-narrative";

        // Render paragraphs from the narrative text
        const paragraphs = text.split("\n").filter((p) => p.trim());
        if (paragraphs.length === 0) {
            div.innerHTML = "<p>" + this._esc(text) + "</p>";
        } else {
            div.innerHTML = paragraphs
                .map((p) => "<p>" + this._esc(p) + "</p>")
                .join("");
        }

        if (opts.isError) {
            div.classList.add("turn-error");
        }

        this.els.narrativeContent.appendChild(div);
        this._scrollToBottom();
    },

    /** Show tool results as subtle narrative annotations. */
    _showToolResults(results) {
        for (const tr of results) {
            const div = document.createElement("div");
            div.className = "turn-tool-result";
            const ok = tr.result && tr.result.ok;
            const resultStr = tr.result
                ? JSON.stringify(tr.result.result || tr.result)
                : "no result";
            div.textContent = `⚙ ${tr.name}: ${ok ? "✓" : "✗"} — ${resultStr}`;
            this.els.narrativeContent.appendChild(div);
        }
        this._scrollToBottom();
    },

    /** Add a decorative turn separator to the narrative. */
    _addTurnSeparator() {
        const div = document.createElement("div");
        div.className = "turn-separator";
        div.innerHTML =
            '<span class="sep-icon">✦</span>';
        this.els.narrativeContent.appendChild(div);
        this._scrollToBottom();
    },

    // ------------------------------------------------------------------
    // Thinking Indicator
    // ------------------------------------------------------------------

    /** Show or hide the "DM is thinking" indicator. */
    _showThinking(visible) {
        this.els.thinkingIndicator.classList.toggle("hidden", !visible);
        if (visible) {
            this._scrollToBottom();
        }
    },

    // ------------------------------------------------------------------
    // NPC Thinking Indicator
    // ------------------------------------------------------------------

    /** Show the NPC thinking indicator with a hint about what they're mulling over. */
    _showNpcThinking(npcData) {
        if (this.els.npcThinkingText) {
            const hint = npcData.hint || "";
            const npcName = npcData.npc_id || "Someone";
            this.els.npcThinkingText.textContent =
                hint
                    ? `${npcName} considers... ${hint}`
                    : `The ${npcName} considers...`;
        }
        this.els.npcThinkingIndicator.classList.remove("hidden");
        this._scrollToBottom();
    },

    /** Hide the NPC thinking indicator. */
    _hideNpcThinking() {
        this.els.npcThinkingIndicator.classList.add("hidden");
    },

    // ------------------------------------------------------------------
    // Sidebar
    // ------------------------------------------------------------------

    /** Render the character info in the sidebar. */
    _renderSidebar() {
        const chara = App.state.character;
        if (!chara) {
            this.els.sidebarName.textContent = "—";
            this.els.sidebarClassLevel.textContent = "—";
            return;
        }

        this.els.sidebarName.textContent = chara.name || "—";

        const cls = chara.character_class || "?";
        const lvl = chara.level || 1;
        this.els.sidebarClassLevel.textContent = `${cls} · Level ${lvl}`;

        // HP bar
        const hp = chara.hp || 0;
        const maxHp = chara.max_hp || 1;
        const pct = Math.max(0, Math.min(100, (hp / maxHp) * 100));
        this.els.hpFill.style.width = pct + "%";
        this.els.hpText.textContent = `${hp} / ${maxHp}`;

        // Color the HP bar
        this.els.hpFill.classList.remove("low", "medium");
        if (pct <= 25) {
            this.els.hpFill.classList.add("low");
        } else if (pct <= 60) {
            this.els.hpFill.classList.add("medium");
        }

        // Ability scores
        const abils = chara.abilities || {};
        const abilKeys = ["STR", "DEX", "CON", "INT", "WIS", "CHA"];
        this.els.statsList.innerHTML = abilKeys
            .map(
                (k) =>
                    `<li><span class="stat-label">${k}</span>` +
                    `<span class="stat-value">${abils[k] ?? "—"}</span></li>`,
            )
            .join("");

        // Inventory
        const inv = chara.inventory || [];
        if (inv.length === 0) {
            this.els.inventoryList.innerHTML =
                '<li class="empty-state">Empty</li>';
        } else {
            this.els.inventoryList.innerHTML = inv
                .map((item) => `<li>${this._esc(item)}</li>`)
                .join("");
        }

        // Location
        const loc = this.state.worldState
            ? this.state.worldState.current_location || "—"
            : "—";
        this.els.locationText.textContent =
            loc.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) ||
            "—";
    },

    // ------------------------------------------------------------------
    // State Management
    // ------------------------------------------------------------------

    /** Apply state changes to the local world state copy. */
    _applyStateChanges(changes) {
        if (!changes || changes.length === 0) return;

        // Initialize world state if needed
        if (!this.state.worldState) {
            this.state.worldState = {
                current_location: "unknown",
                turn_count: 0,
                locations: {},
                quests: {},
                faction_standings: {},
                active_npcs: {},
                inventory: [],
                dm_notes: { plot_threads: [], secrets: [], future_plans: [] },
            };
        }

        for (const change of changes) {
            const action = change.action || "set";
            const path = change.path || "";
            const value = change.value;

            if (action === "set" && path) {
                this._setNested(this.state.worldState, path, value);
            } else if (action === "append" && path && value !== undefined) {
                const arr = this._getNested(this.state.worldState, path);
                if (Array.isArray(arr)) {
                    arr.push(value);
                }
            } else if (action === "remove" && path) {
                this._setNested(this.state.worldState, path, undefined);
            }
        }
    },

    /** Set a value at a dot-separated path in an object. */
    _setNested(obj, path, value) {
        if (typeof path !== "string" || path.length === 0) return;
        const keys = path.split(".");
        if (keys.length === 0 || keys.some((k) => !k)) return;
        const blocked = new Set(["__proto__", "constructor", "prototype"]);
        let current = obj;

        for (let i = 0; i < keys.length - 1; i++) {
            const key = keys[i];
            if (blocked.has(key)) return;
            if (current == null || typeof current !== "object") return;

            if (!Object.prototype.hasOwnProperty.call(current, key)) {
                current[key] = Object.create(null);
            } else {
                const next = current[key];
                if (next == null || typeof next !== "object") return;
            }

            current = current[key];
        }

        const last = keys[keys.length - 1];
        if (blocked.has(last)) return;
        if (current == null || typeof current !== "object") return;
        if (!Object.prototype.hasOwnProperty.call(current, last)) return;

        if (value === undefined) {
            delete current[last];
        } else {
            current[last] = value;
        }
    },

    /** Get a value at a dot-separated path in an object. */
    _getNested(obj, path) {
        const keys = path.split(".");
        const blocked = new Set(["__proto__", "constructor", "prototype"]);
        let current = obj;
        for (const key of keys) {
            if (blocked.has(key)) return undefined;
            if (current == null || typeof current !== "object") return undefined;
            if (!Object.prototype.hasOwnProperty.call(current, key)) return undefined;
            current = current[key];
        }
        return current;
    },

    // ------------------------------------------------------------------
    // Load / Save / Reset
    // ------------------------------------------------------------------

    /** Load initial world state from the server (POST /api/reset). */
    async _loadState() {
        // If we already have a world state, keep it (continuing a game)
        if (this.state.worldState) return;

        try {
            const resp = await fetch("/api/reset", { method: "POST" });
            const data = await resp.json();
            if (data.ok && data.state) {
                this.state.worldState = data.state;
            }
        } catch (e) {
            // Offline — use a minimal default
            this.state.worldState = {
                current_location: "unknown",
                turn_count: 0,
            };
        }
    },

    /** Start a new game — clear state and return to character view. */
    _newGame() {
        if (this.state.isThinking) return;
        // Confirm with the user
        if (!confirm("Start a new game? Progress will be lost.")) return;

        this.state.worldState = null;
        this.state.turnCount = 0;
        this.state.hasStarted = false;

        // Clear the narrative
        this.els.narrativeContent.innerHTML =
            '<p class="narrative-welcome">Your adventure awaits...</p>';

        App.navigate("character");
    },

    /** Save the current game state via the server. */
    async _saveGame() {
        if (this.state.isThinking) return;
        this.els.saveGameBtn.disabled = true;
        this.els.saveGameBtn.textContent = "Saving...";

        try {
            const resp = await fetch("/api/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    state: this.state.worldState || {},
                    name: "manual-save",
                }),
            });
            const data = await resp.json();
            if (data.ok) {
                this.els.saveGameBtn.textContent = "\u2713 Saved";
                setTimeout(() => {
                    this.els.saveGameBtn.textContent = "Save Game";
                    this.els.saveGameBtn.disabled = false;
                }, 2000);
            } else {
                this.els.saveGameBtn.textContent = "\u2717 Failed";
                setTimeout(() => {
                    this.els.saveGameBtn.textContent = "Save Game";
                    this.els.saveGameBtn.disabled = false;
                }, 2000);
            }
        } catch (e) {
            this.els.saveGameBtn.textContent = "\u2717 Error";
            setTimeout(() => {
                this.els.saveGameBtn.textContent = "Save Game";
                this.els.saveGameBtn.disabled = false;
            }, 2000);
        }
    },

    // ------------------------------------------------------------------
    // Utilities
    // ------------------------------------------------------------------

    /** Scroll the narrative pane to the bottom. */
    _scrollToBottom() {
        if (!this.state.autoScroll) return;
        // Use a small delay to let the DOM update
        requestAnimationFrame(() => {
            this.els.narrativePane.scrollTop =
                this.els.narrativePane.scrollHeight;
        });
    },

    /** Escape HTML special chars. */
    _esc(str) {
        if (typeof str !== "string") return String(str || "");
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    },

    /** Strip XML/HTML-like tags from a string. */
    _stripXmlTags(str) {
        return str.replace(/<\/?[a-zA-Z_][^>]*>/g, '');
    },
};

document.addEventListener("DOMContentLoaded", () => GameView.init());
