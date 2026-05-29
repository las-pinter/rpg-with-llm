/**
 * LLM-Powered RPG — Game View
 *
 * The main gameplay interface: narrative display, status sidebar, and
 * action input.  Communicates with the DM backend via POST /api/game/stream (SSE).
 */
const GameView: {
    state: GameState;
    els: GameElements;
    _storyKeyHandler: ((e: KeyboardEvent) => void) | null;
    init(): void;
    _onShow(): Promise<void>;
    _enableInput(): void;
    _disableInput(): void;
    _submit(): void;
    _sendTurn(input: string): Promise<void>;
    _sendTurnSSE(input: string): Promise<void>;
    _addPlayerAction(action: string): void;
    _addNarrative(text: string, opts?: { isError?: boolean }): void;
    _showToolResults(results: any[]): void;
    _addTurnSeparator(): void;
    _showThinking(visible: boolean): void;
    _showNpcThinking(npcData: { npc_id?: string; hint?: string }): void;
    _hideNpcThinking(): void;
    _renderSidebar(): void;
    _applyStateChanges(changes: any[]): void;
    _setNested(obj: any, path: string, value: any): void;
    _getNested(obj: any, path: string): any;
    _loadState(): Promise<void>;
    _newGame(): void;
    _showSaveModal(): void;
    _hideSaveModal(): void;
    _confirmSave(): Promise<void>;
    _showLoadModal(): Promise<void>;
    _loadGame(saveName: string): Promise<void>;
    _showStoryModal(): Promise<void>;
    _hideStoryModal(): void;
    _scrollToBottom(): void;
    _stripXmlTags(str: string): string;
} = {
    /** Runtime game state. */
    state: {
        worldState: null,
        turnCount: 0,
        isThinking: false,
        hasStarted: false,
        autoScroll: true,
        tokenUsage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
        latestTokenUsage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
        showTokens: false,
    },

    /** DOM element references. */
    els: {} as GameElements,

    _storyKeyHandler: null,

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
            charAppearance: document.getElementById("sidebar-appearance"),
            charBackstory: document.getElementById("sidebar-backstory"),
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
            tokenLatestPrompt: document.getElementById("token-latest-prompt"),
            tokenLatestCompletion: document.getElementById("token-latest-completion"),
            tokenLatestTotal: document.getElementById("token-latest-total"),

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
        } as GameElements;

        // Submit action
        this.els.submitBtn!.addEventListener("click", () => this._submit());
        this.els.playerInput!.addEventListener("keydown", (e: KeyboardEvent) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                this._submit();
            }
        });

        // New Game button
        this.els.newGameBtn!.addEventListener("click", () => this._newGame());

        // Save Game button
        this.els.saveGameBtn!.addEventListener("click", () => this._showSaveModal());

        // Load Game button
        if (this.els.loadGameBtn) {
            this.els.loadGameBtn.addEventListener("click", () => this._showLoadModal());
        }

        // Save modal controls
        this.els.saveConfirmBtn!.addEventListener("click", () => this._confirmSave());
        this.els.saveCancelBtn!.addEventListener("click", () => this._hideSaveModal());
        this.els.saveModalOverlay!.addEventListener("click", () => this._hideSaveModal());
        this.els.saveNameInput!.addEventListener("keydown", (e: KeyboardEvent) => {
            if (e.key === "Enter") {
                e.preventDefault();
                this._confirmSave();
            }
        });

        // Sidebar collapse
        this.els.collapseBtn!.addEventListener("click", () => {
            const sidebar = document.getElementById("status-sidebar");
            if (sidebar) {
                sidebar.classList.toggle("collapsed");
                this.els.collapseBtn!.textContent = sidebar.classList.contains("collapsed") ? "\u25C0" : "\u25B6";
            }
        });

        // Token usage toggle
        this.els.tokenToggle!.addEventListener("click", () => {
            this.state.showTokens = !this.state.showTokens;
            this.els.tokenDisplay!.classList.toggle("hidden", !this.state.showTokens);
            this.els.tokenToggle!.textContent = this.state.showTokens ? "Hide Tokens" : "Show Tokens";
        });

        // Story modal button
        const readStoryBtn = document.getElementById("read-story-btn");
        const storyCloseBtn = document.getElementById("story-close-btn");
        if (readStoryBtn) readStoryBtn.addEventListener("click", () => this._showStoryModal());
        if (storyCloseBtn) storyCloseBtn.addEventListener("click", () => this._hideStoryModal());

        // Click outside to close story modal
        const storyModal = document.getElementById("story-modal");
        if (storyModal) {
            storyModal.addEventListener("click", (e: Event) => {
                if (e.target === storyModal) this._hideStoryModal();
            });
        }

        // Auto-scroll detection — pause on manual scroll-up
        this.els.narrativePane!.addEventListener("scroll", () => {
            const el = this.els.narrativePane!;
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
    async _onShow(): Promise<void> {
        // Handle saved game load triggered from character view
        if (App.state.loadSaveName) {
            const saveName = App.state.loadSaveName;
            App.state.loadSaveName = null;
            await this._loadGame(saveName);
            return;
        }

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
        this.els.playerInput!.disabled = false;
        this.els.submitBtn!.disabled = false;
        this.els.playerInput!.focus();
    },

    /** Disable the input field and button (during DM thinking). */
    _disableInput() {
        this.els.playerInput!.disabled = true;
        this.els.submitBtn!.disabled = true;
    },

    /** Submit the current player action. */
    _submit() {
        const input = this.els.playerInput!.value.trim();
        if (!input || this.state.isThinking) return;

        this.els.playerInput!.value = "";
        this._sendTurn(input);
    },

    // ------------------------------------------------------------------
    // Turn Processing
    // ------------------------------------------------------------------

    /** Send a player action to the DM and process the response. */
    async _sendTurn(input: string): Promise<void> {
        if (this.state.isThinking) return;

        this.state.isThinking = true;
        this._disableInput();
        this._hideNpcThinking();
        this._showThinking(true);

        // Add the player's action to the narrative
        this._addPlayerAction(input);

        try {
            await this._sendTurnSSE(input);
        } catch (err) {
            const error = err as Error;
            let msg = error.message;
            if (error.name === "TimeoutError") {
                msg = "The DM is taking too long — check your connection and try again.";
            } else if (error.message === "Failed to fetch") {
                msg = "Cannot reach the game server. Is it running?";
            }
            this._addNarrative(`[${msg}]`, { isError: true });
            this._addTurnSeparator();
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
    _sendTurnSSE(input: string): Promise<void> {
        return new Promise<void>((resolve, reject) => {
            SSEClient.connect(
                input,
                App.state.provider,
                {
                    onNpcThinking: (npcData) => {
                        this._showNpcThinking(npcData);
                    },

                    onStateUpdate: (update) => {
                        if (update && update.state) {
                            this.state.worldState = update.state;
                            this.state.turnCount = update.turn_count || this.state.turnCount + 1;
                        }
                    },

                    onNarrative: (narrative) => {
                        this._hideNpcThinking();
                        this._addNarrative(narrative);
                        this._scrollToBottom();
                    },

                    onDone: (turnCount) => {
                        this._hideNpcThinking();
                        this.state.turnCount = turnCount ?? this.state.turnCount + 1;
                        this._renderSidebar();
                        this._addTurnSeparator();
                        resolve();
                    },

                    onTokenUsage: (data) => {
                        if (data) {
                            // REPLACE accumulated (don't add — backend already accumulates!)
                            if (data.usage) {
                                this.state.tokenUsage = data.usage;
                            }
                            // Store per-turn latest
                            if (data.latest) {
                                this.state.latestTokenUsage = data.latest;
                            }
                        }
                        this._renderSidebar();
                    },

                    onError: (msg) => {
                        this._hideNpcThinking();
                        SSEClient.disconnect();
                        reject(new Error(msg || "SSE connection failed"));
                    },
                },
                // Pass state and character for continuity
                this.state.worldState,
                App.state.character,
                App.state.npcProvider,
                App.state.summarizerProvider,
            );
        });
    },



    // ------------------------------------------------------------------
    // Narrative Display
    // ------------------------------------------------------------------

    /** Add the player's action bubble to the narrative. */
    _addPlayerAction(action: string) {
        const div = document.createElement("div");
        div.className = "turn-player";
        div.textContent = action;
        this.els.narrativeContent!.appendChild(div);
        this._scrollToBottom();
    },

    /** Append DM narrative text to the narrative pane. */
    _addNarrative(text: string, opts?: { isError?: boolean }) {
        opts = opts || {};
        // Strip angle brackets to prevent tag-like content from surviving sanitization
        text = text.replace(/[<>]/g, '');
        if (!text.trim()) return;  // Don't add empty narrative divs
        const div = document.createElement("div");
        div.className = "turn-narrative";

        // Render paragraphs from the narrative text
        const paragraphs = text.split("\n").filter((p) => p.trim());
        if (paragraphs.length === 0) {
            div.innerHTML = "<p>" + _esc(text) + "</p>";
        } else {
            div.innerHTML = paragraphs
                .map((p) => "<p>" + _esc(p) + "</p>")
                .join("");
        }

        if (opts.isError) {
            div.classList.add("turn-error");
        }

        this.els.narrativeContent!.appendChild(div);
        this._scrollToBottom();
    },

    /** Show tool results as subtle narrative annotations. */
    _showToolResults(results: any[]) {
        for (const tr of results) {
            const div = document.createElement("div");
            div.className = "turn-tool-result";
            const ok = tr.result && tr.result.ok;
            const resultStr = tr.result
                ? JSON.stringify(tr.result.result || tr.result)
                : "no result";
            div.textContent = `⚙ ${tr.name}: ${ok ? "✓" : "✗"} — ${resultStr}`;
            this.els.narrativeContent!.appendChild(div);
        }
        this._scrollToBottom();
    },

    /** Add a decorative turn separator to the narrative. */
    _addTurnSeparator() {
        const div = document.createElement("div");
        div.className = "turn-separator";
        div.innerHTML =
            '<span class="sep-icon">✦</span>';
        this.els.narrativeContent!.appendChild(div);
        this._scrollToBottom();
    },

    // ------------------------------------------------------------------
    // Thinking Indicator
    // ------------------------------------------------------------------

    /** Show or hide the "DM is thinking" indicator. */
    _showThinking(visible: boolean) {
        this.els.thinkingIndicator!.classList.toggle("hidden", !visible);
        if (visible) {
            this._scrollToBottom();
        }
    },

    // ------------------------------------------------------------------
    // NPC Thinking Indicator
    // ------------------------------------------------------------------

    /** Show the NPC thinking indicator with a hint about what they're mulling over. */
    _showNpcThinking(npcData: { npc_id?: string; hint?: string }) {
        if (this.els.npcThinkingText) {
            const hint = npcData.hint || "";
            const npcName = npcData.npc_id || "Someone";
            this.els.npcThinkingText.textContent =
                hint
                    ? `${npcName} considers... ${hint}`
                    : `The ${npcName} considers...`;
        }
        this.els.npcThinkingIndicator!.classList.remove("hidden");
        this._scrollToBottom();
    },

    /** Hide the NPC thinking indicator. */
    _hideNpcThinking() {
        this.els.npcThinkingIndicator!.classList.add("hidden");
    },

    // ------------------------------------------------------------------
    // Sidebar
    // ------------------------------------------------------------------

    /** Render the character info in the sidebar. */
    _renderSidebar() {
        const chara = App.state.character;
        if (!chara) {
            this.els.sidebarName!.textContent = "—";
            this.els.sidebarClassLevel!.textContent = "—";
            return;
        }

        this.els.sidebarName!.textContent = chara.name || "—";

        const cls = chara.character_class || "?";
        const lvl = chara.level || 1;
        this.els.sidebarClassLevel!.textContent = `${cls} · Level ${lvl}`;

        // Character info — appearance & backstory
        this.els.charAppearance!.textContent = chara.appearance || "—";
        this.els.charBackstory!.textContent = chara.backstory || "—";

        // HP bar
        const hp = chara.hp || 0;
        const maxHp = chara.max_hp || 1;
        const pct = Math.max(0, Math.min(100, (hp / maxHp) * 100));
        this.els.hpFill!.style.width = pct + "%";
        this.els.hpText!.textContent = `${hp} / ${maxHp}`;

        // Color the HP bar
        this.els.hpFill!.classList.remove("low", "medium");
        if (pct <= 25) {
            this.els.hpFill!.classList.add("low");
        } else if (pct <= 60) {
            this.els.hpFill!.classList.add("medium");
        }

        // Ability scores
        const abils = chara.abilities || {};
        const abilKeys = ["STR", "DEX", "CON", "INT", "WIS", "CHA"];
        this.els.statsList!.innerHTML = abilKeys
            .map(
                (k: string) =>
                    `<li><span class="stat-label">${k}</span>` +
                    `<span class="stat-value">${abils[k] ?? "—"}</span></li>`,
            )
            .join("");

        // Gold — read from worldState
        const gold = (this.state.worldState && this.state.worldState.gold) || 0;
        this.els.goldAmount!.textContent = String(gold);

        // Inventory — read from worldState, not character
        const inv = (this.state.worldState && this.state.worldState.inventory) || [];
        if (inv.length === 0) {
            this.els.inventoryList!.innerHTML =
                '<li class="empty-state">Empty</li>';
        } else {
            this.els.inventoryList!.innerHTML = inv
                .map((item: string) => `<li>${_esc(item)}</li>`)
                .join("");
        }

        // Location
        const loc = this.state.worldState
            ? this.state.worldState.current_location || "—"
            : "—";
        this.els.locationText!.textContent =
            loc.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()) ||
            "—";

        // Known NPCs
        const npcs = (this.state.worldState && this.state.worldState.active_npcs) || {};
        const npcIds = Object.keys(npcs);
        if (npcIds.length === 0) {
            this.els.npcList!.innerHTML =
                '<li class="empty-state">None yet</li>';
        } else {
            this.els.npcList!.innerHTML = npcIds
                .map((id: string) => {
                    const npc = npcs[id] || {};
                    const name = npc.name || id;
                    const lastSeen = npc.last_seen_turn;
                    let label = _esc(name);
                    if (lastSeen != null) {
                        label +=
                            ` <span class="npc-last-seen">` +
                            `(turn ${_esc(String(lastSeen))})</span>`;
                    }
                    return `<li>${label}</li>`;
                })
                .join("");
        }

        // Token usage — accumulated
        const tu = this.state.tokenUsage || {};
        this.els.tokenPrompt!.textContent = String(tu.prompt_tokens ?? 0);
        this.els.tokenCompletion!.textContent = String(tu.completion_tokens ?? 0);
        this.els.tokenTotal!.textContent = String(tu.total_tokens ?? 0);

        // Token usage — latest per-turn
        const latest = this.state.latestTokenUsage || {};
        this.els.tokenLatestPrompt!.textContent = String(latest.prompt_tokens ?? 0);
        this.els.tokenLatestCompletion!.textContent = String(latest.completion_tokens ?? 0);
        this.els.tokenLatestTotal!.textContent = String(latest.total_tokens ?? 0);
    },

    // ------------------------------------------------------------------
    // State Management
    // ------------------------------------------------------------------

    /** Apply state changes to the local world state copy. */
    _applyStateChanges(changes: any[]) {
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
                        current.filter((item: unknown) => item !== value),
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
    _setNested(obj: any, path: string, value: any) {
        if (typeof path !== "string" || path.length === 0) return;
        const keys = path.split(".");
        if (keys.length === 0 || keys.some((k: string) => !k)) return;
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
    _getNested(obj: any, path: string): any {
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
    async _loadState(): Promise<void> {
        // If we already have a world state, keep it (continuing a game)
        if (this.state.worldState) return;

        try {
            const resp = await fetch("/api/reset", { method: "POST" });
            const data = await resp.json();
            if (data.ok && data.state) {
                this.state.worldState = data.state;
            }
        } catch (_) {
            // Offline — use a minimal default
            this.state.worldState = {
                current_location: "unknown",
                turn_count: 0,
                gold: 0,
            };
        }

        // Seed worldState with character's starting equipment and gold
        if (App.state.character) {
            this.state.worldState!.character_name = App.state.character.name || "";
            if (App.state.character.inventory) {
                this.state.worldState!.inventory = [...App.state.character.inventory];
            }
            if (App.state.character.gold != null) {
                this.state.worldState!.gold = App.state.character.gold;
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
        this.state.latestTokenUsage = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };

        // Clear the narrative
        this.els.narrativeContent!.innerHTML =
            '<p class="narrative-welcome">Your adventure awaits...</p>';

        App.navigate("character");
    },

    // ------------------------------------------------------------------
    // Save Modal
    // ------------------------------------------------------------------

    /** Show the save game modal with autogenerated name. */
    _showSaveModal() {
        if (this.state.isThinking) return;

        // Reset all save states: show form, hide loading/success
        const formGroup = document.querySelector("#save-modal .form-group") as HTMLElement | null;
        const saveFooter = document.querySelector("#save-modal .modal-footer") as HTMLElement | null;
        const saveLoading = document.getElementById("save-loading");
        const saveSuccess = document.getElementById("save-success");
        if (formGroup) formGroup.style.display = "";
        if (saveFooter) saveFooter.style.display = "";
        if (saveLoading) saveLoading.style.display = "none";
        if (saveSuccess) saveSuccess.style.display = "none";

        // Auto-generate a suggested name
        const charName = App.state.character ? App.state.character.name : "Adventure";
        const date = new Date().toLocaleString();
        this.els.saveNameInput!.value = `${charName} - ${date}`;
        this.els.saveStatus!.textContent = "";
        this.els.saveStatus!.className = "save-status";
        this.els.saveModal!.classList.remove("hidden");
        this.els.saveModalOverlay!.classList.remove("hidden");
        this.els.saveNameInput!.focus();
        this.els.saveNameInput!.select();
    },

    /** Hide the save modal. */
    _hideSaveModal() {
        this.els.saveModal!.classList.add("hidden");
        this.els.saveModalOverlay!.classList.add("hidden");
    },

    /** Confirm and execute the save. */
    async _confirmSave(): Promise<void> {
        const name = this.els.saveNameInput!.value.trim();
        if (!name) {
            this.els.saveStatus!.textContent = "Please enter a save name.";
            this.els.saveStatus!.className = "save-status save-status-error";
            return;
        }

        // Get elements for state transitions
        const formGroup = document.querySelector("#save-modal .form-group") as HTMLElement | null;
        const saveFooter = document.querySelector("#save-modal .modal-footer") as HTMLElement | null;
        const saveLoading = document.getElementById("save-loading");
        const saveSuccess = document.getElementById("save-success");

        // Hide form, show loading spinner
        if (formGroup) formGroup.style.display = "none";
        if (saveFooter) saveFooter.style.display = "none";
        if (saveLoading) saveLoading.style.display = "block";
        this.els.saveStatus!.textContent = "";
        this.els.saveStatus!.className = "save-status";

        try {
            // Embed character data inside the state dict for single-file save
            const stateData = this.state.worldState ? { ...this.state.worldState } : {};
            if (App.state.character) {
                // Ensure character ID is always a string (UUID), not a number
                const charData = { ...App.state.character };
                if (charData.id != null) charData.id = String(charData.id);
                stateData._character = charData;
                stateData.character_name = charData.name || "";
                stateData.character_id = charData.id;
            }
            const resp = await fetch("/api/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    state: stateData,
                    name: name,
                }),
            });
            const data = await resp.json();

            // Hide loading
            if (saveLoading) saveLoading.style.display = "none";

            if (data.ok) {
                // Show success briefly, then close
                if (saveSuccess) saveSuccess.style.display = "block";
                setTimeout(() => {
                    this._hideSaveModal();
                    // Reset for next open
                    if (formGroup) formGroup.style.display = "";
                    if (saveFooter) saveFooter.style.display = "";
                    if (saveSuccess) saveSuccess.style.display = "none";
                }, 1200);
            } else {
                // Show error, restore form
                if (formGroup) formGroup.style.display = "";
                if (saveFooter) saveFooter.style.display = "";
                this.els.saveStatus!.textContent = `✗ Failed: ${data.error || "Unknown error"}`;
                this.els.saveStatus!.className = "save-status save-status-error";
            }
        } catch (e) {
            const error = e as Error;
            if (saveLoading) saveLoading.style.display = "none";
            if (formGroup) formGroup.style.display = "";
            if (saveFooter) saveFooter.style.display = "";
            this.els.saveStatus!.textContent = `✗ Error: ${error.message}`;
            this.els.saveStatus!.className = "save-status save-status-error";
        }
    },

    // ------------------------------------------------------------------
    // Load Game
    // ------------------------------------------------------------------

    /** Show the load game modal. */
    async _showLoadModal(): Promise<void> {
        const loadModal = document.getElementById("load-modal");
        const loadOverlay = document.getElementById("load-modal-overlay");
        const loadList = document.getElementById("load-list");

        if (!loadModal || !loadList) return;

        loadList.innerHTML = '<p class="empty-state">Loading saves...</p>';
        loadModal.classList.remove("hidden");
        loadOverlay!.classList.remove("hidden");

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
                    (s: any) => `
                <div class="save-card" data-name="${_esc(s.name || s.character_name || "Unknown")}">
                    <div class="save-info">
                        <h3>${_esc(s.character_name || "Unknown")}</h3>
                        <p class="save-meta">
                            Turn ${s.turn_count ?? "?"} · ${s.timestamp ? _formatTimestamp(s.timestamp) : ""}
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
                    const card = (btn as HTMLElement).closest(".save-card") as HTMLElement | null;
                    const saveName = card?.dataset.name;
                    if (saveName) {
                        this._loadGame(saveName);
                    }
                });
            });

            // Bind delete buttons
            loadList.querySelectorAll(".btn-delete-save").forEach((btn) => {
                btn.addEventListener("click", async () => {
                    const card = (btn as HTMLElement).closest(".save-card") as HTMLElement | null;
                    const saveName = card?.dataset.name;
                    if (!saveName || !confirm(`Delete save "${saveName}"?`)) return;
                    try {
                        const resp = await fetch(
                            `/api/delete/${encodeURIComponent(saveName)}`,
                            { method: "DELETE" },
                        );
                        if (!resp.ok) {
                            const errData = await resp.json().catch(() => ({}));
                            console.warn(
                                `Failed to delete save: ${errData.error || resp.statusText}`,
                            );
                        }
                    } catch (_) { /* ignore network errors */ }
                    this._showLoadModal(); // Refresh list
                });
            });
        } catch (e) {
            const error = e as Error;
            loadList.innerHTML = `<p class="empty-state">Error loading saves: ${error.message}</p>`;
        }

        // Close handlers
        const closeModal = () => {
            loadModal.classList.add("hidden");
            loadOverlay!.classList.add("hidden");
        };
        loadOverlay!.onclick = closeModal;
        const closeBtn = loadModal.querySelector(".modal-close") as HTMLElement | null;
        if (closeBtn) closeBtn.onclick = closeModal;
    },

    /** Load a saved game: fetch state + character, restore them, and enter game. */
    async _loadGame(saveName: string): Promise<void> {
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

                // Restore character from embedded _character data (new format)
                // with fallback to separate character field (legacy format)
                const charData = data.state && data.state._character
                    ? data.state._character
                    : data.character || null;
                if (charData) {
                    // Ensure character ID is always a string (UUID), not a number
                    if (charData.id != null) charData.id = String(charData.id);
                    App.state.character = charData;
                }

                // Clear and rebuild narrative
                this.els.narrativeContent!.innerHTML =
                    '<p class="narrative-welcome">Loading saved game...</p>';

                // Hide modal
                loadModal!.classList.add("hidden");
                loadOverlay!.classList.add("hidden");

                // Add a brief load message
                this._addNarrative(`[Game loaded: "${saveName}"]`, {});
                this._addTurnSeparator();
                this._renderSidebar();
                this._enableInput();
            } else {
                alert(`Failed to load save: ${data.error || "Unknown error"}`);
            }
        } catch (e) {
            const error = e as Error;
            alert(`Failed to load save: ${error.message}`);
        }
    },

    // ------------------------------------------------------------------
    // Story Modal
    // ------------------------------------------------------------------

    /** Show the story modal with the adventure log from live state. */
    async _showStoryModal(): Promise<void> {
        const modal = document.getElementById("story-modal");
        const content = document.getElementById("story-content");
        if (!modal || !content) return;

        modal.style.display = "flex";
        content.innerHTML = '';

        // Escape key closes the modal
        this._storyKeyHandler = (e: KeyboardEvent) => {
            if (e.key === "Escape") this._hideStoryModal();
        };
        document.addEventListener("keydown", this._storyKeyHandler);

        const storyLog = this.state.worldState?.story_log;

        if (!storyLog || storyLog.length === 0) {
            content.innerHTML = '<p class="text-muted">The adventure has just begun... no story yet!</p>';
            return;
        }

        // Render each story entry
        content.innerHTML = storyLog.map((entry: string) => {
            const match = entry.match(/^\[Turn (\d+)\]\s*(.*)/s);
            if (match) {
                return `<div class="story-entry">
                    <div class="story-turn-header">Turn ${_esc(match[1])}</div>
                    <div class="story-narrative">${_esc(match[2])}</div>
                </div>`;
            }
            return `<div class="story-entry"><div class="story-narrative">${_esc(entry)}</div></div>`;
        }).join('');
    },

    /** Hide the story modal and clean up. */
    _hideStoryModal() {
        const modal = document.getElementById("story-modal");
        if (modal) modal.style.display = "none";
        const content = document.getElementById("story-content");
        if (content) content.innerHTML = ''; // clear on close
        if (this._storyKeyHandler) {
            document.removeEventListener("keydown", this._storyKeyHandler);
            this._storyKeyHandler = null;
        }
    },

    // ------------------------------------------------------------------
    // Utilities
    // ------------------------------------------------------------------

    /** Scroll the narrative pane to the bottom. */
    _scrollToBottom() {
        if (!this.state.autoScroll) return;
        requestAnimationFrame(() => {
            this.els.narrativePane!.scrollTop =
                this.els.narrativePane!.scrollHeight;
        });
    },

    /** Strip XML/HTML-like tags, markdown bold artifacts, and backtick state-change attributes. */
    _stripXmlTags(str: string): string {
        if (typeof str !== "string") return "";
        let clean = str;
        let previous: string;
        do {
            previous = clean;
            clean = clean.replace(/<[^>]*>?/g, '');
        } while (clean !== previous);
        clean = clean.replace(/\*\*[a-zA-Z_]+\*\*/g, '');
        clean = clean.replace(/`[^`]*?(?:action=|path=|value=)[^`]*`/g, '');
        return clean;
    },
};

document.addEventListener("DOMContentLoaded", () => GameView.init());
