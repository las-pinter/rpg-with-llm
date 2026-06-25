/**
 * Shared utilities for restoring narrative entries from save/load data.
 * Both GamePage.handleLoaded() and characterStore.loadSaveGame() use this
 * to avoid duplicating the extraction logic.
 */

export interface RawNarrativeEntry {
  type: string
  content: string
}

/**
 * Extract narrative entries from a world-state object using a priority chain:
 *
 *   1. `_narrative_entries` — rich array of { type, content } objects
 *   2. `story_summary` — legacy flat array of strings (each treated as 'narrative')
 *   3. `story_log` + `user_input_history` — legacy merge (story_log → 'narrative',
 *      user_input_history → 'player')
 *
 * Returns an empty array when none of the sources exist or are valid arrays.
 */
export function extractNarrativeEntries(
  state: Record<string, unknown>,
): RawNarrativeEntry[] {
  // Priority 1: Rich narrative entries (player + narrative, full conversation)
  const richEntries = state._narrative_entries as
    | Array<{ type: string; content: string }>
    | undefined

  if (richEntries && Array.isArray(richEntries) && richEntries.length > 0) {
    return richEntries.map((e) => ({
      type: e.type || 'narrative',
      content: e.content,
    }))
  }

  // Priority 2: Legacy story_summary array
  const storySummary = state.story_summary as string[] | undefined
  if (storySummary && Array.isArray(storySummary) && storySummary.length > 0) {
    return storySummary.map((content) => ({
      type: 'narrative',
      content,
    }))
  }

  // Priority 3: Merge story_log and user_input_history
  const entries: RawNarrativeEntry[] = []
  const storyLog = state.story_log as string[] | undefined
  if (storyLog && Array.isArray(storyLog)) {
    for (const entry of storyLog) {
      entries.push({ type: 'narrative', content: entry })
    }
  }
  const userInputHistory = state.user_input_history as string[] | undefined
  if (userInputHistory && Array.isArray(userInputHistory)) {
    for (const input of userInputHistory) {
      entries.push({ type: 'player', content: input })
    }
  }
  return entries
}
