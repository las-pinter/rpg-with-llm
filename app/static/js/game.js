/**
 * LLM-Powered RPG — Game View
 *
 * The main gameplay interface: narrative display, status sidebar, and
 * action input.  Communicates with the DM backend via POST /api/turn
 * and GET /api/game/stream (SSE).
 */
const GameView = {
    /** Runtime game state. */
    state: {
        worldState: null,
        turnCount: 0,
        isThinking: false,
        hasStarted: false,
        autoScroll: true,
        tokenUsage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
        showTokens: false,
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
            goldDisplay: document.getElementById("gold-display"),
            goldAmount: document.getElementById("gold-amount"),
            inventoryList: document.getElementById("inventory-list"),
            locationText: document.getElementById("location-text"),
            npcList: document.getElementById("npc-list"),
            collapseBtn: document.getElementById("sidebar-collapse"),

            // Token Usage
            tokenToggle: document.getElementById("token-toggle"),
            tokenDisplay: document.getElementById("token-display"),
            tokenPrompt: document.getElementById("token-prompt"),
            tokenCompletion: document.getElementById("token-completion"),
            tokenTotal: document.getElementById("token-total"),

            // Input
            playerInput: document.getElementById("player-input"),
            submitBtn: document.getElementById("submit-action"),
            quickActions: document.getElementById("quick-actions"),
            newGameBtn: document.getElementById("new-game-btn"),
            saveGameBtn: document.getElementById("save-game-btn"),
            loadGameBtn: document.getElementById("load-game-btn"),

            // Save modal
            saveModal: document.getElementById("save-modal"),
            saveModalOverlay: document.getElementById("save-modal-overlay"),
            saveNameInput: document.getElementById("save-name-input"),
            saveConfirmBtn: document.getElementById("save-confirm"),
            saveCancelBtn: document.getElementById("save-cancel"),
            saveStatus: document.getElementById("save-status"),
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
        this.els.saveGameBtn.addEventListener("click", () => this._showSaveModal());

        // Load Game button
        if (this.els.loadGameBtn) {
            this.els.loadGameBtn.addEventListener("click", () => this._showLoadModal());
        }

        // Save modal controls
        this.els.saveConfirmBtn.addEventListener("click", () => this._confirmSave());
        this.els.saveCancelBtn.addEventListener("click", () => this._hideSaveModal());
        this.els.saveModalOverlay.addEventListener("click", () => this._hideSaveModal());
        this.els.saveNameInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                this._confirmSave();
            }
        });

        // Sidebar collapse
        this.els.collapseBtn.addEventListener("click", () => {
            const sidebar = document.getElementById("status-sidebar");
            sidebar.classList.toggle("collapsed");
            this.els.collapseBtn.textContent = sidebar.classList.contains("collapsed") ? "\u25B6" : "\u25C0";

            // Toggle game grid layout
            const gameView = document.getElementById("view-game");
            gameView.classList.toggle("sidebar-collapsed");
        });

        // Token usage toggle
        this.els.tokenToggle.addEventListener("click", () => {
            this.state.showTokens = !this.state.showTokens;
            this.els.tokenDisplay.classList.toggle("hidden", !this.state.showTokens);
            this.els.tokenToggle.textContent = this.state.showTokens ? "Hide Tokens" : "Show Tokens";
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
    async _onShow() {
        await this._loadState();
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
            // Keep a token buffer for internal parsing but don't display raw tokens
            let tokenBuffer = "";

            SSEClient.connect(
                input,
                App.state.provider,
                {
                    onToken: ((token) => {
                        tokenBuffer += token;
                    }).bind(this),

                    onNpcThinking: ((npcData) => {
                        this._showNpcThinking(npcData);
                    }).bind(this),

                    onStateUpdate: ((update) => {
                        if (update && update.state) {
                            this.state.worldState = update.state;
                            this.state.turnCount = update.turn_count || this.state.turnCount + 1;
                        }
                    }).bind(this),

                    onNarrative: ((narrative) => {
                        this._hideNpcThinking();
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

                    onTokenUsage: ((usage) => {
                        if (usage) {
                            this.state.tokenUsage.prompt_tokens += usage.prompt_tokens || 0;
                            this.state.tokenUsage.completion_tokens += usage.completion_tokens || 0;
                            this.state.tokenUsage.total_tokens += usage.total_tokens || 0;
                        }
                        this._renderSidebar();
                    }).bind(this),

                    onError: ((msg) => {
                        this._hideNpcThinking();
                        SSEClient.disconnect();
                        reject(new Error(msg || "SSE connection failed"));
                    }).bind(this),
                },
                // Pass state and character for continuity
                this.state.worldState,
                App.state.character,
                App.state.npcProvider,
                App.state.summarizerProvider,
            );
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

            // Accumulate token usage from POST response
            if (data.token_usage) {
                this.state.tokenUsage.prompt_tokens += data.token_usage.prompt_tokens || 0;
                this.state.tokenUsage.completion_tokens += data.token_usage.completion_tokens || 0;
                this.state.tokenUsage.total_tokens += data.token_usage.total_tokens || 0;
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
        // Strip any residual XML tags from the narrative text
        text = text.replace(/<[^>]*>/g, '');
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

        // Gold — read from worldState
        const gold = (this.state.worldState && this.state.worldState.gold) || 0;
        this.els.goldAmount.textContent = gold;

        // Inventory — read from worldState, not character
        const inv = (this.state.worldState && this.state.worldState.inventory) || [];
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

        // Known NPCs
        const npcs = (this.state.worldState && this.state.worldState.active_npcs) || {};
        const npcIds = Object.keys(npcs);
        if (npcIds.length === 0) {
            this.els.npcList.innerHTML =
                '<li class="empty-state">None yet</li>';
        } else {
            this.els.npcList.innerHTML = npcIds
                .map((id) => {
                    const npc = npcs[id] || {};
                    const name = npc.name || id;
                    const lastSeen = npc.last_seen_turn;
                    let label = this._esc(name);
                    if (lastSeen != null) {
                        label +=
                            ` <span class="npc-last-seen">` +
                            `(turn ${this._esc(String(lastSeen))})</span>`;
                    }
                    return `<li>${label}</li>`;
                })
                .join("");
        }

        // Token usage
        const tu = this.state.tokenUsage || {};
        this.els.tokenPrompt.textContent = tu.prompt_tokens ?? 0;
        this.els.tokenCompletion.textContent = tu.completion_tokens ?? 0;
        this.els.tokenTotal.textContent = tu.total_tokens ?? 0;
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
                gold: 0,
                dm_notes: { plot_threads: [], secrets: [], future_plans: [] },
            };
        }

        for (const change of changes) {
            const action = change.action || "set";
            const path = change.path || "";
            const value = change.value;

            if (action === "set" && path) {
                this._setNested(this.state.worldState, path, value);
            } else if (action === "add" && path && value !== undefined) {
                const current = this._getNested(this.state.worldState, path);
                if (typeof current === "number") {
                    this._setNested(this.state.worldState, path, current + Number(value));
                }
            } else if (action === "append" && path && value !== undefined) {
                const arr = this._getNested(this.state.worldState, path);
                if (Array.isArray(arr)) {
                    arr.push(value);
                }
            } else if (action === "remove" && path) {
                const current = this._getNested(this.state.worldState, path);
                if (Array.isArray(current)) {
                    this._setNested(
                        this.state.worldState,
                        path,
                        current.filter((item) => item !== value),
                    );
                } else if (typeof current === 'object' && current !== null) {
                    delete current[value];
                } else {
                    this._setNested(this.state.worldState, path, undefined);
                }
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
                gold: 0,
            };
        }

        // Seed worldState with character's starting equipment and gold
        if (App.state.character) {
            if (App.state.character.inventory) {
                this.state.worldState.inventory = [...App.state.character.inventory];
            }
            if (App.state.character.gold != null) {
                this.state.worldState.gold = App.state.character.gold;
            }
        }
    },

    /** Start a new game — clear state and return to character view. */
    _newGame() {
        if (this.state.isThinking) return;
        if (!confirm("Start a new game? Progress will be lost.")) return;

        this.state.worldState = null;
        this.state.turnCount = 0;
        this.state.hasStarted = false;
        this.state.tokenUsage = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };

        // Clear the narrative
        this.els.narrativeContent.innerHTML =
            '<p class="narrative-welcome">Your adventure awaits...</p>';

        App.navigate("character");
    },

    // ------------------------------------------------------------------
    // Save Modal
    // ------------------------------------------------------------------

    /** Show the save game modal with autogenerated name. */
    _showSaveModal() {
        if (this.state.isThinking) return;

        // Auto-generate a suggested name
        const charName = App.state.character ? App.state.character.name : "Adventure";
        const date = new Date().toLocaleString();
        this.els.saveNameInput.value = `${charName} - ${date}`;
        this.els.saveStatus.textContent = "";
        this.els.saveStatus.className = "save-status";
        this.els.saveModal.classList.remove("hidden");
        this.els.saveModalOverlay.classList.remove("hidden");
        this.els.saveNameInput.focus();
        this.els.saveNameInput.select();
    },

    /** Hide the save modal. */
    _hideSaveModal() {
        this.els.saveModal.classList.add("hidden");
        this.els.saveModalOverlay.classList.add("hidden");
    },

    /** Confirm and execute the save. */
    async _confirmSave() {
        const name = this.els.saveNameInput.value.trim();
        if (!name) {
            this.els.saveStatus.textContent = "Please enter a save name.";
            this.els.saveStatus.className = "save-status save-status-error";
            return;
        }

        this.els.saveConfirmBtn.disabled = true;
        this.els.saveConfirmBtn.textContent = "Saving...";
        this.els.saveStatus.textContent = "";
        this.els.saveStatus.className = "save-status";

        try {
            const resp = await fetch("/api/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    state: this.state.worldState || {},
                    character: App.state.character || undefined,
                    name: name,
                }),
            });
            const data = await resp.json();
            if (data.ok) {
                this.els.saveStatus.textContent = `✓ Saved as "${data.name}"`;
                this.els.saveStatus.className = "save-status save-status-ok";
                setTimeout(() => this._hideSaveModal(), 1500);
            } else {
                this.els.saveStatus.textContent = `✗ Failed: ${data.error || "Unknown error"}`;
                this.els.saveStatus.className = "save-status save-status-error";
            }
        } catch (e) {
            this.els.saveStatus.textContent = `✗ Error: ${e.message}`;
            this.els.saveStatus.className = "save-status save-status-error";
        } finally {
            this.els.saveConfirmBtn.disabled = false;
            this.els.saveConfirmBtn.textContent = "Save";
        }
    },

    // ------------------------------------------------------------------
    // Load Game
    // ------------------------------------------------------------------

    /** Show the load game modal. */
    async _showLoadModal() {
        const loadModal = document.getElementById("load-modal");
        const loadOverlay = document.getElementById("load-modal-overlay");
        const loadList = document.getElementById("load-list");

        if (!loadModal || !loadList) return;

        loadList.innerHTML = '<p class="empty-state">Loading saves...</p>';
        loadModal.classList.remove("hidden");
        loadOverlay.classList.remove("hidden");

        try {
            const resp = await fetch("/api/saves");
            const data = await resp.json();
            const saves = data.saves || [];

            if (saves.length === 0) {
                loadList.innerHTML = '<p class="empty-state">No saved games found.</p>';
                return;
            }

            loadList.innerHTML = saves
                .map(
                    (s) => `
                <div class="save-card" data-name="${this._esc(s.name || s.character_name || "Unknown")}">
                    <div class="save-info">
                        <h3>${this._esc(s.character_name || "Unknown")}</h3>
                        <p class="save-meta">
                            Turn ${s.turn_count ?? "?"} · ${s.timestamp ? this._formatTimestamp(s.timestamp) : ""}
                        </p>
                    </div>
                    <div class="save-actions">
                        <button class="btn btn-sm btn-load-save">Load</button>
                        <button class="btn btn-sm btn-danger btn-delete-save">Del</button>
                    </div>
                </div>
            `,
                )
                .join("");

            // Bind load buttons
            loadList.querySelectorAll(".btn-load-save").forEach((btn) => {
                btn.addEventListener("click", () => {
                    const card = btn.closest(".save-card");
                    const saveName = card.dataset.name;
                    this._loadGame(saveName);
                });
            });

            // Bind delete buttons
            loadList.querySelectorAll(".btn-delete-save").forEach((btn) => {
                btn.addEventListener("click", async () => {
                    const card = btn.closest(".save-card");
                    const saveName = card.dataset.name;
                    if (!confirm(`Delete save "${saveName}"?`)) return;
                    try {
                        await fetch(`/api/delete/${encodeURIComponent(saveName)}`, { method: "DELETE" });
                    } catch (_) { /* ignore */ }
                    this._showLoadModal(); // Refresh list
                });
            });
        } catch (e) {
            loadList.innerHTML = `<p class="empty-state">Error loading saves: ${e.message}</p>`;
        }

        // Close handlers
        const closeModal = () => {
            loadModal.classList.add("hidden");
            loadOverlay.classList.add("hidden");
        };
        loadOverlay.onclick = closeModal;
        const closeBtn = loadModal.querySelector(".modal-close");
        if (closeBtn) closeBtn.onclick = closeModal;
    },

    /** Load a saved game: fetch state + character, restore them, and enter game. */
    async _loadGame(saveName) {
        const loadModal = document.getElementById("load-modal");
        const loadOverlay = document.getElementById("load-modal-overlay");

        try {
            const resp = await fetch(`/api/load/${encodeURIComponent(saveName)}`, { method: "POST" });
            const data = await resp.json();

            if (data.ok) {
                // Restore world state
                this.state.worldState = data.state;
                this.state.turnCount = data.state.turn_count || 0;
                this.state.hasStarted = true;

                // Restore character if companion data exists
                if (data.character) {
                    App.state.character = data.character;
                }

                // Clear and rebuild narrative
                this.els.narrativeContent.innerHTML =
                    '<p class="narrative-welcome">Loading saved game...</p>';

                // Hide modal
                loadModal.classList.add("hidden");
                loadOverlay.classList.add("hidden");

                // Add a brief load message
                this._addNarrative(`[Game loaded: "${saveName}"]`, {});
                this._addTurnSeparator();
                this._renderSidebar();
                this._enableInput();
            } else {
                alert(`Failed to load save: ${data.error || "Unknown error"}`);
            }
        } catch (e) {
            alert(`Failed to load save: ${e.message}`);
        }
    },

    /** Format a timestamp string for display. */
    _formatTimestamp(ts) {
        if (!ts) return "";
        // Try parsing YYYYMMDD_HHMMSS_ffffff format
        const m = ts.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
        if (m) {
            const date = new Date(
                parseInt(m[1]), parseInt(m[2]) - 1, parseInt(m[3]),
                parseInt(m[4]), parseInt(m[5]), parseInt(m[6]),
            );
            return date.toLocaleString();
        }
        return ts;
    },

    // ------------------------------------------------------------------
    // Utilities
    // ------------------------------------------------------------------

    /** Scroll the narrative pane to the bottom. */
    _scrollToBottom() {
        if (!this.state.autoScroll) return;
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

    /** Strip XML/HTML-like tags, markdown bold artifacts, and backtick state-change attributes. */
    _stripXmlTags(str) {
        if (typeof str !== "string") return "";
        let clean = str.replace(/<[^>]*>?/g, '');
        clean = clean.replace(/\*\*[a-zA-Z_]+\*\*/g, '');
        clean = clean.replace(/`[^`]*?(?:action=|path=|value=)[^`]*`/g, '');
        return clean;
    },
};

document.addEventListener("DOMContentLoaded", () => GameView.init());
