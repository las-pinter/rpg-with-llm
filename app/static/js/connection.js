/**
 * LLM-Powered RPG — Connection View
 *
 * Handles LLM provider selection, connection testing, and model
 * discovery.  The user must successfully test a connection before
 * they can proceed to character creation.
 */
const ConnectionView = {
    /** Provider metadata — label, API key requirement. URLs come from the
     *  backend settings API or user input. */
    providers: {
        ollama: { needsKey: false, label: "Ollama" },
        groq: { needsKey: true, label: "Groq" },
        openrouter: { needsKey: true, label: "OpenRouter" },
        custom: { needsKey: false, label: "Custom" },
        unsloth: { needsKey: false, label: "Unsloth" },
        llamacpp: { needsKey: false, label: "llama.cpp" },
    },

    /** DOM element references (populated in init). */
    els: {},

    /** Initialise the view — bind event listeners. */
    init() {
        this.els = {
            providerSelect: document.getElementById("provider-select"),
            baseUrl: document.getElementById("base-url"),
            apiKey: document.getElementById("api-key"),
            apiKeyGroup: document.getElementById("api-key-group"),
            modelSelect: document.getElementById("model-select"),
            modelInput: document.getElementById("model-input"),
            fetchModels: document.getElementById("fetch-models"),
            testBtn: document.getElementById("test-connection"),
            status: document.getElementById("connection-status"),
            statusDot: document.querySelector("#connection-status .status-dot"),
            statusText: document.querySelector("#connection-status .status-text"),
            startBtn: document.getElementById("start-adventure"),
            // Advanced per-agent toggle and section
            advancedToggle: document.getElementById("advanced-toggle"),
            advancedSection: document.getElementById("advanced-section"),
            // NPC provider fields
            npcProviderSelect: document.getElementById("npc-provider-select"),
            npcBaseUrl: document.getElementById("npc-base-url"),
            npcApiKey: document.getElementById("npc-api-key"),
            npcApiKeyGroup: document.getElementById("npc-api-key-group"),
            npcModelInput: document.getElementById("npc-model-input"),
            // Summarizer provider fields
            summarizerProviderSelect: document.getElementById(
                "summarizer-provider-select",
            ),
            summarizerBaseUrl: document.getElementById("summarizer-base-url"),
            summarizerApiKey: document.getElementById("summarizer-api-key"),
            summarizerApiKeyGroup: document.getElementById(
                "summarizer-api-key-group",
            ),
            summarizerModelInput: document.getElementById(
                "summarizer-model-input",
            ),
            // NPC/Summarizer enable checkboxes and config groups
            npcEnabled: document.getElementById("npc-enabled"),
            npcConfigGroup: document.getElementById("npc-config-group"),
            summarizerEnabled: document.getElementById("summarizer-enabled"),
            summarizerConfigGroup: document.getElementById(
                "summarizer-config-group",
            ),
            // Generation settings (DM)
            dmMaxTokens: document.getElementById("dm-max-tokens"),
            dmTemperature: document.getElementById("dm-temperature"),
            dmTimeout: document.getElementById("dm-timeout"),
            // NPC generation settings
            npcMaxTokens: document.getElementById("npc-max-tokens"),
            npcTemperature: document.getElementById("npc-temperature"),
            npcTimeout: document.getElementById("npc-timeout"),
            // Summarizer generation settings
            summarizerMaxTokens: document.getElementById("summarizer-max-tokens"),
            summarizerTemperature: document.getElementById("summarizer-temperature"),
            summarizerTimeout: document.getElementById("summarizer-timeout"),
        };

        // Provider change → update API key visibility
        this.els.providerSelect.addEventListener(
            "change",
            () => this._onProviderChange(),
        );

        // Fetch models button
        this.els.fetchModels.addEventListener(
            "click",
            () => this._fetchModels(),
        );

        // Test connection
        this.els.testBtn.addEventListener(
            "click",
            () => this._testConnection(),
        );

        // Start adventure
        this.els.startBtn.addEventListener(
            "click",
            () => this._startAdventure(),
        );

        // Also trigger model input on blur (so typed models are stored)
        this.els.modelInput.addEventListener("change", () => {
            this._setStatus("idle", "Model set to: " + this.els.modelInput.value);
        });

        // Advanced toggle — show/hide per-agent config section
        if (this.els.advancedToggle) {
            this.els.advancedToggle.addEventListener("click", () => {
                const expanded =
                    this.els.advancedSection.style.display !== "none";
                this.els.advancedSection.style.display = expanded
                    ? "none"
                    : "block";
                this.els.advancedToggle.textContent = expanded
                    ? "\u25B8 Advanced"
                    : "\u25BE Advanced";
            });
        }

        // NPC provider change → update defaults
        if (this.els.npcProviderSelect) {
            this.els.npcProviderSelect.addEventListener(
                "change",
                () => this._onAgentProviderChange("npc"),
            );
        }

        // Summarizer provider change → update defaults
        if (this.els.summarizerProviderSelect) {
            this.els.summarizerProviderSelect.addEventListener(
                "change",
                () => this._onAgentProviderChange("summarizer"),
            );
        }

        // NPC enable toggle
        if (this.els.npcEnabled) {
            this.els.npcEnabled.addEventListener("change", () => {
                const enabled = this.els.npcEnabled.checked;
                this.els.npcConfigGroup.style.display = enabled
                    ? "block"
                    : "none";
                if (enabled) {
                    this._populateAgentDefaults("npc");
                }
            });
        }

        // Summarizer enable toggle
        if (this.els.summarizerEnabled) {
            this.els.summarizerEnabled.addEventListener("change", () => {
                const enabled = this.els.summarizerEnabled.checked;
                this.els.summarizerConfigGroup.style.display = enabled
                    ? "block"
                    : "none";
                if (enabled) {
                    this._populateAgentDefaults("summarizer");
                }
            });
        }

        // Set initial provider state (API key visibility, etc.)
        this._onProviderChange();

        // Initialise per-agent provider defaults
        if (this.els.npcProviderSelect) this._onAgentProviderChange("npc");
        if (this.els.summarizerProviderSelect) {
            this._onAgentProviderChange("summarizer");
        }

        // Fetch settings from backend, then restore saved state
        this._fetchSettings();
    },

    // ------------------------------------------------------------------
    // Provider switching
    // ------------------------------------------------------------------

    /** Handle provider dropdown change — update API key field visibility. */
    _onProviderChange() {
        const key = this.els.providerSelect.value;
        const provider = this.providers[key];
        if (!provider) return;

        // Show/hide API key field based on provider
        if (provider.needsKey) {
            this.els.apiKeyGroup.style.display = "block";
        } else {
            this.els.apiKeyGroup.style.display = "none";
        }

        // Enable Fetch Models for all providers — the server-side
        // endpoint handles provider-specific model list APIs
        this.els.fetchModels.disabled = false;

        // Reset connection status
        this._setStatus("idle", "Provider changed — test the connection");
        this.els.startBtn.disabled = true;
    },

    /** Handle per-agent provider dropdown change — update API key visibility. */
    _onAgentProviderChange(prefix) {
        const selectKey = prefix + "ProviderSelect";
        const apiKeyKey = prefix + "ApiKey";
        const apiKeyGroupKey = prefix + "ApiKeyGroup";

        const sel = this.els[selectKey];
        const apiKeyGroup = this.els[apiKeyGroupKey];
        const apiKeyInput = this.els[apiKeyKey];

        if (!sel) return;

        const key = sel.value;
        const provider = this.providers[key];
        if (!provider) return;

        if (provider.needsKey) {
            apiKeyGroup.style.display = "block";
        } else {
            apiKeyGroup.style.display = "none";
            if (apiKeyInput) apiKeyInput.value = "";
        }
    },

    /** Populate per-agent provider fields from the main provider's current values. */
    _populateAgentDefaults(prefix) {
        const mainType = this.els.providerSelect.value;
        const mainUrl = this.els.baseUrl.value;
        const mainModel = this._getModel();
        const mainApiKey = this.els.apiKey.value;

        const typeSelect = this.els[prefix + "ProviderSelect"];
        const urlInput = this.els[prefix + "BaseUrl"];
        const modelInput = this.els[prefix + "ModelInput"];
        const apiKeyInput = this.els[prefix + "ApiKey"];
        const apiKeyGroup = this.els[prefix + "ApiKeyGroup"];

        if (typeSelect) typeSelect.value = mainType;
        if (urlInput) urlInput.value = mainUrl;
        if (modelInput) modelInput.value = mainModel;
        if (apiKeyInput) apiKeyInput.value = mainApiKey;

        // Show/hide API key based on the selected provider type
        const provider = this.providers[mainType];
        if (apiKeyGroup && provider) {
            apiKeyGroup.style.display = provider.needsKey ? "block" : "none";
            if (!provider.needsKey && apiKeyInput) {
                apiKeyInput.value = "";
            }
        }

        // Also copy generation settings from DM
        const dmMaxTokens = this.els.dmMaxTokens ? this.els.dmMaxTokens.value : undefined;
        const dmTemp = this.els.dmTemperature ? this.els.dmTemperature.value : undefined;
        const dmTimeout = this.els.dmTimeout ? this.els.dmTimeout.value : undefined;
        if (dmMaxTokens && this.els[prefix + "MaxTokens"]) {
            this.els[prefix + "MaxTokens"].value = dmMaxTokens;
        }
        if (dmTemp && this.els[prefix + "Temperature"]) {
            this.els[prefix + "Temperature"].value = dmTemp;
        }
        if (dmTimeout && this.els[prefix + "Timeout"]) {
            this.els[prefix + "Timeout"].value = dmTimeout;
        }
    },

    // ------------------------------------------------------------------
    // Model fetching
    // ------------------------------------------------------------------

    /** Fetch available models via the server-side proxy. */
    async _fetchModels() {
        const baseUrl = this.els.baseUrl.value.trim();
        const model = this._getModel();
        const apiKey = this.els.apiKey.value.trim() || undefined;

        if (!baseUrl) {
            this._setStatus("error", "Base URL is required to fetch models");
            return;
        }

        this.els.fetchModels.disabled = true;
        this.els.fetchModels.textContent = "Fetching...";
        this._setStatus("loading", "Fetching models...");

        try {
            const resp = await fetch("/api/models", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    base_url: baseUrl,
                    model: model || "placeholder",
                    api_key: apiKey,
                    provider_type: this.els.providerSelect.value,
                }),
                signal: AbortSignal.timeout(15000),
            });

            const data = await resp.json();

            if (!data.ok) {
                throw new Error(data.error || "Server returned error");
            }

            const models = data.models || [];

            if (models.length === 0) {
                this._setStatus("error", "No models found on this server");
                return;
            }

            // Populate the select
            this.els.modelSelect.innerHTML = "";
            models.forEach((m) => {
                const opt = document.createElement("option");
                opt.value = m.id;
                opt.textContent = m.name || m.id;
                this.els.modelSelect.appendChild(opt);
            });

            // Also populate datalist for the text input
            if (models.length > 0) {
                this.els.modelInput.placeholder =
                    models[0].name || models[0].id || "model-name";
            }

            this._setStatus("success", `Found ${models.length} model(s)`);
        } catch (err) {
            this.els.modelSelect.innerHTML = "";
            if (err.name === "TimeoutError") {
                this._setStatus("error", "Request timed out — is the server running?");
            } else {
                this._setStatus(
                    "error",
                    "Could not fetch models: " + err.message,
                );
            }
        } finally {
            this.els.fetchModels.disabled = false;
            this.els.fetchModels.textContent = "Fetch";
        }
    },

    // ------------------------------------------------------------------
    // Settings persistence (backend)
    // ------------------------------------------------------------------

    /** POST settings to the backend and return the response data.
     *
     *  Returns the full response JSON on success, or null on failure.
     *  Does NOT throw — callers should check the return value.
     *  This is a best-effort operation; failures are only logged.
     */
    async _postSettings(payload) {
        try {
            const resp = await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
                signal: AbortSignal.timeout(10000),
            });
            const data = await resp.json();
            if (data.ok) return data;
            console.warn(
                "Settings POST returned error:",
                data.error || data.errors,
            );
            return null;
        } catch (e) {
            console.warn("Failed to save settings to backend:", e.message);
            return null;
        }
    },

    // ------------------------------------------------------------------
    // Connection testing
    // ------------------------------------------------------------------

    /** Test the connection by calling POST /api/health. */
    async _testConnection() {
        const baseUrl = this.els.baseUrl.value.trim();
        const model = this._getModel();

        if (!baseUrl) {
            this._setStatus("error", "Base URL is required");
            return;
        }
        if (!model) {
            this._setStatus("error", "Please select or enter a model");
            return;
        }

        const apiKey = this.els.apiKey.value.trim() || undefined;

        this.els.testBtn.disabled = true;
        this.els.testBtn.textContent = "Testing...";
        this._setStatus("loading", "Testing connection...");

        try {
            const resp = await fetch("/api/health", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    base_url: baseUrl,
                    model: model,
                    api_key: apiKey,
                    provider_type: this.els.providerSelect.value,
                }),
                signal: AbortSignal.timeout(15000),
            });

            const data = await resp.json();

            if (data.ok) {
                // POST provider config to backend settings (best-effort)
                const settingsResult = await this._postSettings({
                    base_url: baseUrl,
                    model: model,
                    api_key: apiKey,
                    provider_type: this.els.providerSelect.value,
                });

                if (settingsResult && settingsResult.settings) {
                    this._setStatus(
                        "success",
                        `Connected! Latency: ${data.latency_ms.toFixed(1)}ms — Settings saved`,
                    );
                } else {
                    this._setStatus(
                        "success",
                        `Connected! Latency: ${data.latency_ms.toFixed(1)}ms — Model: ${data.model}`,
                    );
                }
                this.els.startBtn.disabled = false;

                // Save to app state (authoritative source is backend,
                // localStorage is secondary cache)
                App.state.provider = {
                    base_url: baseUrl,
                    model: model,
                    api_key: apiKey,
                    provider_type: this.els.providerSelect.value,
                };
                this._saveState();
            } else {
                this._setStatus(
                    "error",
                    data.error || "Connection failed (no details)",
                );
                this.els.startBtn.disabled = true;
            }
        } catch (err) {
            if (err.name === "TimeoutError") {
                this._setStatus(
                    "error",
                    "Request timed out — check your URL and try again",
                );
            } else {
                this._setStatus("error", "Connection error: " + err.message);
            }
            this.els.startBtn.disabled = true;
        } finally {
            this.els.testBtn.disabled = false;
            this.els.testBtn.textContent = "Test Connection";
        }
    },

    // ------------------------------------------------------------------
    // Start Adventure
    // ------------------------------------------------------------------

    /** Save provider configs and navigate to character creation. */
    async _startAdventure() {
        if (this.els.startBtn.disabled) return;

        // Save DM provider config
        const baseUrl = this.els.baseUrl.value.trim();
        const model = this._getModel();
        const apiKey = this.els.apiKey.value.trim() || undefined;
        App.state.provider = {
            base_url: baseUrl,
            model: model,
            api_key: apiKey,
            provider_type: this.els.providerSelect.value,
        };

        // Add generation settings to provider config
        App.state.provider.max_tokens = parseInt(this.els.dmMaxTokens.value, 10) || undefined;
        App.state.provider.temperature = parseFloat(this.els.dmTemperature.value) || undefined;
        App.state.provider.timeout = parseInt(this.els.dmTimeout.value, 10) || undefined;

        // Save per-agent provider configs (null = use DM provider)
        App.state.npcProvider = this._buildAgentProvider("npc");
        App.state.summarizerProvider = this._buildAgentProvider("summarizer");

        // Build full flat settings payload for the backend
        const settingsPayload = {
            base_url: baseUrl,
            model: model,
            api_key: apiKey,
            provider_type: this.els.providerSelect.value,
            dm_max_tokens:
                parseInt(this.els.dmMaxTokens.value, 10) || undefined,
            dm_temperature:
                parseFloat(this.els.dmTemperature.value) || undefined,
            dm_timeout:
                parseInt(this.els.dmTimeout.value, 10) || undefined,
            npc_max_tokens:
                parseInt(this.els.npcMaxTokens.value, 10) || undefined,
            npc_temperature:
                parseFloat(this.els.npcTemperature.value) || undefined,
            npc_timeout:
                parseInt(this.els.npcTimeout.value, 10) || undefined,
            summarizer_max_tokens:
                parseInt(this.els.summarizerMaxTokens.value, 10) || undefined,
            summarizer_temperature:
                parseFloat(this.els.summarizerTemperature.value) || undefined,
            summarizer_timeout:
                parseInt(this.els.summarizerTimeout.value, 10) || undefined,
        };
        // POST settings to the backend (best-effort — don't block navigation)
        await this._postSettings(settingsPayload);

        this._saveState();
        App.navigate("character");
    },

    /** Build a provider config for a per-agent (npc / summarizer), or null. */
    _buildAgentProvider(prefix) {
        const enabledCheckbox = this.els[prefix + "Enabled"];
        // If not enabled, return null (use main provider)
        if (!enabledCheckbox || !enabledCheckbox.checked) {
            return null;
        }

        const providerType = this.els[prefix + "ProviderSelect"].value;
        const baseUrl = this.els[prefix + "BaseUrl"].value.trim();
        const model = this.els[prefix + "ModelInput"].value.trim();

        if (!baseUrl || !model) return null;

        const config = {
            base_url: baseUrl,
            model: model,
            provider_type: providerType,
        };

        const apiKey = this.els[prefix + "ApiKey"].value.trim();
        if (apiKey) {
            config.api_key = apiKey;
        }

        // Add per-agent generation settings
        const maxTokensEl = this.els[prefix + "MaxTokens"];
        const tempEl = this.els[prefix + "Temperature"];
        const timeoutEl = this.els[prefix + "Timeout"];
        if (maxTokensEl) config.max_tokens = parseInt(maxTokensEl.value, 10) || undefined;
        if (tempEl) config.temperature = parseFloat(tempEl.value) || undefined;
        if (timeoutEl) config.timeout = parseInt(timeoutEl.value, 10) || undefined;

        return config;
    },

    // ------------------------------------------------------------------
    // Status display
    // ------------------------------------------------------------------

    /** Update the connection status indicator. */
    _setStatus(type, message) {
        this.els.status.className = "status-indicator " + type;
        this.els.statusText.textContent = message;
    },

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    /** Get the currently selected or typed model name. */
    _getModel() {
        const selected = this.els.modelSelect.value;
        if (selected) return selected;
        const typed = this.els.modelInput.value.trim();
        return typed || "";
    },

    /** Populate form fields from backend settings response. */
    _populateFromSettings(settings) {
        if (!settings) return;

        // Provider type
        if (settings.provider_type) {
            this.els.providerSelect.value = settings.provider_type;
        }
        // Base URL
        if (settings.base_url) {
            this.els.baseUrl.value = settings.base_url;
        }
        // API key (backend may return null — skip it)
        if (settings.api_key) {
            this.els.apiKey.value = settings.api_key;
        }
        // Model
        if (settings.model) {
            this.els.modelInput.value = settings.model;
        }

        // DM generation settings
        if (settings.dm_max_tokens != null && this.els.dmMaxTokens) {
            this.els.dmMaxTokens.value = settings.dm_max_tokens;
        }
        if (settings.dm_temperature != null && this.els.dmTemperature) {
            this.els.dmTemperature.value = settings.dm_temperature;
        }
        if (settings.dm_timeout != null && this.els.dmTimeout) {
            this.els.dmTimeout.value = settings.dm_timeout;
        }

        // NPC generation settings
        if (settings.npc_max_tokens != null && this.els.npcMaxTokens) {
            this.els.npcMaxTokens.value = settings.npc_max_tokens;
        }
        if (settings.npc_temperature != null && this.els.npcTemperature) {
            this.els.npcTemperature.value = settings.npc_temperature;
        }
        if (settings.npc_timeout != null && this.els.npcTimeout) {
            this.els.npcTimeout.value = settings.npc_timeout;
        }

        // Summarizer generation settings
        if (settings.summarizer_max_tokens != null && this.els.summarizerMaxTokens) {
            this.els.summarizerMaxTokens.value = settings.summarizer_max_tokens;
        }
        if (settings.summarizer_temperature != null && this.els.summarizerTemperature) {
            this.els.summarizerTemperature.value = settings.summarizer_temperature;
        }
        if (settings.summarizer_timeout != null && this.els.summarizerTimeout) {
            this.els.summarizerTimeout.value = settings.summarizer_timeout;
        }

        // Sync UI after populating provider-related fields
        this._onProviderChange();

        // Sync per-agent provider dropdowns to match the main provider type
        if (settings.provider_type && this.els.npcProviderSelect) {
            this.els.npcProviderSelect.value = settings.provider_type;
            this._onAgentProviderChange("npc");
        }
        if (settings.provider_type && this.els.summarizerProviderSelect) {
            this.els.summarizerProviderSelect.value = settings.provider_type;
            this._onAgentProviderChange("summarizer");
        }
    },

    /** Fetch settings from the backend API, then restore saved state. */
    async _fetchSettings() {
        try {
            const resp = await fetch("/api/settings", {
                signal: AbortSignal.timeout(5000),
            });
            const data = await resp.json();
            if (data.ok && data.settings) {
                this._populateFromSettings(data.settings);
            }
        } catch (e) {
            // API unavailable — fall back to HTML defaults (value attributes
            // in the markup) and localStorage. This is graceful degradation.
        }
        // Always restore user's saved state on top of API defaults so that
        // localStorage overrides backend settings.
        this._restoreState();
    },

    // ------------------------------------------------------------------
    // State persistence (localStorage)
    // ------------------------------------------------------------------

    /** Persist to localStorage as a secondary cache.
     *
     *  The authoritative source of settings is the backend
     *  (``/api/settings``).  localStorage is a fallback for offline
     *  resilience.  On page load, ``_fetchSettings()`` fetches fresh
     *  settings from the backend before ``_restoreState()`` overlays
     *  any cached values.
     */
    _saveState() {
        try {
            const data = {
                provider: App.state.provider,
                npcProvider: App.state.npcProvider || null,
                summarizerProvider: App.state.summarizerProvider || null,
                baseUrl: this.els.baseUrl.value,
                model: this._getModel(),
                npcEnabled: this.els.npcEnabled
                    ? this.els.npcEnabled.checked
                    : false,
                summarizerEnabled: this.els.summarizerEnabled
                    ? this.els.summarizerEnabled.checked
                    : false,
                dmMaxTokens: this.els.dmMaxTokens ? this.els.dmMaxTokens.value : 4096,
                dmTemperature: this.els.dmTemperature ? this.els.dmTemperature.value : 0.8,
                dmTimeout: this.els.dmTimeout ? this.els.dmTimeout.value : 300,
                npcMaxTokens: this.els.npcMaxTokens ? this.els.npcMaxTokens.value : 1024,
                npcTemperature: this.els.npcTemperature ? this.els.npcTemperature.value : 0.8,
                npcTimeout: this.els.npcTimeout ? this.els.npcTimeout.value : 300,
                summarizerMaxTokens: this.els.summarizerMaxTokens ? this.els.summarizerMaxTokens.value : 4096,
                summarizerTemperature: this.els.summarizerTemperature ? this.els.summarizerTemperature.value : 0.3,
                summarizerTimeout: this.els.summarizerTimeout ? this.els.summarizerTimeout.value : 300,
            };
            localStorage.setItem("rpg_connection", JSON.stringify(data));
        } catch (e) {
            // localStorage may be full or disabled — silently ignore
        }
    },

    _restoreState() {
        try {
            const raw = localStorage.getItem("rpg_connection");
            if (!raw) return;
            const data = JSON.parse(raw);

            // Restore App.state
            if (data.provider) {
                App.state.provider = data.provider;
            }
            if (data.npcProvider) {
                App.state.npcProvider = data.npcProvider;
            }
            if (data.summarizerProvider) {
                App.state.summarizerProvider = data.summarizerProvider;
            }

            // Restore main provider type selection and refresh UI
            if (data.provider && data.provider.provider_type) {
                this.els.providerSelect.value =
                    data.provider.provider_type;
                this._onProviderChange();
            }

            // Restore base URL
            if (data.baseUrl) {
                this.els.baseUrl.value = data.baseUrl;
            }

            // Restore model
            if (data.model) {
                // Try to set the model select value first
                const options = this.els.modelSelect.options;
                let found = false;
                for (let i = 0; i < options.length; i++) {
                    if (options[i].value === data.model) {
                        this.els.modelSelect.value = data.model;
                        found = true;
                        break;
                    }
                }
                this.els.modelInput.value = data.model;
            }

            // Restore API key if saved in provider
            if (data.provider && data.provider.api_key) {
                this.els.apiKey.value = data.provider.api_key;
            }

            // Restore NPC enabled state
            if (data.npcEnabled && this.els.npcEnabled) {
                this.els.npcEnabled.checked = true;
                this.els.npcConfigGroup.style.display = "block";
            }
            // Restore NPC provider config values if present
            if (
                data.npcProvider &&
                typeof data.npcProvider === "object" &&
                data.npcProvider.base_url
            ) {
                if (
                    this.els.npcProviderSelect &&
                    data.npcProvider.provider_type
                ) {
                    this.els.npcProviderSelect.value =
                        data.npcProvider.provider_type;
                }
                if (this.els.npcBaseUrl && data.npcProvider.base_url) {
                    this.els.npcBaseUrl.value =
                        data.npcProvider.base_url;
                }
                if (this.els.npcModelInput && data.npcProvider.model) {
                    this.els.npcModelInput.value =
                        data.npcProvider.model;
                }
                if (this.els.npcApiKey && data.npcProvider.api_key) {
                    this.els.npcApiKey.value =
                        data.npcProvider.api_key;
                }
                this._onAgentProviderChange("npc");
            }

            // Restore Summarizer enabled state
            if (data.summarizerEnabled && this.els.summarizerEnabled) {
                this.els.summarizerEnabled.checked = true;
                this.els.summarizerConfigGroup.style.display = "block";
            }
            // Restore Summarizer provider config values if present
            if (
                data.summarizerProvider &&
                typeof data.summarizerProvider === "object" &&
                data.summarizerProvider.base_url
            ) {
                if (
                    this.els.summarizerProviderSelect &&
                    data.summarizerProvider.provider_type
                ) {
                    this.els.summarizerProviderSelect.value =
                        data.summarizerProvider.provider_type;
                }
                if (
                    this.els.summarizerBaseUrl &&
                    data.summarizerProvider.base_url
                ) {
                    this.els.summarizerBaseUrl.value =
                        data.summarizerProvider.base_url;
                }
                if (
                    this.els.summarizerModelInput &&
                    data.summarizerProvider.model
                ) {
                    this.els.summarizerModelInput.value =
                        data.summarizerProvider.model;
                }
                if (
                    this.els.summarizerApiKey &&
                    data.summarizerProvider.api_key
                ) {
                    this.els.summarizerApiKey.value =
                        data.summarizerProvider.api_key;
                }
                this._onAgentProviderChange("summarizer");
            }
            // Restore generation settings
            if (data.dmMaxTokens && this.els.dmMaxTokens) {
                this.els.dmMaxTokens.value = data.dmMaxTokens;
            }
            if (data.dmTemperature && this.els.dmTemperature) {
                this.els.dmTemperature.value = data.dmTemperature;
            }
            if (data.dmTimeout && this.els.dmTimeout) {
                this.els.dmTimeout.value = data.dmTimeout;
            }
            if (data.npcMaxTokens && this.els.npcMaxTokens) {
                this.els.npcMaxTokens.value = data.npcMaxTokens;
            }
            if (data.npcTemperature && this.els.npcTemperature) {
                this.els.npcTemperature.value = data.npcTemperature;
            }
            if (data.npcTimeout && this.els.npcTimeout) {
                this.els.npcTimeout.value = data.npcTimeout;
            }
            if (data.summarizerMaxTokens && this.els.summarizerMaxTokens) {
                this.els.summarizerMaxTokens.value = data.summarizerMaxTokens;
            }
            if (data.summarizerTemperature && this.els.summarizerTemperature) {
                this.els.summarizerTemperature.value = data.summarizerTemperature;
            }
            if (data.summarizerTimeout && this.els.summarizerTimeout) {
                this.els.summarizerTimeout.value = data.summarizerTimeout;
            }
        } catch (e) {
            // Corrupted data — ignore
        }
    },
};

// Auto-initialise on DOMContentLoaded
document.addEventListener("DOMContentLoaded", () => ConnectionView.init());
