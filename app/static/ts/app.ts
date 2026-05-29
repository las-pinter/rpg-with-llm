/**
 * LLM-Powered RPG — SPA Router
 *
 * Simple hash-based single-page application router.
 * Manages three views: #connection, #character, #game.
 */
const App: AppInstance = {
    currentView: null,

    /** Shared state passed between views. */
    state: {
        provider: null,   // { base_url, model, api_key }
        character: null,  // Full character data dict
        loadSaveName: null, // Save name to load when navigating to game view
    },

    /** Initialise the router — call once on DOMContentLoaded. */
    init() {
        window.addEventListener("hashchange", () => this._handleRoute());
        if (!window.location.hash) {
            window.location.hash = "connection";
        }
        this._handleRoute();
    },

    /** Internal — parse the current hash and show the matching view. */
    _handleRoute() {
        const hash = window.location.hash.slice(1) || "connection";
        this._showView(hash);
        this.currentView = hash;
    },

    /** Internal — show one view, hide all others. */
    _showView(viewId) {
        document.querySelectorAll(".view").forEach((v) => {
            v.classList.remove("active");
        });
        const el = document.getElementById(`view-${viewId}`);
        if (el) {
            el.classList.add("active");
        } else {
            // Invalid hash — fall back to connection view
            window.location.hash = "connection";
        }
    },

    /** Public — navigate to a view by name (without the #). */
    navigate(view) {
        window.location.hash = view;
    },

    /** Public — return the currently active view name. */
    getCurrentView() {
        return this.currentView;
    },
};

document.addEventListener("DOMContentLoaded", () => App.init());
