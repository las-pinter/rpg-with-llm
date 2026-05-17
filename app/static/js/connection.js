/**
 * LLM-Powered RPG — Connection View
 *
 * Handles LLM provider selection, connection testing, and model
 * discovery.  The user must successfully test a connection before
 * they can proceed to character creation.
 */
const ConnectionView = {
    /** Provider definitions with default URLs and key requirements. */
    providers: {
        ollama: {
            url: "http://localhost:11434",
            needsKey: false,
            label: "Ollama",
        },
        groq: {
            url: "https://api.groq.com/openai/v1",
            needsKey: true,
            label: "Groq",
        },
        openrouter: {
            url: "https://openrouter.ai/api/v1",
            needsKey: true,
            label: "OpenRouter",
        },
        custom: {
            url: "http://localhost:11434",
            needsKey: false,
            label: "Custom",
        },
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
        };

        // Provider change → update URL default + API key visibility
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

        // Set initial provider state
        this._onProviderChange();

        // Restore previous connection if available
        this._restoreState();
    },

    // ------------------------------------------------------------------
    // Provider switching
    // ------------------------------------------------------------------

    /** Handle provider dropdown change — update URL and API key field. */
    _onProviderChange() {
        const key = this.els.providerSelect.value;
        const provider = this.providers[key];
        if (!provider) return;

        this.els.baseUrl.value = provider.url;

        // Show/hide API key field based on provider
        if (provider.needsKey) {
            this.els.apiKeyGroup.style.display = "block";
        } else {
            this.els.apiKeyGroup.style.display = "none";
        }

        // Disable fetch models for non-Ollama providers (they use
        // different model listing endpoints)
        if (key === "ollama" || key === "custom") {
            this.els.fetchModels.disabled = false;
        } else {
            this.els.fetchModels.disabled = true;
        }

        // Reset connection status
        this._setStatus("idle", "Provider changed — test the connection");
        this.els.startBtn.disabled = true;
    },

    // ------------------------------------------------------------------
    // Model fetching
    // ------------------------------------------------------------------

    /** Fetch available models from the Ollama /api/tags endpoint. */
    async _fetchModels() {
        const baseUrl = this.els.baseUrl.value.trim().replace(/\/+$/, "");
        const url = baseUrl + "/api/tags";

        this.els.fetchModels.disabled = true;
        this.els.fetchModels.textContent = "Fetching...";
        this._setStatus("loading", "Fetching models...");

        try {
            const resp = await fetch(url, { signal: AbortSignal.timeout(8000) });
            if (!resp.ok) {
                throw new Error(
                    `Server returned HTTP ${resp.status}: ${resp.statusText}`,
                );
            }
            const data = await resp.json();
            const models = data.models || [];

            if (models.length === 0) {
                this._setStatus("error", "No models found on this server");
                return;
            }

            // Populate the select
            this.els.modelSelect.innerHTML = "";
            models.forEach((m) => {
                const opt = document.createElement("option");
                opt.value = m.name || m.model || m;
                opt.textContent = m.name || m.model || m;
                this.els.modelSelect.appendChild(opt);
            });

            // Also populate datalist for the text input
            if (models.length > 0) {
                this.els.modelInput.placeholder =
                    models[0].name || models[0].model || "llama3.2";
            }

            this._setStatus("success", `Found ${models.length} model(s)`);
        } catch (err) {
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
                }),
                signal: AbortSignal.timeout(15000),
            });

            const data = await resp.json();

            if (data.ok) {
                this._setStatus(
                    "success",
                    `Connected! Latency: ${data.latency_ms.toFixed(1)}ms — Model: ${data.model}`,
                );
                this.els.startBtn.disabled = false;

                // Save to app state
                App.state.provider = {
                    base_url: baseUrl,
                    model: model,
                    api_key: apiKey,
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

    /** Navigate to the character creation view. */
    _startAdventure() {
        if (this.els.startBtn.disabled) return;
        App.navigate("character");
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

    // ------------------------------------------------------------------
    // State persistence (localStorage)
    // ------------------------------------------------------------------

    _saveState() {
        try {
            const data = {
                provider: App.state.provider,
                baseUrl: this.els.baseUrl.value,
                model: this._getModel(),
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
            if (data.provider) {
                App.state.provider = data.provider;
            }
        } catch (e) {
            // Corrupted data — ignore
        }
    },
};

// Auto-initialise on DOMContentLoaded
document.addEventListener("DOMContentLoaded", () => ConnectionView.init());
