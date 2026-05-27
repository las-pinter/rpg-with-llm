/**
 * LLM-Powered RPG — Character View
 *
 * Character creation with point-buy ability scores, class-based
 * defaults, and server-side persistence.  "Load Existing" tab
 * lists saved characters fetched from the backend API.
 *
 * The server is the single source of truth — no localStorage.
 * Game rules data (point-buy costs, class templates, etc.) is
 * fetched from the backend at startup via /api/config/character-rules.
 */
const CharacterView = {
    // ------------------------------------------------------------------
    // Runtime State
    // ------------------------------------------------------------------

    /** Holds game rules fetched from the API (null until loaded). */
    _rules: null,

    /** Current ability scores (mutable during point-buy). */
    abilities: {},

    selectedClass: "",
    remainingPoints: 0,

    /** Assisted creation state. */
    _assistedState: {
        currentQuestion: 0,
        totalQuestions: 0,
        answers: [],
    },

    /** DOM element references. */
    els: {},

    // ------------------------------------------------------------------
    // Rule Access Helpers
    // ------------------------------------------------------------------

    /** Get the assisted creation questions array (with fallback). */
    _getQuestions() {
        return this._rules?.assisted_creation_questions ?? [];
    },

    /** Get the total number of assisted creation questions. */
    _getQuestionCount() {
        return this._getQuestions().length;
    },

    // ------------------------------------------------------------------
    // Initialisation
    // ------------------------------------------------------------------

    async init() {
        // Fetch game rules from the API before setting up UI
        await this._fetchRules();

        // Set initial values from loaded rules
        this._initDefaults();

        this.els = {
            // Tabs
            tabBar: document.querySelector(".tab-bar"),
            tabCreate: document.getElementById("tab-create"),
            tabLoad: document.getElementById("tab-load"),

            // Create form
            name: document.getElementById("char-name"),
            classSelect: document.getElementById("char-class"),
            appearance: document.getElementById("char-appearance"),
            backstory: document.getElementById("char-backstory"),
            assistedToggle: document.getElementById("assisted-toggle"),
            assistedInfo: document.getElementById("assisted-info"),
            createBtn: document.getElementById("create-character"),
            validationMsg: document.getElementById("char-validation"),

            // Ability scores
            remainingSpan: document.getElementById("remaining-points"),

            // Skills display
            skillsDisplay: document.getElementById("skills-display"),

            // Load tab
            characterList: document.getElementById("character-list"),
            savedGamesList: document.getElementById("saved-games-list"),

            // Assisted creation modal
            assistedModal: document.getElementById("assisted-modal"),
            assistedOverlay: document.getElementById("assisted-modal-overlay"),
            assistedQuestions: document.getElementById("assisted-questions"),
            assistedQuestionNum: document.getElementById("assisted-question-num"),
            assistedProgressFill: document.getElementById("assisted-progress-fill"),
            assistedQuestionText: document.getElementById("assisted-question-text"),
            assistedAnswerInput: document.getElementById("assisted-answer-input"),
            assistedPrevBtn: document.getElementById("assisted-prev-btn"),
            assistedNextBtn: document.getElementById("assisted-next-btn"),
            assistedLoading: document.getElementById("assisted-loading"),
            assistedError: document.getElementById("assisted-error"),
            assistedClose: document.getElementById("assisted-modal-close"),

            // Full-page generating overlay
            charGeneratingOverlay: document.getElementById("char-generating-overlay"),
            charGeneratingText: document.getElementById("char-generating-text"),
        };

        // Tab switching
        this.els.tabBar.addEventListener("click", (e) => {
            const tab = e.target.closest(".tab");
            if (!tab) return;
            this._switchTab(tab.dataset.tab);
        });

        // Class change => update ability defaults + skills
        this.els.classSelect.addEventListener("change", () => {
            this.selectedClass = this.els.classSelect.value;
            this._applyClassDefaults();
            this._updateSkills();
            this._updateUI();
        });

        // Ability score controls (event delegation)
        document
            .getElementById("abilities-grid")
            .addEventListener("click", (e) => {
                const btn = e.target.closest(".abil-btn");
                if (!btn) return;
                const card = btn.closest(".ability-card");
                const abil = card.dataset.abil;
                if (btn.classList.contains("inc")) {
                    this._increase(abil);
                } else {
                    this._decrease(abil);
                }
            });

        // Assisted creation toggle
        this.els.assistedToggle.addEventListener("change", () => {
            const show = this.els.assistedToggle.checked;
            this.els.assistedInfo.classList.toggle("hidden", !show);
        });

        // Assisted creation modal navigation
        this.els.assistedPrevBtn.addEventListener("click",
            () => this._prevAssistedQuestion());
        this.els.assistedNextBtn.addEventListener("click",
            () => this._nextAssistedQuestion());
        this.els.assistedClose.addEventListener("click",
            () => this._hideAssistedModal());
        this.els.assistedOverlay.addEventListener("click",
            () => this._hideAssistedModal());

        // Create character
        this.els.createBtn.addEventListener("click", () => this._createCharacter());

        // Apply initial class defaults
        this._applyClassDefaults();
        this._updateSkills();
        this._updateUI();

        // Load existing characters list on init
        this._renderLoadList();

        // One-time migration from legacy localStorage to server
        this._migrateLocalCharacters();
    },

    /** Initialise defaults from the loaded rules. */
    _initDefaults() {
        const rules = this._rules;

        // Default abilities: first class template or flat 8s
        if (rules?.class_templates) {
            const firstClass = rules.valid_classes?.[0];
            if (firstClass && rules.class_templates[firstClass]) {
                this.abilities = { ...rules.class_templates[firstClass].abilities };
                this.selectedClass = firstClass;
            } else {
                // Fallback — flat 8s
                this.abilities = { STR: 8, DEX: 8, CON: 8, INT: 8, WIS: 8, CHA: 8 };
                this.selectedClass = rules.valid_classes?.[0] || "";
            }
        } else {
            this.abilities = { STR: 8, DEX: 8, CON: 8, INT: 8, WIS: 8, CHA: 8 };
            this.selectedClass = "";
        }

        this.remainingPoints = rules?.point_buy?.max_points ?? 27;

        // Track total questions in assisted state
        this._assistedState.totalQuestions = this._getQuestionCount();
    },

    /** Fetch character creation rules from the backend. */
    async _fetchRules() {
        try {
            const resp = await fetch("/api/config/character-rules");
            const data = await resp.json();
            if (data.ok) {
                this._rules = data.rules;
            }
        } catch (e) {
            console.warn("Failed to fetch character rules, using defaults", e);
        }
    },

    // ------------------------------------------------------------------
    // Tab Switching
    // ------------------------------------------------------------------

    _switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll(".tab").forEach((t) => {
            t.classList.toggle("active", t.dataset.tab === tabName);
        });
        // Update tab content
        this.els.tabCreate.classList.toggle("active", tabName === "create");
        this.els.tabLoad.classList.toggle("active", tabName === "load");

        if (tabName === "load") {
            this._renderLoadList();
        }
    },

    // ------------------------------------------------------------------
    // Point-Buy Logic
    // ------------------------------------------------------------------

    /** Get the point-buy cost for a given ability score. */
    _getCost(score) {
        const costs = this._rules?.point_buy?.costs || {};
        return parseInt(costs[score]) || 0;
    },

    /** Calculate total points spent across all abilities. */
    _totalSpent() {
        let total = 0;
        for (const abil of Object.values(this.abilities)) {
            total += this._getCost(abil);
        }
        return total;
    },

    /** Check if an ability can be increased. */
    _canIncrease(abil) {
        const score = this.abilities[abil];
        const maxScore = this._rules?.point_buy?.max_score ?? 15;
        if (score >= maxScore) return false;
        const nextScore = score + 1;
        const nextCost = this._getCost(nextScore);
        const currentCost = this._getCost(score);
        const pointCost = nextCost - currentCost;
        return this.remainingPoints >= pointCost;
    },

    /** Check if an ability can be decreased. */
    _canDecrease(abil) {
        const minScore = this._rules?.point_buy?.min_score ?? 8;
        return this.abilities[abil] > minScore;
    },

    /** Increase an ability score by 1 (point-buy permitting). */
    _increase(abil) {
        if (!this._canIncrease(abil)) return;
        const oldScore = this.abilities[abil];
        const oldCost = this._getCost(oldScore);
        const newScore = oldScore + 1;
        const newCost = this._getCost(newScore);
        const pointCost = newCost - oldCost;

        this.abilities[abil] = newScore;
        this.remainingPoints -= pointCost;
        this._updateUI();
    },

    /** Decrease an ability score by 1. */
    _decrease(abil) {
        if (!this._canDecrease(abil)) return;
        const oldScore = this.abilities[abil];
        const oldCost = this._getCost(oldScore);
        const newScore = oldScore - 1;
        const newCost = this._getCost(newScore);
        const pointRefund = oldCost - newCost;

        this.abilities[abil] = newScore;
        this.remainingPoints += pointRefund;
        this._updateUI();
    },

    /** Apply class default ability scores to the point-buy. */
    _applyClassDefaults() {
        const templates = this._rules?.class_templates;
        if (!templates) return;
        const template = templates[this.selectedClass];
        if (!template) return;
        this.abilities = { ...template.abilities };
        this.remainingPoints =
            (this._rules?.point_buy?.max_points ?? 27)
            - this._totalPointsForScores(template.abilities);
    },

    /** Calculate total point-buy cost for a set of scores. */
    _totalPointsForScores(scores) {
        let total = 0;
        for (const s of Object.values(scores)) {
            total += this._getCost(s);
        }
        return total;
    },

    /** Update the skills display based on selected class. */
    _updateSkills() {
        const template = this._rules?.class_templates?.[this.selectedClass];
        const skills = template?.skills || [];
        this.els.skillsDisplay.innerHTML = skills
            .map((s) => `<span class="skill-tag">${s}</span>`)
            .join("");
    },

    // ------------------------------------------------------------------
    // UI Update
    // ------------------------------------------------------------------

    /** Refresh all ability score display elements. */
    _updateUI() {
        // Update individual scores
        for (const [abil, score] of Object.entries(this.abilities)) {
            const scoreEl = document.getElementById(`abil-${abil}`);
            const costEl = document.getElementById(`cost-${abil}`);
            if (scoreEl) scoreEl.textContent = score;
            if (costEl) {
                costEl.textContent = `(${this._getCost(score)} pts)`;
            }

            // Enable/disable buttons
            const card = document.querySelector(`[data-abil="${abil}"]`);
            if (card) {
                const incBtn = card.querySelector(".abil-btn.inc");
                const decBtn = card.querySelector(".abil-btn.dec");
                if (incBtn) incBtn.disabled = !this._canIncrease(abil);
                if (decBtn) decBtn.disabled = !this._canDecrease(abil);
            }
        }

        // Update remaining points
        if (this.els.remainingSpan) {
            this.els.remainingSpan.textContent = this.remainingPoints;
        }
    },

    // ------------------------------------------------------------------
    // Character Creation
    // ------------------------------------------------------------------

    /** Validate and create the character via the backend. */
    async _createCharacter() {
        // Assisted creation path
        if (this.els.assistedToggle.checked) {
            this._startAssistedCreation();
            return;
        }

        const name = this.els.name.value.trim();
        if (!name) {
            this._showValidation("Enter a character name.", "error");
            return;
        }

        const cls = this.els.classSelect.value;
        const appearance = this.els.appearance.value.trim();
        const backstory = this.els.backstory.value.trim();

        this._showValidation("Creating character...", "info");

        try {
            const resp = await fetch("/api/character/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: name,
                    character_class: cls,
                    appearance: appearance || undefined,
                    backstory: backstory || undefined,
                }),
            });

            const data = await resp.json();

            if (!resp.ok || !data.ok) {
                throw new Error(
                    data.error || `Server responded with ${resp.status}`,
                );
            }

            const character = data.character;

            // Store in App state
            App.state.character = character;

            // Server is the source of truth — no localStorage persistence

            this._showValidation(
                `Character "${name}" created! Entering the world...`,
                "success",
            );

            // Navigate to game view
            App.navigate("game");
        } catch (err) {
            this._showValidation(
                `Failed to create character: ${err.message}`,
                "error",
            );
        }
    },

    /** Display a validation/success message. */
    _showValidation(msg, type) {
        const el = this.els.validationMsg;
        el.textContent = msg;
        el.className = "validation-msg " + type;
        el.classList.remove("hidden");
    },

    // ------------------------------------------------------------------
    // Assisted Creation Question Flow
    // ------------------------------------------------------------------

    /** Open the assisted creation modal and start the question flow. */
    _startAssistedCreation() {
        const state = this._assistedState;
        state.currentQuestion = 0;
        state.answers = [];
        state.totalQuestions = this._getQuestionCount();

        // Hide error and loading
        this.els.assistedError.classList.add("hidden");
        this.els.assistedError.textContent = "";
        this.els.assistedLoading.classList.add("hidden");

        // Reset visibility of question elements
        this._assistedResetVisibility();

        // Show modal
        this.els.assistedOverlay.classList.remove("hidden");
        this.els.assistedModal.classList.remove("hidden");

        // Show first question
        this._showAssistedQuestion(0);
    },

    /** Reset all visibility toggles inside the assisted modal. */
    _assistedResetVisibility() {
        const qs = this.els.assistedQuestions;
        const visibleIds = [
            "#assisted-progress",
            "#assisted-question-text",
            "#assisted-answer-input",
        ];
        visibleIds.forEach((id) => {
            const el = qs.querySelector(id);
            if (el) el.classList.remove("hidden");
        });
        const nav = qs.querySelector(".assisted-nav");
        if (nav) nav.classList.remove("hidden");
    },

    /** Display the question at the given index. */
    _showAssistedQuestion(index) {
        const state = this._assistedState;
        const questions = this._getQuestions();
        const totalQuestions = this._getQuestionCount();
        state.currentQuestion = index;

        // Update question text
        this.els.assistedQuestionText.textContent = questions[index];

        // Load existing answer if typed before
        this.els.assistedAnswerInput.value = state.answers[index] || "";

        // Update progress
        const qNum = index + 1;
        this.els.assistedQuestionNum.textContent =
            `Question ${qNum} of ${totalQuestions}`;
        const pct = ((qNum) / totalQuestions) * 100;
        this.els.assistedProgressFill.style.width = `${pct}%`;

        // Update navigation buttons
        this.els.assistedPrevBtn.disabled = index === 0;

        if (index === totalQuestions - 1) {
            this.els.assistedNextBtn.textContent = "Submit";
        } else {
            this.els.assistedNextBtn.textContent = "Next";
        }

        // Focus the textarea
        this.els.assistedAnswerInput.focus();
    },

    /** Save current answer and advance to the next question or submit. */
    _nextAssistedQuestion() {
        const state = this._assistedState;
        const index = state.currentQuestion;
        state.answers[index] = this.els.assistedAnswerInput.value.trim();

        if (index >= this._getQuestionCount() - 1) {
            this._submitAssistedAnswers();
        } else {
            this._showAssistedQuestion(index + 1);
        }
    },

    /** Save current answer and go back to the previous question. */
    _prevAssistedQuestion() {
        const state = this._assistedState;
        const index = state.currentQuestion;
        state.answers[index] = this.els.assistedAnswerInput.value.trim();
        this._showAssistedQuestion(index - 1);
    },

    /** Submit answers to the backend and handle the response. */
    async _submitAssistedAnswers() {
        const state = this._assistedState;

        // Save the last answer
        state.answers[state.currentQuestion] =
            this.els.assistedAnswerInput.value.trim();

        // Show loading, hide question UI
        const qs = this.els.assistedQuestions;
        const hideIds = [
            "#assisted-progress",
            "#assisted-question-text",
            "#assisted-answer-input",
        ];
        hideIds.forEach((id) => {
            const el = qs.querySelector(id);
            if (el) el.classList.add("hidden");
        });
        const nav = qs.querySelector(".assisted-nav");
        if (nav) nav.classList.add("hidden");
        this.els.assistedError.classList.add("hidden");
        this.els.assistedLoading.classList.remove("hidden");

        // Show page-level overlay for visibility even if modal is dismissed
        this.els.charGeneratingOverlay.classList.remove("hidden");

        try {
            // Build answers object with numeric keys
            const answers = {};
            for (let i = 0; i < state.answers.length; i++) {
                answers[i] = state.answers[i] || "";
            }

            const resp = await fetch("/api/character/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    answers: answers,
                    abilities: CharacterView.abilities,
                    provider: App.state.provider,
                }),
            });

            const data = await resp.json();

            if (!resp.ok || !data.ok) {
                throw new Error(
                    data.error || `Server responded with ${resp.status}`,
                );
            }

            const character = data.character;

            // Store in App state
            App.state.character = character;

            // Server is the source of truth — no localStorage persistence

            // Hide page-level overlay
            this.els.charGeneratingOverlay.classList.add("hidden");

            // Hide modal
            this._hideAssistedModal();

            // Navigate to game
            App.navigate("game");
        } catch (err) {
            // Hide page-level overlay and modal loading
            this.els.charGeneratingOverlay.classList.add("hidden");
            this.els.assistedLoading.classList.add("hidden");

            // Restore question UI
            this._assistedResetVisibility();

            this.els.assistedError.textContent =
                `Failed to generate character: ${err.message}. ` +
                "Check your provider connection and try again.";
            this.els.assistedError.classList.remove("hidden");
        }
    },

    /** Hide the assisted creation modal and reset visibility. */
    _hideAssistedModal() {
        this.els.assistedOverlay.classList.add("hidden");
        this.els.assistedModal.classList.add("hidden");
        this.els.assistedLoading.classList.add("hidden");
        this.els.assistedError.classList.add("hidden");
        this.els.charGeneratingOverlay.classList.add("hidden");
        this._assistedResetVisibility();
    },

    // ------------------------------------------------------------------
    // Load Tab — Server-Backed Character Management
    // ------------------------------------------------------------------

    /** Delete a character on the server by UUID. */
    async _deleteCharacter(id) {
        try {
            const resp = await fetch(
                `/api/character/id/${encodeURIComponent(id)}`,
                { method: "DELETE" },
            );
            if (!resp.ok) {
                const data = await resp.json();
                throw new Error(
                    data.error || `Server responded with ${resp.status}`,
                );
            }
        } catch (err) {
            this._showLoadError(
                `Failed to delete character: ${err.message}`,
            );
            return;
        }

        this._renderLoadList();
    },

    /** Render the list of characters from the server in the Load tab. */
    async _renderLoadList() {
        const container = this.els.characterList;

        // Show loading state
        container.innerHTML =
            '<p class="empty-state">Loading characters...</p>';

        try {
            const resp = await fetch("/api/characters");
            const data = await resp.json();

            if (!resp.ok || !data.ok || !Array.isArray(data.characters)) {
                throw new Error(
                    data.error || "Invalid response from server",
                );
            }

            const characters = data.characters;

            if (characters.length === 0) {
                container.innerHTML =
                    '<p class="empty-state">No saved characters yet. Create one!</p>';
            } else {
                container.innerHTML = characters
                    .map(
                        (c) => `
                    <div class="char-card">
                        <div class="char-info">
                            <h3>${_esc(c.name)}</h3>
                            <p class="char-meta">
                                ${_esc(c.class)} · Level ${c.level}
                                ${c.timestamp ? " · " + _formatTimestamp(c.timestamp) : ""}
                            </p>
                        </div>
                        <div class="char-actions">
                            <button class="btn btn-sm btn-load" data-id="${_esc(c.id)}" data-name="${_esc(c.name)}">Load</button>
                            <button class="btn btn-sm btn-danger btn-delete" data-id="${_esc(c.id)}" data-name="${_esc(c.name)}">Del</button>
                        </div>
                    </div>
                `,
                    )
                    .join("");

                // Bind events for load/delete buttons
                container.querySelectorAll(".btn-load").forEach((btn) => {
                    btn.addEventListener("click", () => {
                        this._loadCharacter(btn.dataset.id);
                    });
                });
                container.querySelectorAll(".btn-delete").forEach((btn) => {
                    btn.addEventListener("click", () => {
                        this._deleteCharacter(btn.dataset.id);
                    });
                });
            }
        } catch (err) {
            container.innerHTML =
                '<p class="empty-state">Could not load characters from server.</p>';
        }

        // ---- Render saved games section ----
        this._renderSavedGames();
    },

    /** Fetch and render the list of saved games in the Load tab. */
    async _renderSavedGames() {
        const savesContainer = this.els.savedGamesList;
        if (!savesContainer) return;

        savesContainer.innerHTML =
            '<p class="empty-state">Loading saved games...</p>';

        try {
            const resp = await fetch("/api/saves");
            const data = await resp.json();
            const saves = data.saves || [];

            if (saves.length === 0) {
                savesContainer.innerHTML =
                    '<p class="empty-state">No saved games yet.</p>';
                return;
            }

            savesContainer.innerHTML = saves
                .map(
                    (s) => {
                        const saveName = s.name || s.character_name || "Unknown";
                        const charName = s.character_name || "Unknown";
                        const turnCount = s.turn_count ?? "?";
                        const ts = s.timestamp
                            ? _formatTimestamp(s.timestamp)
                            : "";
                        return `
                    <div class="save-card" data-name="${_esc(saveName)}">
                        <div class="save-info">
                            <h3>${_esc(charName)}</h3>
                            <p class="save-meta">
                                Turn ${turnCount} · ${ts}
                            </p>
                        </div>
                        <div class="save-actions">
                            <button class="btn btn-sm btn-continue-save">
                                Continue Adventure
                            </button>
                        </div>
                    </div>
                `;
                    },
                )
                .join("");

            savesContainer.querySelectorAll(".btn-continue-save").forEach(
                (btn) => {
                    btn.addEventListener("click", () => {
                        const card = btn.closest(".save-card");
                        const saveName = card.dataset.name;
                        App.state.loadSaveName = saveName;
                        App.navigate("game");
                    });
                },
            );
        } catch (e) {
            savesContainer.innerHTML =
                '<p class="empty-state">Could not load saved games.</p>';
        }
    },

    /** Load a character by UUID from the server. */
    async _loadCharacter(id) {
        try {
            const resp = await fetch(
                `/api/character/id/${encodeURIComponent(id)}`,
            );
            const data = await resp.json();

            if (!resp.ok || !data.ok || !data.character) {
                throw new Error(
                    data.error || "Character not found",
                );
            }

            App.state.character = data.character;
            App.navigate("game");
        } catch (err) {
            this._showLoadError(
                `Failed to load character: ${err.message}`,
            );
        }
    },

    // ------------------------------------------------------------------
    // Migration from Legacy localStorage
    // ------------------------------------------------------------------

    /**
     * One-time migration: POST any characters still in localStorage
     * to the server, then remove the localStorage key.
     */
    async _migrateLocalCharacters() {
        let raw;
        try {
            raw = localStorage.getItem("rpg_characters");
        } catch (_e) {
            return; // localStorage unavailable
        }
        if (!raw) return;

        let chars;
        try {
            chars = JSON.parse(raw);
        } catch (_e) {
            return; // corrupt JSON, skip
        }
        if (!Array.isArray(chars) || chars.length === 0) return;

        let migrated = 0;
        for (const char of chars) {
            try {
                // Build payload with ALL available fields from localStorage
                const payload = {
                    name: char.name,
                    character_class: char.character_class,
                };

                // Narrative / identity fields
                for (const field of ["appearance", "backstory", "personality",
                                     "ideals", "bonds", "flaws", "plot_hooks"]) {
                    if (char[field]) payload[field] = char[field];
                }

                // Numeric fields
                for (const field of ["level", "xp", "hp", "max_hp", "ac", "gold"]) {
                    if (char[field] != null) payload[field] = char[field];
                }

                // Ability scores — send full dict if available, else individual fields
                if (char.abilities && typeof char.abilities === "object") {
                    payload.abilities = char.abilities;
                } else {
                    for (const key of ["strength", "dexterity", "constitution",
                                       "intelligence", "wisdom", "charisma"]) {
                        if (char[key] != null) payload[key] = char[key];
                    }
                }

                // Array fields
                if (Array.isArray(char.skills)) payload.skills = char.skills;
                if (Array.isArray(char.inventory)) payload.inventory = char.inventory;

                const resp = await fetch("/api/character/create", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                if (resp.ok) migrated++;
            } catch (_e) {
                // Skip individual failures — character data remains in
                // localStorage so nothing is lost.
            }
        }

        if (migrated > 0) {
            try {
                localStorage.removeItem("rpg_characters");
            } catch (_e) {
                // Ignore — data already on server
            }
        }

        if (migrated > 0) {
            this._showMigrationBanner(migrated);
        }
    },

    /** Show a dismissible banner confirming migration. */
    _showMigrationBanner(count) {
        const existing = document.querySelector(".migration-banner");
        if (existing) existing.remove();

        const banner = document.createElement("div");
        banner.className = "migration-banner";
        banner.innerHTML = `
            <span class="migration-banner-text">
                Your local character${count !== 1 ? "s have" : " has"} been saved to the server!
            </span>
            <button class="migration-banner-close" aria-label="Dismiss">&times;</button>
        `;
        banner.querySelector(".migration-banner-close")
            .addEventListener("click", () => banner.remove());

        this.els.tabLoad.prepend(banner);
    },

    /** Show an inline error banner inside the Load tab (auto-dismiss). */
    _showLoadError(message) {
        const el = document.createElement("p");
        el.className = "validation-msg error";
        el.textContent = message;
        el.style.marginBottom = "0.5rem";
        this.els.tabLoad.prepend(el);
        setTimeout(() => el.remove(), 5000);
    },

    // ------------------------------------------------------------------
    // Utilities
    // ------------------------------------------------------------------

};

document.addEventListener("DOMContentLoaded", () => CharacterView.init());
