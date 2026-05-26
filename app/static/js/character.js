/**
 * LLM-Powered RPG — Character View
 *
 * Character creation with point-buy ability scores, class-based
 * defaults, and localStorage persistence.  "Load Existing" tab
 * lists saved characters for quick loading or deletion.
 */
const CharacterView = {
    // ------------------------------------------------------------------
    // D&D 5e Point-Buy Constants
    // ------------------------------------------------------------------
    POINT_BUY_COST: { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 },
    MAX_POINTS: 27,
    MIN_SCORE: 8,
    MAX_SCORE: 15,

    /** Default ability arrays for each class (standard array assigned). */
    CLASS_DEFAULTS: {
        Fighter: { STR: 15, DEX: 13, CON: 14, WIS: 12, INT: 10, CHA: 8 },
        Rogue: { STR: 8, DEX: 15, CON: 13, INT: 14, WIS: 12, CHA: 10 },
        Mage: { STR: 8, DEX: 13, CON: 14, INT: 15, WIS: 12, CHA: 10 },
        Cleric: { STR: 13, DEX: 8, CON: 14, INT: 10, WIS: 15, CHA: 12 },
    },

    CLASS_SKILLS: {
        Fighter: ["Athletics", "Perception"],
        Rogue: ["Stealth", "Sleight of Hand", "Perception"],
        Mage: ["Arcana", "Investigation"],
        Cleric: ["Religion", "Medicine"],
    },

    CLASS_HP: {
        Fighter: 12,
        Rogue: 9,
        Mage: 8,
        Cleric: 10,
    },

    CLASS_AC: {
        Fighter: 18,
        Rogue: 14,
        Mage: 12,
        Cleric: 16,
    },

    /** Current ability scores (mutable during point-buy). */
    abilities: { STR: 8, DEX: 8, CON: 8, INT: 8, WIS: 8, CHA: 8 },

    selectedClass: "Fighter",
    remainingPoints: 27,

    /** Assisted creation state and questions. */
    _assistedState: {
        currentQuestion: 0,
        totalQuestions: 7,
        answers: [],
        questions: [
            "Where were you born and raised? What did your family do — and what did " +
                "you do before you picked up a sword (or a spellbook, or a set of lockpicks)?",
            "Describe a single moment that changed everything — a betrayal, a loss, a " +
                "discovery, or a choice you couldn't take back. What happened, and why " +
                "did it leave you no choice but to adventure?",
            "What is your deepest flaw — the thing about yourself you're trying to hide " +
                "or outrun? And what strength do you lean on when you fall?",
            "What are you looking for out there — really? Treasure? A name for yourself? " +
                "Revenge? Something you lost? And what would make you turn back?",
            "Describe someone you left behind — a person you love, fear, owe, or hate. " +
                "What would they say about you if you never came back?",
            "What do you look like? What marks, scars, or gear does a stranger notice " +
                "first — and what story do those marks tell?",
            "What's one thing about your past that, if it ever caught up to you, would " +
                "ruin everything? A debt? A crime? A promise you broke? A secret you're " +
                "keeping?",
        ],
    },

    /** DOM element references. */
    els: {},

    // ------------------------------------------------------------------
    // Initialisation
    // ------------------------------------------------------------------

    init() {
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

        // Class change → update ability defaults + skills
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

        // Load existing characters list on tab switch
        this._renderLoadList();
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
        return this.POINT_BUY_COST[score] || 0;
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
        if (score >= this.MAX_SCORE) return false;
        const nextScore = score + 1;
        const nextCost = this._getCost(nextScore);
        const currentCost = this._getCost(score);
        const pointCost = nextCost - currentCost;
        return this.remainingPoints >= pointCost;
    },

    /** Check if an ability can be decreased. */
    _canDecrease(abil) {
        return this.abilities[abil] > this.MIN_SCORE;
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
        const defaults = this.CLASS_DEFAULTS[this.selectedClass];
        if (!defaults) return;
        this.abilities = { ...defaults };
        this.remainingPoints =
            this.MAX_POINTS - this._totalPointsForScores(defaults);
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
        const skills = this.CLASS_SKILLS[this.selectedClass] || [];
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

    /** Validate and create the character, storing in localStorage. */
    _createCharacter() {
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
        const conScore = this.abilities.CON || 10;
        const conMod = Math.floor((conScore - 10) / 2);
        const baseHp = this.CLASS_HP[cls] || 10;
        const maxHp = baseHp + conMod;
        const ac = this.CLASS_AC[cls] || 10;

        const character = {
            name: name,
            character_class: cls,
            level: 1,
            xp: 0,
            abilities: { ...this.abilities },
            skills: [...(this.CLASS_SKILLS[cls] || [])],
            hp: maxHp,
            max_hp: maxHp,
            ac: ac,
            inventory: [],
            appearance: appearance,
            personality: "",
            backstory: backstory,
            hooks: [],
            created: new Date().toISOString(),
        };

        // Store in App state
        App.state.character = character;

        // Persist to localStorage
        this._saveCharacter(character);

        this._showValidation(
            `Character "${name}" created! Entering the world...`,
            "success",
        );

        // Navigate to game view after a brief pause
        setTimeout(() => App.navigate("game"), 800);
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
        state.currentQuestion = index;

        // Update question text
        this.els.assistedQuestionText.textContent = state.questions[index];

        // Load existing answer if typed before
        this.els.assistedAnswerInput.value = state.answers[index] || "";

        // Update progress
        const qNum = index + 1;
        this.els.assistedQuestionNum.textContent =
            `Question ${qNum} of ${state.totalQuestions}`;
        const pct = ((qNum) / state.totalQuestions) * 100;
        this.els.assistedProgressFill.style.width = `${pct}%`;

        // Update navigation buttons
        this.els.assistedPrevBtn.disabled = index === 0;

        if (index === state.totalQuestions - 1) {
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

        if (index >= state.totalQuestions - 1) {
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

            // Persist to localStorage
            this._saveCharacter(character);

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
    // localStorage Persistence
    // ------------------------------------------------------------------

    _storageKey() {
        return "rpg_characters";
    },

    /** Get all saved characters from localStorage. */
    _getSavedCharacters() {
        try {
            const raw = localStorage.getItem(this._storageKey());
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    },

    /** Save a character to localStorage and fire-and-forget to server. */
    _saveCharacter(char) {
        const chars = this._getSavedCharacters();
        // Replace if name already exists
        const idx = chars.findIndex((c) => c.name === char.name);
        if (idx >= 0) {
            chars[idx] = char;
        } else {
            chars.push(char);
        }
        try {
            localStorage.setItem(this._storageKey(), JSON.stringify(chars));
        } catch (e) {
            // localStorage full — silently fail
        }

        // Fire-and-forget server save — don't block navigation
        try {
            fetch("/api/character/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ character: char }),
            }).catch(() => {});  // ignore network errors
        } catch (_e) {
            // Server unreachable — no harm, localStorage has it
        }
    },

    /** Delete a character from localStorage and server by name. */
    _deleteCharacter(name) {
        // Delete from localStorage
        let chars = this._getSavedCharacters();
        chars = chars.filter((c) => c.name !== name);
        try {
            localStorage.setItem(this._storageKey(), JSON.stringify(chars));
        } catch (e) {
            // ignore
        }

        // Fire-and-forget DELETE to server — don't block UI
        try {
            fetch(`/api/character/delete/${encodeURIComponent(name)}`, {
                method: "DELETE",
            }).catch(() => {});  // ignore network errors
        } catch (_e) {
            // Server unreachable
        }

        this._renderLoadList();
    },

    // ------------------------------------------------------------------
    // Load Tab Rendering
    // ------------------------------------------------------------------

    /** Render the list of saved characters in the Load tab. */
    async _renderLoadList() {
        const container = this.els.characterList;

        // Show loading state while fetching from server
        container.innerHTML =
            '<p class="empty-state">Loading characters...</p>';

        // Get local characters immediately
        const localChars = this._getSavedCharacters();

        // Fetch server characters (non-blocking — failures use local only)
        let serverChars = [];
        try {
            const resp = await fetch("/api/characters");
            if (resp.ok) {
                const data = await resp.json();
                if (data.ok && Array.isArray(data.characters)) {
                    serverChars = data.characters;
                }
            }
        } catch (_e) {
            // Server unreachable — use local only, no harm done
        }

        // Merge: deduplicate by name, prefer localStorage (most recent data)
        const merged = this._mergeCharacterLists(localChars, serverChars);

        if (merged.length === 0) {
            container.innerHTML =
                '<p class="empty-state">No saved characters yet. Create one!</p>';
        } else {
            container.innerHTML = merged
                .map(
                    (c) => `
                <div class="char-card">
                    <div class="char-info">
                        <h3>${_esc(c.name)}</h3>
                        <p class="char-meta">
                            ${_esc(c.character_class)} · Level ${c.level}
                            ${c.created ? " · " + new Date(c.created).toLocaleDateString() : ""}
                        </p>
                    </div>
                    <div class="char-actions">
                        <button class="btn btn-sm btn-load" data-name="${_esc(c.name)}">Load</button>
                        <button class="btn btn-sm btn-danger btn-delete" data-name="${_esc(c.name)}">Del</button>
                    </div>
                </div>
            `,
                )
                .join("");

            // Bind events for load/delete buttons
            container.querySelectorAll(".btn-load").forEach((btn) => {
                btn.addEventListener("click", () => {
                    this._loadCharacter(btn.dataset.name);
                });
            });
            container.querySelectorAll(".btn-delete").forEach((btn) => {
                btn.addEventListener("click", () => {
                    this._deleteCharacter(btn.dataset.name);
                });
            });
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

    /**
     * Merge localStorage and server character lists.
     *
     * Server metadata uses `class` instead of `character_class` and
     * `timestamp` instead of `created`.  This normalises both to a
     * common shape and deduplicates by name, preferring the localStorage
     * version since it has the most recent data.
     */
    _mergeCharacterLists(localChars, serverChars) {
        const map = new Map();

        // Add server chars first (will be overridden by local for same name)
        for (const c of serverChars || []) {
            map.set(c.name, {
                name: c.name,
                character_class: c.class,
                level: c.level,
                created: c.timestamp,
            });
        }

        // Add local chars (overrides server for matching names)
        for (const c of localChars || []) {
            map.set(c.name, c);
        }

        return Array.from(map.values());
    },

    /** Load a character from localStorage or server into App state and navigate. */
    async _loadCharacter(name) {
        // Try localStorage first (it's the primary persistence)
        const chars = this._getSavedCharacters();
        const localChar = chars.find((c) => c.name === name);
        if (localChar) {
            App.state.character = localChar;
            App.navigate("game");
            return;
        }

        // Not in localStorage — try loading from server
        try {
            const resp = await fetch(
                `/api/character/load/${encodeURIComponent(name)}`,
            );
            if (resp.ok) {
                const data = await resp.json();
                if (data.ok && data.character) {
                    App.state.character = data.character;
                    App.navigate("game");
                    return;
                }
            }
        } catch (_e) {
            // Server unreachable
        }

        console.warn(`Character "${name}" not found in localStorage or on server.`);
    },

    // ------------------------------------------------------------------
    // Utilities
    // ------------------------------------------------------------------

};

document.addEventListener("DOMContentLoaded", () => CharacterView.init());
