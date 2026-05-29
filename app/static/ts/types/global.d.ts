/**
 * LLM-Powered RPG — Global Type Definitions
 *
 * Shared types used across all frontend TS files.
 * Declared at global scope (no import/export) so they're available
 * in all script-loaded TypeScript files without explicit imports.
 */

// ---------------------------------------------------------------------------
// Provider Configuration
// ---------------------------------------------------------------------------

interface ProviderConfig {
    base_url: string;
    model: string;
    api_key?: string;
    provider?: string;
    max_tokens?: number;
    temperature?: number;
    timeout?: number;
}

// ---------------------------------------------------------------------------
// Character & World Data
// ---------------------------------------------------------------------------

interface CharacterData {
    id?: string;
    name?: string;
    character_class?: string;
    level?: number;
    appearance?: string;
    backstory?: string;
    hp?: number;
    max_hp?: number;
    abilities?: Record<string, number>;
    inventory?: string[];
    gold?: number;
    [key: string]: unknown;
}

interface WorldState {
    current_location?: string;
    turn_count?: number;
    gold?: number;
    inventory?: string[];
    active_npcs?: Record<string, { name?: string; last_seen_turn?: number }>;
    locations?: Record<string, unknown>;
    quests?: Record<string, unknown>;
    faction_standings?: Record<string, unknown>;
    dm_notes?: Record<string, unknown>;
    character_name?: string;
    character_id?: string;
    story_log?: string[];
    [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Token Usage
// ---------------------------------------------------------------------------

interface TokenCounts {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
}

interface TokenUsageData {
    usage?: TokenCounts;
    latest?: TokenCounts;
}

// ---------------------------------------------------------------------------
// SSE Client
// ---------------------------------------------------------------------------

interface SSECallbacks {
    onToken?: (content: string) => void;
    onNarrative?: (content: string) => void;
    onNpcThinking?: (data: { npc_id?: string; hint?: string }) => void;
    onStateUpdate?: (data: { state?: WorldState; turn_count?: number }) => void;
    onDone?: (turnCount: number) => void;
    onTokenUsage?: (data: TokenUsageData) => void;
    onError?: (message: string) => void;
}

// ---------------------------------------------------------------------------
// Character Creation Rules (from /api/config/character-rules)
// ---------------------------------------------------------------------------

interface CharacterRules {
    valid_classes: string[];
    class_templates: Record<string, { abilities: Record<string, number> }>;
    standard_abilities: Record<string, number>;
    point_buy: { max_points: number };
    assisted_creation_questions: string[];
}

// ---------------------------------------------------------------------------
// App State & Instance
// ---------------------------------------------------------------------------

interface AppState {
    provider: ProviderConfig | null;
    character: CharacterData | null;
    loadSaveName: string | null;
    npcProvider?: ProviderConfig | null;
    summarizerProvider?: ProviderConfig | null;
}

interface AppInstance {
    currentView: string | null;
    state: AppState;
    init(): void;
    _handleRoute(): void;
    _showView(viewId: string): void;
    navigate(view: string): void;
    getCurrentView(): string | null;
}

// ---------------------------------------------------------------------------
// DOM Element Maps
// ---------------------------------------------------------------------------

interface CharacterElements {
    tabBar: HTMLElement | null;
    tabCreate: HTMLElement | null;
    tabLoad: HTMLElement | null;
    campfireTab: HTMLElement | null;
    manualTab: HTMLElement | null;
    campfireContent: HTMLElement | null;
    manualContent: HTMLElement | null;
    charName: HTMLElement | null;
    charClass: HTMLSelectElement | null;
    nameManual: HTMLInputElement | null;
    classManual: HTMLSelectElement | null;
    appearance: HTMLTextAreaElement | null;
    backstory: HTMLTextAreaElement | null;
    manualCreateBtn: HTMLElement | null;
    validationMsg: HTMLElement | null;
    remainingSpan: HTMLElement | null;
    campRemainingSpan: HTMLElement | null;
    skillsDisplay: HTMLElement | null;
    storyQuestions: HTMLElement | null;
    storyProgressFill: HTMLElement | null;
    storyChapterNum: HTMLElement | null;
    storyChapterTotal: HTMLElement | null;
    storyStepDots: HTMLElement | null;
    storyPrevBtn: HTMLElement | null;
    storyNextBtn: HTMLElement | null;
    storyGenerateBtn: HTMLElement | null;
    reviewSection: HTMLElement | null;
    reviewCharacterSheet: HTMLElement | null;
    reviewLoading: HTMLElement | null;
    reviewEditBtn: HTMLElement | null;
    reviewRegenerateBtn: HTMLElement | null;
    reviewStartBtn: HTMLElement | null;
    characterList: HTMLElement | null;
    savedGamesList: HTMLElement | null;
}

interface GameElements {
    container: HTMLElement | null;
    narrativeContent: HTMLElement | null;
    narrativePane: HTMLElement | null;
    thinkingIndicator: HTMLElement | null;
    npcThinkingIndicator: HTMLElement | null;
    npcThinkingText: HTMLElement | null;
    sidebarName: HTMLElement | null;
    sidebarClassLevel: HTMLElement | null;
    charAppearance: HTMLElement | null;
    charBackstory: HTMLElement | null;
    hpFill: HTMLElement | null;
    hpText: HTMLElement | null;
    statsList: HTMLElement | null;
    goldDisplay: HTMLElement | null;
    goldAmount: HTMLElement | null;
    inventoryList: HTMLElement | null;
    locationText: HTMLElement | null;
    npcList: HTMLElement | null;
    collapseBtn: HTMLElement | null;
    tokenToggle: HTMLElement | null;
    tokenDisplay: HTMLElement | null;
    tokenPrompt: HTMLElement | null;
    tokenCompletion: HTMLElement | null;
    tokenTotal: HTMLElement | null;
    tokenLatestPrompt: HTMLElement | null;
    tokenLatestCompletion: HTMLElement | null;
    tokenLatestTotal: HTMLElement | null;
    playerInput: HTMLInputElement | null;
    submitBtn: HTMLElement | null;
    quickActions: HTMLElement | null;
    newGameBtn: HTMLElement | null;
    saveGameBtn: HTMLElement | null;
    loadGameBtn: HTMLElement | null;
    saveModal: HTMLElement | null;
    saveModalOverlay: HTMLElement | null;
    saveNameInput: HTMLInputElement | null;
    saveConfirmBtn: HTMLElement | null;
    saveCancelBtn: HTMLElement | null;
    saveStatus: HTMLElement | null;
}

interface ConnectionElements {
    providerSelect: HTMLSelectElement | null;
    baseUrl: HTMLInputElement | null;
    apiKey: HTMLInputElement | null;
    apiKeyGroup: HTMLElement | null;
    modelSelect: HTMLSelectElement | null;
    modelInput: HTMLInputElement | null;
    fetchModels: HTMLElement | null;
    testBtn: HTMLElement | null;
    status: HTMLElement | null;
    statusDot: Element | null;
    statusText: Element | null;
    startBtn: HTMLElement | null;
    advancedToggle: HTMLElement | null;
    advancedSection: HTMLElement | null;
    npcProviderSelect: HTMLSelectElement | null;
    npcBaseUrl: HTMLInputElement | null;
    npcApiKey: HTMLInputElement | null;
    npcApiKeyGroup: HTMLElement | null;
    npcModelInput: HTMLInputElement | null;
    summarizerProviderSelect: HTMLSelectElement | null;
    summarizerBaseUrl: HTMLInputElement | null;
    summarizerApiKey: HTMLInputElement | null;
    summarizerApiKeyGroup: HTMLElement | null;
    summarizerModelInput: HTMLInputElement | null;
    npcEnabled: HTMLInputElement | null;
    npcConfigGroup: HTMLElement | null;
    summarizerEnabled: HTMLInputElement | null;
    summarizerConfigGroup: HTMLElement | null;
    dmMaxTokens: HTMLInputElement | null;
    dmTemperature: HTMLInputElement | null;
    dmTimeout: HTMLInputElement | null;
    npcMaxTokens: HTMLInputElement | null;
    npcTemperature: HTMLInputElement | null;
    npcTimeout: HTMLInputElement | null;
    summarizerMaxTokens: HTMLInputElement | null;
    summarizerTemperature: HTMLInputElement | null;
    summarizerTimeout: HTMLInputElement | null;
}

// ---------------------------------------------------------------------------
// Game View State
// ---------------------------------------------------------------------------

interface GameState {
    worldState: WorldState | null;
    turnCount: number;
    isThinking: boolean;
    hasStarted: boolean;
    autoScroll: boolean;
    tokenUsage: TokenCounts;
    latestTokenUsage: TokenCounts;
    showTokens: boolean;
}

// ---------------------------------------------------------------------------
// SPA View helpers
// ---------------------------------------------------------------------------

interface SPAView {
    els: Record<string, HTMLElement | null>;
    init(): void;
    [key: string]: unknown;
}
