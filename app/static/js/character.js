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

    /** Save a character to localStorage. */
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
    },

    /** Delete a character from localStorage by name. */
    _deleteCharacter(name) {
        let chars = this._getSavedCharacters();
        chars = chars.filter((c) => c.name !== name);
        try {
            localStorage.setItem(this._storageKey(), JSON.stringify(chars));
        } catch (e) {
            // ignore
        }
        this._renderLoadList();
    },

    // ------------------------------------------------------------------
    // Load Tab Rendering
    // ------------------------------------------------------------------

    /** Render the list of saved characters in the Load tab. */
    _renderLoadList() {
        const chars = this._getSavedCharacters();
        const container = this.els.characterList;

        if (chars.length === 0) {
            container.innerHTML =
                '<p class="empty-state">No saved characters yet. Create one!</p>';
            return;
        }

        container.innerHTML = chars
            .map(
                (c) => `
            <div class="char-card">
                <div class="char-info">
                    <h3>${this._esc(c.name)}</h3>
                    <p class="char-meta">
                        ${this._esc(c.character_class)} · Level ${c.level}
                        ${c.created ? " · " + new Date(c.created).toLocaleDateString() : ""}
                    </p>
                </div>
                <div class="char-actions">
                    <button class="btn btn-sm btn-load" data-name="${this._esc(c.name)}">Load</button>
                    <button class="btn btn-sm btn-danger btn-delete" data-name="${this._esc(c.name)}">Del</button>
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
    },

    /** Load a character from localStorage into App state and navigate. */
    _loadCharacter(name) {
        const chars = this._getSavedCharacters();
        const char = chars.find((c) => c.name === name);
        if (!char) return;

        App.state.character = char;
        App.navigate("game");
    },

    // ------------------------------------------------------------------
    // Utilities
    // ------------------------------------------------------------------

    /** Escape HTML special chars (simple XSS guard). */
    _esc(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    },
};

document.addEventListener("DOMContentLoaded", () => CharacterView.init());
