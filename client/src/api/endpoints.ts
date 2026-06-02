/** Typed API endpoint functions for all game routes. */

import { get, post, del } from './client'
import type {
  HealthResponse,
  ModelsResponse,
  CharacterResponse,
  CharactersListResponse,
  CharacterRulesResponse,
  SettingsResponse,
  SaveResponse,
  SavesListResponse,
  LoadResponse,
  StoryResponse,
  ResetResponse,
  SuccessResponse,
} from './types'

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthCheckParams {
  base_url: string
  model: string
  api_key?: string
  provider_type?: string
}

export function checkHealth(
  params: HealthCheckParams,
  signal?: AbortSignal,
): Promise<HealthResponse> {
  return post<HealthResponse>('/api/health', params, signal)
}

export interface ListModelsParams {
  base_url: string
  model: string
  api_key?: string
  provider_type?: string
}

export function listModels(params: ListModelsParams): Promise<ModelsResponse> {
  return post<ModelsResponse>('/api/models', params)
}

// ---------------------------------------------------------------------------
// Character
// ---------------------------------------------------------------------------

export interface GenerateCharacterParams {
  answers: Record<number, string>
  abilities?: Record<string, number>
  character_class?: string
  name?: string
  provider?: {
    base_url: string
    model: string
    api_key?: string
    /** Backend defaults to 'ollama' if omitted. */
    provider_type?: string
  }
}

export function generateCharacter(
  params: GenerateCharacterParams,
): Promise<CharacterResponse> {
  return post<CharacterResponse>('/api/character/generate', params)
}

export interface CreateCharacterParams {
  name: string
  character_class: string
  abilities: Record<string, number>
  backstory?: string
  appearance?: string
  personality?: string
  ideals?: string
  bonds?: string
  flaws?: string
  inventory?: string[]
  gold?: number
  hp?: number
}

export function createCharacter(
  params: CreateCharacterParams,
): Promise<CharacterResponse> {
  return post<CharacterResponse>('/api/character/create', params)
}

export function listCharacters(): Promise<CharactersListResponse> {
  return get<CharactersListResponse>('/api/characters')
}

export function loadCharacter(name: string): Promise<CharacterResponse> {
  return get<CharacterResponse>(`/api/character/load/${encodeURIComponent(name)}`)
}

export function deleteCharacter(name: string): Promise<SuccessResponse> {
  return del<SuccessResponse>(`/api/character/delete/${encodeURIComponent(name)}`)
}

export function loadCharacterById(charId: string): Promise<CharacterResponse> {
  return get<CharacterResponse>(`/api/character/id/${encodeURIComponent(charId)}`)
}

export function deleteCharacterById(charId: string): Promise<SuccessResponse> {
  return del<SuccessResponse>(`/api/character/id/${encodeURIComponent(charId)}`)
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export function getCharacterRules(): Promise<CharacterRulesResponse> {
  return get<CharacterRulesResponse>('/api/config/character-rules')
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export function getSettings(): Promise<SettingsResponse> {
  return get<SettingsResponse>('/api/settings')
}

export function saveSettings(
  settings: Record<string, unknown>,
): Promise<SettingsResponse> {
  return post<SettingsResponse>('/api/settings', settings)
}

// ---------------------------------------------------------------------------
// Save / Load
// ---------------------------------------------------------------------------

export interface SaveGameParams {
  state: Record<string, unknown>
  character?: Record<string, unknown>
  name?: string
}

export function saveGame(params: SaveGameParams): Promise<SaveResponse> {
  return post<SaveResponse>('/api/save', params)
}

export function listSaves(): Promise<SavesListResponse> {
  return get<SavesListResponse>('/api/saves')
}

export function loadGame(slug: string): Promise<LoadResponse> {
  return post<LoadResponse>(`/api/load/${encodeURIComponent(slug)}`)
}

export function deleteSave(slug: string): Promise<SuccessResponse> {
  return del<SuccessResponse>(`/api/delete/${encodeURIComponent(slug)}`)
}

export function getStory(slug: string): Promise<StoryResponse> {
  return get<StoryResponse>(`/api/story/${encodeURIComponent(slug)}`)
}

export function resetGame(): Promise<ResetResponse> {
  return post<ResetResponse>('/api/reset')
}

// ---------------------------------------------------------------------------
// Game / Stream
// ---------------------------------------------------------------------------

export interface GameStreamParams {
  input: string
  character_id: string
  provider?: {
    base_url: string
    model: string
    api_key?: string
    provider_type?: string
  }
}

/**
 * Start an SSE game stream.
 *
 * Note: This endpoint uses Server-Sent Events. The response is a stream,
 * not a standard JSON payload. Use EventSource or fetch with
 * `response.body.getReader()` to consume the stream.
 */
export function startGameStream(params: GameStreamParams): string {
  const searchParams = new URLSearchParams()
  searchParams.set('input', params.input)
  searchParams.set('character_id', params.character_id)
  if (params.provider) {
    searchParams.set('provider', JSON.stringify(params.provider))
  }
  return `/api/game/stream?${searchParams.toString()}`
}
