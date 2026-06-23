/** Shared API response types for the LLM-Powered RPG. */

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  ok: boolean
  latency_ms: number
  model: string
  error: string | null
}

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

export interface ModelInfo {
  id: string
  name: string
}

export interface ModelsResponse {
  ok: boolean
  models: ModelInfo[]
  error?: string
}

// ---------------------------------------------------------------------------
// Character
// ---------------------------------------------------------------------------

export interface AbilityScores {
  [ability: string]: number
}

/** Item types matching backend ItemTypeEnum. */
export enum ItemType {
  WEAPON = "WEAPON",
  ARMOR = "ARMOR",
  CONSUMABLE = "CONSUMABLE",
  TOOL = "TOOL",
  CONTAINER = "CONTAINER",
  QUEST = "QUEST",
  MISC = "MISC",
}

/** An item in a character's inventory. */
export interface Item {
  id: string
  name: string
  quantity: number
  item_type: ItemType
  properties: Record<string, unknown>
  description: string
  weight: number
  value: number
}

/** A resource (e.g. HP, mana) with recovery rules. */
export interface ResourceData {
  value: number
  max: number | string
  short_rest_recovery: string
  long_rest_recovery: string
}

/** Computed character statistics — never persisted, always derived from a CharacterRecord. */
export interface DerivedSheet {
  ability_modifiers: Record<string, number>
  proficiency_bonus: number
  ac: number
  initiative: number
  speed: number
  skill_modifiers: Record<string, number>
  saving_throw_modifiers: Record<string, number>
  passive_perception: number
  attack_bonus: Record<string, number>
  encumbrance: Record<string, unknown>
  hit_dice: string
  resistances: string[]
  vulnerabilities: string[]
  formulas: Record<string, string>
}

export interface Character {
  id?: string
  name: string
  character_class: string
  level: number
  abilities: AbilityScores
  skills: string[]
  backstory: string
  appearance: string
  personality: string
  hooks: string[]
  inventory: Item[]
  equipped_items: string[]
  resources: Record<string, ResourceData>
  gold: number
  xp: number
  created_at: string
}

export interface CharacterResponse {
  ok: boolean
  character: Character
}

export interface SheetResponse {
  ok: boolean
  sheet: DerivedSheet
}

/** Item in the saved characters list (metadata only, not full character). */
export interface CharacterListItem {
  id: string
  name: string
  class: string
  level: number
  timestamp: string
}

export interface CharactersListResponse {
  ok: boolean
  characters: CharacterListItem[]
}

export interface CharacterRulesResponse {
  ok: boolean
  rules: CharacterRules
}

export interface ClassTemplate {
  abilities: Record<string, number>
  hp?: number
  ac?: number
  skills?: string[]
  inventory?: string[]
  gold?: number
}

export interface CharacterRules {
  valid_classes: string[]
  standard_abilities: string[]
  class_templates: Record<string, ClassTemplate>
  point_buy: {
    costs: Record<string, number>
    max_points: number
    min_score: number
    max_score: number
  }
  assisted_creation_questions: string[]
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export interface Settings {
  dm_max_tokens: number
  dm_temperature: number
  dm_timeout: number
  npc_max_tokens: number
  npc_temperature: number
  npc_timeout: number
  summarizer_max_tokens: number
  summarizer_temperature: number
  summarizer_timeout: number
  base_url: string
  model: string
  provider_type: string
  api_key: string | null
  timeout: number
  max_tokens: number | null
  temperature: number | null
}

export interface SettingsResponse {
  ok: boolean
  settings: Settings
}

// ---------------------------------------------------------------------------
// Save / Load
// ---------------------------------------------------------------------------

export interface SaveMeta {
  id: string
  name: string
  timestamp: string
  character_name?: string
  turn_count?: number
}

export interface SaveResponse {
  ok: boolean
  slug: string
}

export interface SavesListResponse {
  ok: boolean
  saves: SaveMeta[]
}

export interface LoadResponse {
  ok: boolean
  state: Record<string, unknown>
  character?: Record<string, unknown>
}

export interface StoryResponse {
  ok: boolean
  story: Array<{type: string; content: string}>
}

export interface ResetResponse {
  ok: boolean
  state: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Game / Stream
// ---------------------------------------------------------------------------

export interface GameStreamResponse {
  ok: boolean
  turn?: string
  narrative?: string
  state?: Record<string, unknown>
  error?: string
}

// ---------------------------------------------------------------------------
// Consult
// ---------------------------------------------------------------------------

export interface ConsultParams {
  input: string
  character?: Record<string, unknown>
  state?: Record<string, unknown>
  provider?: Record<string, unknown>
  save_slug?: string
}

export interface ConsultResponse {
  ok: boolean
  answer: string
}

// ---------------------------------------------------------------------------
// Common
// ---------------------------------------------------------------------------

export interface SuccessResponse {
  ok: true
}

export interface ErrorResponse {
  ok: false
  error: string
  errors?: Record<string, string>
}
