/**
 * LLM-Powered RPG — Shared UI Utilities
 *
 * Global helper functions used across multiple views.
 * Loaded via <script> tag before other JS files.
 */

/** Escape HTML special chars (simple XSS guard). */
function _esc(str) {
    if (typeof str !== "string") return String(str || "");
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

/** Format a YYYYMMDD_HHMMSS[_ffffff] timestamp for display. */
function _formatTimestamp(ts) {
    const match = ts.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(?:_\d+)?$/);
    if (!match) return ts;
    const date = new Date(+match[1], +match[2] - 1, +match[3], +match[4], +match[5], +match[6]);
    return date.toLocaleString();
}

/** POST JSON body to a URL, parse the JSON response, and check for ok flag. */
async function _postJSON(url, body) {
    const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!data.ok) throw new Error(data.error || "Request failed");
    return data;
}

/** Show a modal and optional overlay by removing the "hidden" class. */
function _showModal(modal, overlay) {
    modal.classList.remove("hidden");
    if (overlay) overlay.classList.remove("hidden");
}

/** Hide a modal and optional overlay by adding the "hidden" class. */
function _hideModal(modal, overlay) {
    modal.classList.add("hidden");
    if (overlay) overlay.classList.add("hidden");
}
