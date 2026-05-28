/**
 * LLM-Powered RPG — Character View
 *
 * "The Campfire" story-first character creation flow with sub-tabs
 * for Campfire (narrative) and Manual (point-buy) creation, plus a
 * review screen that both paths converge on before starting the game.
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

    /** DOM element references. */
    els: {},

    /** 'campfire' | 'manual' | 'review' */
    _mode: "campfire",

    /** Array of 7 answer strings from the story questions. */
    _storyAnswers: [],

    /** Index of the currently visible story question. */
    _currentQuestion: 0,

    /** Character data returned from the generate / create API. */
    _generatedCharacter: null,

    /** Whether the review sheet is in edit mode. */
    _isEditing: false,

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

            // Sub-tabs
            campfireTab: document.getElementById("campfire-tab"),
            manualTab: document.getElementById("manual-tab"),
            campfireContent: document.getElementById("campfire-content"),
            manualContent: document.getElementById("manual-content"),

            // Create form — campfire
            charName: document.getElementById("char-name"),
            charClass: document.getElementById("char-class"),

            // Create form — manual
            nameManual: document.getElementById("char-name-manual"),
            classManual: document.getElementById("char-class-manual"),
            appearance: document.getElementById("char-appearance"),
            backstory: document.getElementById("char-backstory"),
            manualCreateBtn: document.getElementById("manual-create-btn"),
            validationMsg: document.getElementById("char-validation"),

            // Ability scores
            remainingSpan: document.getElementById("remaining-points"),
            campRemainingSpan: document.getElementById("camp-remaining-points"),

            // Skills display
            skillsDisplay: document.getElementById("skills-display"),

            // Story / Campfire section
            storyQuestions: document.getElementById("story-questions"),
            storyProgressFill: document.getElementById("story-progress-fill"),
            storyChapterNum: document.getElementById("story-chapter-num"),
            storyChapterTotal: document.getElementById("story-chapter-total"),
            storyStepDots: document.getElementById("story-step-dots"),
            storyPrevBtn: document.getElementById("story-prev-btn"),
            storyNextBtn: document.getElementById("story-next-btn"),
            storyGenerateBtn: document.getElementById("story-generate-btn"),

            // Review section
            reviewSection: document.getElementById("review-section"),
            reviewCharacterSheet: document.getElementById(
                "review-character-sheet",
            ),
            reviewLoading: document.getElementById("review-loading"),
            reviewEditBtn: document.getElementById("review-edit-btn"),
            reviewRegenerateBtn: document.getElementById(
                "review-regenerate-btn",
            ),
            reviewStartBtn: document.getElementById("review-start-btn"),

            // Load tab
            characterList: document.getElementById("character-list"),
            savedGamesList: document.getElementById("saved-games-list"),
        };

        // Populate class dropdowns
        this._populateClassDropdowns();

        // Tab switching (Create ↔ Load)
        this.els.tabBar.addEventListener("click", (e) => {
            const tab = e.target.closest(".tab");
            if (!tab) return;
            this._switchTab(tab.dataset.tab);
        });

        // Sub-tab switching (Campfire ↔ Manual)
        this.els.campfireTab.addEventListener("click", () =>
            this._switchCreationMode("campfire"),
        );
        this.els.manualTab.addEventListener("click", () =>
            this._switchCreationMode("manual"),
        );

        // Class change => update ability defaults + skills
        this.els.charClass.addEventListener("change", () => {
            this.selectedClass = this.els.charClass.value;
            this._applyClassDefaults();
            this._updateSkills();
            this._updateUI();
        });

        // Manual class change => same treatment
        this.els.classManual.addEventListener("change", () => {
            this.selectedClass = this.els.classManual.value;
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

        // Campfire ability score controls (event delegation)
        const campGrid = document.getElementById("camp-abilities-grid");
        if (campGrid) {
            campGrid.addEventListener("click", (e) => {
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
        }

        // Story navigation
        this.els.storyPrevBtn.addEventListener("click", () =>
            this._prevStoryQuestion(),
        );
        this.els.storyNextBtn.addEventListener("click", () =>
            this._nextStoryQuestion(),
        );
        this.els.storyGenerateBtn.addEventListener("click", () =>
            this._submitStoryAnswers(),
        );

        // Step dots — click to jump
        this.els.storyStepDots.addEventListener("click", (e) => {
            const dot = e.target.closest(".story-step-dot");
            if (dot) {
                const idx = parseInt(dot.dataset.index, 10);
                this._saveCurrentAnswer();
                this._showStoryQuestion(idx);
            }
        });

        // Review buttons
        this.els.reviewEditBtn.addEventListener("click", () =>
            this._toggleEditMode(),
        );
        this.els.reviewRegenerateBtn.addEventListener("click", () =>
            this._regenerateCharacter(),
        );
        this.els.reviewStartBtn.addEventListener("click", () =>
            this._startAdventure(),
        );

        // Manual create character
        this.els.manualCreateBtn.addEventListener("click", () =>
            this._createCharacter(),
        );

        // Apply initial class defaults
        this._applyClassDefaults();
        this._updateSkills();
        this._updateUI();

        // Load existing characters list on init
        this._renderLoadList();

        // Build story questions and start in campfire mode
        this._buildStoryQuestions();
        this._showStoryQuestion(0);
        this._switchCreationMode("campfire");
    },

    /** Populate both class dropdowns from the loaded rules. */
    _populateClassDropdowns() {
        const classes = this._rules?.valid_classes || [];
        const options = classes
            .map((c) => `<option value="${_esc(c)}">${_esc(c)}</option>`)
            .join("");

        const campfireSelect = this.els.charClass;
        const manualSelect = this.els.classManual;

        if (campfireSelect) campfireSelect.innerHTML = options;
        if (manualSelect) manualSelect.innerHTML = options;
    },

    /** Initialise defaults from the loaded rules. */
    _initDefaults() {
        const rules = this._rules;

        // Default to flat 8s, then override with class template if possible
        this.abilities = { STR: 8, DEX: 8, CON: 8, INT: 8, WIS: 8, CHA: 8 };

        if (rules?.class_templates) {
            const firstClass = rules.valid_classes?.[0];
            if (firstClass && rules.class_templates[firstClass]) {
                this.abilities = { ...this.abilities, ...rules.class_templates[firstClass].abilities };
                this.selectedClass = firstClass;
            } else {
                this.selectedClass = rules.valid_classes?.[0] || "";
            }
        } else {
            this.selectedClass = "";
        }

        this.remainingPoints = rules?.point_buy?.max_points ?? 27;
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
    // Sub-Tab / Creation Mode Switching
    // ------------------------------------------------------------------

    /**
     * Toggle between 'campfire' and 'manual' creation modes.
     * The 'review' mode is set separately by _showReviewScreen.
     */
    _switchCreationMode(mode) {
        this._mode = mode;

        // Update sub-tab button active states
        const campfireTab = this.els.campfireTab;
        const manualTab = this.els.manualTab;
        if (campfireTab) {
            campfireTab.classList.toggle("active", mode === "campfire");
        }
        if (manualTab) {
            manualTab.classList.toggle("active", mode === "manual");
        }

        // Show/hide sub-tab content
        if (this.els.campfireContent) {
            this.els.campfireContent.classList.toggle(
                "active",
                mode === "campfire",
            );
        }
        if (this.els.manualContent) {
            this.els.manualContent.classList.toggle(
                "active",
                mode === "manual",
            );
        }

        // When switching to campfire mode, ensure the review section
        // is hidden and the story section is visible
        if (mode === "campfire") {
            const storySection = document.getElementById("story-section");
            if (storySection) storySection.style.display = "";
            if (this.els.reviewSection) {
                this.els.reviewSection.style.display = "none";
            }
        }
    },

    // ------------------------------------------------------------------
    // Story Question Flow ("The Campfire")
    // ------------------------------------------------------------------

    /** Build story question DOM from rules or fallback questions. */
    _buildStoryQuestions() {
        const questions =
            this._rules?.assisted_creation_questions || [
                "Where were you born, and what was your childhood like?",
                "What drove you to become an adventurer?",
                "Describe a pivotal moment that shaped who you are.",
                "What is your greatest fear, and why?",
                "Who or what do you value above all else?",
                "Tell me about a mentor or rival who influenced you.",
                "What is your ultimate goal or ambition?",
            ];

        const container = this.els.storyQuestions;
        if (!container) return;
        container.innerHTML = "";

        questions.forEach((q, i) => {
            const div = document.createElement("div");
            div.className = "journal-chapter";
            div.dataset.index = i;
            div.innerHTML =
                `
                <div class="journal-chapter-number">Chapter ${i + 1}</div>
                <div class="journal-chapter-question">${_esc(q)}</div>
                <textarea class="journal-chapter-textarea"
                    placeholder="Type your answer here..."
                    data-index="${i}"></textarea>
            `.trim();
            container.appendChild(div);
        });

        // Update chapter total
        if (this.els.storyChapterTotal) {
            this.els.storyChapterTotal.textContent = questions.length;
        }

        // Build step dots
        this._buildStepDots(questions.length);
    },

    /** Create clickable step dots for the story progress bar. */
    _buildStepDots(count) {
        const dotsContainer = this.els.storyStepDots;
        if (!dotsContainer) return;
        dotsContainer.innerHTML = "";
        for (let i = 0; i < count; i++) {
            const dot = document.createElement("span");
            dot.className = "story-step-dot";
            dot.dataset.index = i;
            dotsContainer.appendChild(dot);
        }
    },

    /** Show the story question at the given index. */
    _showStoryQuestion(index) {
        const chapters = this.els.storyQuestions?.querySelectorAll(
            ".journal-chapter",
        );
        if (!chapters || chapters.length === 0) return;

        const total = chapters.length;

        // Hide all, show target
        chapters.forEach((ch, i) => {
            ch.classList.toggle("active", i === index);
        });

        this._currentQuestion = index;

        // Update progress bar
        if (this.els.storyProgressFill) {
            const pct = ((index + 1) / total) * 100;
            this.els.storyProgressFill.style.width = pct + "%";
        }

        // Update chapter number text
        if (this.els.storyChapterNum) {
            this.els.storyChapterNum.textContent = index + 1;
        }

        // Update step dots
        const dots = this.els.storyStepDots?.querySelectorAll(
            ".story-step-dot",
        );
        if (dots) {
            dots.forEach((dot, i) => {
                dot.classList.toggle("active", i === index);
                dot.classList.toggle("done", i < index);
            });
        }

        // Nav buttons
        if (this.els.storyPrevBtn) {
            this.els.storyPrevBtn.disabled = index === 0;
        }

        const isLast = index === total - 1;
        if (this.els.storyNextBtn) {
            this.els.storyNextBtn.style.display = isLast ? "none" : "";
        }
        if (this.els.storyGenerateBtn) {
            this.els.storyGenerateBtn.style.display = isLast ? "" : "none";
        }
    },

    /** Save the current question's textarea value into _storyAnswers. */
    _saveCurrentAnswer() {
        const chapters = this.els.storyQuestions?.querySelectorAll(
            ".journal-chapter",
        );
        if (!chapters || !chapters[this._currentQuestion]) return;

        const textarea = chapters[this._currentQuestion].querySelector(
            ".journal-chapter-textarea",
        );
        if (textarea) {
            this._storyAnswers[this._currentQuestion] = textarea.value;
        }
    },

    /** Move to the next story question. */
    _nextStoryQuestion() {
        this._saveCurrentAnswer();
        const total = this.els.storyQuestions?.querySelectorAll(
            ".journal-chapter",
        ).length;
        if (this._currentQuestion < (total || 1) - 1) {
            this._showStoryQuestion(this._currentQuestion + 1);
        }
    },

    /** Move to the previous story question. */
    _prevStoryQuestion() {
        this._saveCurrentAnswer();
        if (this._currentQuestion > 0) {
            this._showStoryQuestion(this._currentQuestion - 1);
        }
    },

    /** Return a default ability score for the selected class. */
    _getDefaultAbility(abilName) {
        const cls = this.els.charClass?.value || this.selectedClass;
        const template =
            this._rules?.class_templates?.[cls];
        if (template && template.abilities && template.abilities[abilName] != null) {
            return template.abilities[abilName];
        }
        return 10;
    },

    /** Build the request body for the generate endpoint. */
    _buildGenerateRequestBody() {
        const standardAbilities =
            this._rules?.standard_abilities || ["STR", "DEX", "CON", "INT", "WIS", "CHA"];
        const abilities = {};
        for (const abil of standardAbilities) {
            abilities[abil] = this.abilities[abil] ?? this._getDefaultAbility(abil);
        }
        const answersObj = {};
        this._storyAnswers.forEach((a, i) => { answersObj[String(i)] = a || ""; });
        const name = this.els.charName?.value.trim() || "";
        const cls = this.els.charClass?.value || this.selectedClass;
        return { abilities, answers: answersObj, name, character_class: cls };
    },

    /** Submit story answers to the backend for AI character generation. */
    async _submitStoryAnswers() {
        this._saveCurrentAnswer();

        // Check that at least 3 answers are filled
        const filled = this._storyAnswers.filter(
            (a) => a && a.trim().length > 0,
        );
        if (filled.length < 3) {
            alert(
                "Please answer at least 3 questions so the Dungeon Master " +
                    "has enough to weave your story.",
            );
            return;
        }

        // Check provider config
        if (!App.state.provider) {
            alert(
                "No LLM provider configured! Go to the Connection screen " +
                    "and set up a provider first.",
            );
            return;
        }

        const { abilities, answers, name, character_class } =
            this._buildGenerateRequestBody();

        const body = {
            answers,
            abilities,
            character_class,
            provider: App.state.provider,
        };
        if (name) {
            body.name = name;
        }

        // Show loading state
        const genBtn = this.els.storyGenerateBtn;
        if (genBtn) {
            genBtn.disabled = true;
            genBtn.textContent = "Weaving...";
        }

        try {
            const resp = await fetch("/api/character/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            const data = await resp.json();

            if (!resp.ok || !data.ok) {
                throw new Error(
                    data.error || `Server responded with ${resp.status}`,
                );
            }

            this._showReviewScreen(data.character);
        } catch (err) {
            alert("Failed to generate character: " + err.message);
        } finally {
            if (genBtn) {
                genBtn.disabled = false;
                genBtn.textContent = "✨ Weave My Story";
            }
        }
    },

    // ------------------------------------------------------------------
    // Review Screen
    // ------------------------------------------------------------------

    /** Display the review screen with the generated/created character. */
    _showReviewScreen(character) {
        this._generatedCharacter = character;
        this._mode = "review";
        this._isEditing = false;

        // Hide the story section
        const storySection = document.getElementById("story-section");
        if (storySection) storySection.style.display = "none";

        // Show the review section
        if (this.els.reviewSection) {
            this.els.reviewSection.style.display = "";
        }

        // Ensure campfire content is visible (review lives inside it)
        if (this.els.campfireContent) {
            this.els.campfireContent.classList.add("active");
        }
        if (this.els.manualContent) {
            this.els.manualContent.classList.remove("active");
        }

        // Make sure sub-tab highlighting reflects campfire is active
        if (this.els.campfireTab) {
            this.els.campfireTab.classList.add("active");
        }
        if (this.els.manualTab) {
            this.els.manualTab.classList.remove("active");
        }

        // Render the character sheet
        this._renderCharacterSheet(character);

        // Hide generate loading if it was visible
        const genBtn = this.els.storyGenerateBtn;
        if (genBtn) {
            genBtn.disabled = false;
            genBtn.textContent = "✨ Weave My Story";
        }

        // Ensure review loading is hidden
        if (this.els.reviewLoading) {
            this.els.reviewLoading.style.display = "none";
        }
        if (this.els.reviewCharacterSheet) {
            this.els.reviewCharacterSheet.style.display = "";
        }

        // Reset edit button text
        if (this.els.reviewEditBtn) {
            this.els.reviewEditBtn.textContent = "✏️ Edit";
        }
    },

    /** Render the full character sheet in the review section. */
    _renderCharacterSheet(character) {
        const container = this.els.reviewCharacterSheet;
        if (!container) return;

        // Determine standard abilities list
        const abilities = this._rules?.standard_abilities || [
            "STR",
            "DEX",
            "CON",
            "INT",
            "WIS",
            "CHA",
        ];

        container.innerHTML = `
            <div class="review-sheet-name" data-field="name">
                ${_esc(character.name || "Unnamed Hero")}
            </div>
            <div class="review-sheet-class">
                ${_esc(character.character_class || "Unknown")} —
                Level ${character.level ?? 1}
            </div>

            <div class="review-sheet-stats">
                ${abilities
                    .map(
                        (abil) => `
                    <div class="review-stat">
                        <div class="review-stat-label">${_esc(abil)}</div>
                        <div class="review-stat-value"
                             data-field="abilities.${_esc(abil)}">
                            ${character.abilities?.[abil] ?? 10}
                        </div>
                    </div>
                `,
                    )
                    .join("")}
            </div>

            <div class="review-sheet-details">
                <div class="review-field">
                    <div class="review-field-label">Hit Points</div>
                    <div class="review-field-value" data-field="hp">
                        ${character.hp ?? 0} / ${character.max_hp ?? 0}
                    </div>
                </div>
                <div class="review-field">
                    <div class="review-field-label">Armour Class</div>
                    <div class="review-field-value" data-field="ac">
                        ${character.ac ?? 10}
                    </div>
                </div>
                <div class="review-field">
                    <div class="review-field-label">Gold</div>
                    <div class="review-field-value" data-field="gold">
                        ${character.gold ?? 0} gp
                    </div>
                </div>
                <div class="review-field">
                    <div class="review-field-label">Skills</div>
                    <div class="review-field-value" data-field="skills">
                        ${(character.skills || []).join(", ") || "None"}
                    </div>
                </div>
                <div class="review-field">
                    <div class="review-field-label">Appearance</div>
                    <div class="review-field-value" data-field="appearance">
                        ${_esc(character.appearance || "None")}
                    </div>
                </div>
                <div class="review-field">
                    <div class="review-field-label">Backstory</div>
                    <div class="review-field-value" data-field="backstory">
                        ${_esc(character.backstory || "None")}
                    </div>
                </div>
                <div class="review-field">
                    <div class="review-field-label">Inventory</div>
                    <div class="review-field-value" data-field="inventory">
                        ${(character.inventory || []).join(", ") || "None"}
                    </div>
                </div>
            </div>
        `;
    },

    /** Toggle between display and edit mode for review fields. */
    _toggleEditMode() {
        if (!this._generatedCharacter) return;
        if (!this._isEditing) {
            this._enterEditMode();
        } else {
            this._saveEditMode();
        }
    },

    /** Switch review fields to editable inputs. */
    _enterEditMode() {
        const container = this.els.reviewCharacterSheet;
        const character = this._generatedCharacter;
        const fields = container.querySelectorAll("[data-field]");

        // Replace text with inputs
        fields.forEach((el) => {
            const path = el.dataset.field;
            const value = this._getFieldByPath(character, path);
            const display = el.textContent.trim();

            if (path === "backstory" || path === "appearance") {
                const textarea = document.createElement("textarea");
                textarea.value =
                    value != null ? String(value) : display;
                textarea.dataset.field = path;
                el.textContent = "";
                el.appendChild(textarea);
            } else if (path.startsWith("abilities.")) {
                const input = document.createElement("input");
                input.type = "number";
                input.min = 3;
                input.max = 18;
                input.value =
                    value != null ? String(value) : display;
                input.dataset.field = path;
                el.textContent = "";
                el.appendChild(input);
            } else if (
                path === "skills" ||
                path === "inventory"
            ) {
                const input = document.createElement("input");
                input.type = "text";
                input.value = Array.isArray(value)
                    ? value.join(", ")
                    : display;
                input.dataset.field = path;
                el.textContent = "";
                el.appendChild(input);
            } else if (
                path === "hp" ||
                path === "max_hp" ||
                path === "ac" ||
                path === "gold"
            ) {
                const parts = display.split(" / ");
                const rawVal = parts[0];
                const input = document.createElement("input");
                input.type = "number";
                input.min = 0;
                input.value =
                    value != null ? String(value) : rawVal;
                input.dataset.field = path;
                el.textContent = "";
                el.appendChild(input);
            } else {
                // Default: text input
                const input = document.createElement("input");
                input.type = "text";
                input.value =
                    value != null ? String(value) : display;
                input.dataset.field = path;
                el.textContent = "";
                el.appendChild(input);
            }
        });

        this._isEditing = true;
        if (this.els.reviewEditBtn) {
            this.els.reviewEditBtn.textContent = "💾 Save";
        }
    },

    /** Read edit inputs back into the character and re-render. */
    _saveEditMode() {
        const container = this.els.reviewCharacterSheet;
        const character = this._generatedCharacter;
        const fields = container.querySelectorAll("[data-field]");

        // Read inputs and update character
        fields.forEach((el) => {
            const input = el.querySelector(
                "input, textarea",
            );
            if (!input) return;
            const path = input.dataset.field || el.dataset.field;
            let rawValue = input.value;

            if (path.startsWith("abilities.")) {
                const abilName = path.split(".")[1];
                const num = parseInt(rawValue, 10);
                if (!isNaN(num) && num >= 3 && num <= 18) {
                    if (!character.abilities) {
                        character.abilities = {};
                    }
                    character.abilities[abilName] = num;
                }
            } else if (
                path === "skills" ||
                path === "inventory"
            ) {
                const items = rawValue
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean);
                character[path] = items;
            } else if (
                path === "hp" ||
                path === "max_hp" ||
                path === "ac" ||
                path === "gold"
            ) {
                const num = parseInt(rawValue, 10);
                if (!isNaN(num)) {
                    character[path] = num;
                }
            } else {
                character[path] = rawValue;
            }
        });

        // Re-render the sheet with updated values
        this._renderCharacterSheet(character);

        this._isEditing = false;
        if (this.els.reviewEditBtn) {
            this.els.reviewEditBtn.textContent = "✏️ Edit";
        }
    },

    /** Get a nested field value by dot-separated path (e.g. "abilities.STR"). */
    _getFieldByPath(obj, path) {
        const parts = path.split(".");
        let current = obj;
        for (const part of parts) {
            if (current == null || typeof current !== "object") {
                return undefined;
            }
            current = current[part];
        }
        return current;
    },

    /** Re-call the generate API to create a new variant of the character. */
    async _regenerateCharacter() {
        // Show loading, hide sheet
        if (this.els.reviewLoading) {
            this.els.reviewLoading.style.display = "";
        }
        if (this.els.reviewCharacterSheet) {
            this.els.reviewCharacterSheet.style.display = "none";
        }

        // Re-build the same request body
        const { abilities, answers, name, character_class } =
            this._buildGenerateRequestBody();
        const body = {
            answers,
            abilities,
            character_class,
            provider: App.state.provider,
        };
        if (name) {
            body.name = name;
        }

        try {
            const resp = await fetch("/api/character/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            const data = await resp.json();

            if (!resp.ok || !data.ok) {
                throw new Error(
                    data.error || `Server responded with ${resp.status}`,
                );
            }

            this._generatedCharacter = data.character;
            this._renderCharacterSheet(data.character);

            // Hide loading, show sheet
            if (this.els.reviewLoading) {
                this.els.reviewLoading.style.display = "none";
            }
            if (this.els.reviewCharacterSheet) {
                this.els.reviewCharacterSheet.style.display = "";
            }

            // Reset edit state
            this._isEditing = false;
            if (this.els.reviewEditBtn) {
                this.els.reviewEditBtn.textContent = "✏️ Edit";
            }
        } catch (err) {
            alert("Failed to regenerate character: " + err.message);
            if (this.els.reviewLoading) {
                this.els.reviewLoading.style.display = "none";
            }
            if (this.els.reviewCharacterSheet) {
                this.els.reviewCharacterSheet.style.display = "";
            }
        }
    },

    /** Store the character and navigate to the game view. */
    _startAdventure() {
        if (!this._generatedCharacter) return;
        App.state.character = this._generatedCharacter;
        App.navigate("game");
    },

    // ------------------------------------------------------------------
    // Point-Buy Logic
    // ------------------------------------------------------------------

    /** Get the point-buy cost for a given ability score. */
    _getCost(score) {
        const costs = this._rules?.point_buy?.costs || {};
        return parseInt(costs[score]) || 0;
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
            (this._rules?.point_buy?.max_points ?? 27) -
            this._totalPointsForScores(template.abilities);
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

    /** Update ability increment/decrement button states for a grid. */
    _updateAbilityButtons(gridSelector) {
        const standardAbilities =
            this._rules?.standard_abilities || ["STR", "DEX", "CON", "INT", "WIS", "CHA"];
        for (const abil of standardAbilities) {
            const card = document.querySelector(
                `${gridSelector} [data-abil="${abil}"]`,
            );
            if (card) {
                const incBtn = card.querySelector(".abil-btn.inc");
                const decBtn = card.querySelector(".abil-btn.dec");
                if (incBtn) incBtn.disabled = !this._canIncrease(abil);
                if (decBtn) decBtn.disabled = !this._canDecrease(abil);
            }
        }
    },

    /** Refresh all ability score display elements. */
    _updateUI() {
        // Update individual scores
        for (const [abil, score] of Object.entries(this.abilities)) {
            // Manual grid
            const scoreEl = document.getElementById(`abil-${abil}`);
            const costEl = document.getElementById(`cost-${abil}`);
            if (scoreEl) scoreEl.textContent = score;
            if (costEl) {
                costEl.textContent = `(${this._getCost(score)} pts)`;
            }

            // Campfire grid
            const campScoreEl = document.getElementById(`camp-abil-${abil}`);
            const campCostEl = document.getElementById(`camp-cost-${abil}`);
            if (campScoreEl) campScoreEl.textContent = score;
            if (campCostEl) {
                campCostEl.textContent = `(${this._getCost(score)} pts)`;
            }
        }

        // Update button states for both grids
        this._updateAbilityButtons("#abilities-grid");
        this._updateAbilityButtons("#camp-abilities-grid");

        // Update remaining points (manual)
        if (this.els.remainingSpan) {
            this.els.remainingSpan.textContent = this.remainingPoints;
        }
        // Update remaining points (campfire)
        if (this.els.campRemainingSpan) {
            this.els.campRemainingSpan.textContent = this.remainingPoints;
        }
    },

    // ------------------------------------------------------------------
    // Character Creation — Manual Build
    // ------------------------------------------------------------------

    /** Validate and create the character via the backend (manual build). */
    async _createCharacter() {
        const name = this.els.nameManual?.value.trim();
        if (!name) {
            this._showValidation("Enter a character name.", "error");
            return;
        }

        const cls = this.els.classManual?.value;
        const appearance = this.els.appearance?.value.trim();
        const backstory = this.els.backstory?.value.trim();

        this._showValidation("Creating character...", "info");

        try {
            const resp = await fetch("/api/character/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: name,
                    character_class: cls,
                    abilities: this.abilities,
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

            // Show the review screen instead of navigating directly
            this._showReviewScreen(data.character);
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
                                ${
                                    c.timestamp
                                        ? " · " + _formatTimestamp(c.timestamp)
                                        : ""
                                }
                            </p>
                        </div>
                        <div class="char-actions">
                            <button class="btn btn-sm btn-load"
                                data-id="${_esc(c.id)}"
                                data-name="${_esc(c.name)}">Load</button>
                            <button class="btn btn-sm btn-danger btn-delete"
                                data-id="${_esc(c.id)}"
                                data-name="${_esc(c.name)}">Del</button>
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
                .map((s) => {
                    const saveName =
                        s.name || s.character_name || "Unknown";
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
                })
                .join("");

            savesContainer
                .querySelectorAll(".btn-continue-save")
                .forEach((btn) => {
                    btn.addEventListener("click", () => {
                        const card = btn.closest(".save-card");
                        const saveName = card.dataset.name;
                        App.state.loadSaveName = saveName;
                        App.navigate("game");
                    });
                });
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
