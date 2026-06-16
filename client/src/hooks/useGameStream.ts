/**
 * Hook to connect to the SSE game stream, parse events, and dispatch
 * them to the game store.
 *
 * Uses POST + JSON body (not query params) to avoid HTTP 414 errors
 * when the story log grows large. Reads the SSE response via
 * ReadableStream with manual chunk buffering and event parsing.
 */

import { useRef, useCallback, useEffect, useState } from 'react'
import { useGameStore } from '../stores/gameStore'

const STREAM_URL = '/api/game/stream'
const MAX_RETRIES = 3

export interface UseGameStreamOptions {
  input: string
  character?: Record<string, unknown>
  state?: Record<string, unknown>
  provider?: Record<string, unknown>
  npcProvider?: Record<string, unknown>
  summarizerProvider?: Record<string, unknown>
}

export interface UseGameStreamReturn {
  connect: (options: UseGameStreamOptions) => void
  disconnect: () => void
  isConnecting: boolean
  error: string | null
}

export function useGameStream(): UseGameStreamReturn {
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setLocalError] = useState<string | null>(null)

  const controllerRef = useRef<AbortController | null>(null)
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null)
  const bufferRef = useRef('')
  const decoderRef = useRef(new TextDecoder())
  const cancelledRef = useRef(false)
  const fetchedRef = useRef(false)
  // Ref for disconnect so processStreamEvent always calls the latest version,
  // avoiding stale closure issues if disconnect's deps ever change.
  const disconnectRef = useRef<() => void>(() => {})

  const disconnect = useCallback(() => {
    cancelledRef.current = true
    bufferRef.current = ''
    setIsConnecting(false)

    if (readerRef.current) {
      readerRef.current.cancel().catch(() => {})
      readerRef.current = null
    }
    if (controllerRef.current) {
      controllerRef.current.abort()
      controllerRef.current = null
    }
  }, [])

  // Keep ref in sync so inner closures always call the current disconnect
  disconnectRef.current = disconnect

  // Cleanup on unmount — always disconnect
  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  const connect = useCallback(
    (options: UseGameStreamOptions) => {
      // Strict Mode guard — prevents double-connect when effects fire twice
      if (fetchedRef.current) return
      fetchedRef.current = true

      // Clean up any existing connection first
      disconnect()

      cancelledRef.current = false
      setIsConnecting(true)
      setLocalError(null)

      const controller = new AbortController()
      controllerRef.current = controller

      const body: Record<string, unknown> = { input: options.input }
      if (options.provider) body.provider = options.provider
      if (options.state) body.state = options.state
      if (options.character) body.character = options.character
      if (options.npcProvider) body.npc_provider = options.npcProvider
      if (options.summarizerProvider) {
        body.summarizer_provider = options.summarizerProvider
      }

      /** Parse a single SSE block and dispatch to the game store. */
      const processStreamEvent = (type: string, data: unknown) => {
        if (data === null || typeof data !== 'object') return
        const s = useGameStore.getState()

        switch (type) {
          case 'token': {
            const content = (data as { content?: string }).content
            if (content) {
              s.setStreamingText(s.streamingText + content)
            }
            break
          }
          case 'narrative': {
            const content = (data as { content?: string }).content
            if (content) {
              s.addNarrativeEntry({ type: 'narrative', content })
              s.setNarrative(s.narrative + content)
            }
            break
          }
          case 'npc_thinking': {
            const d = data as { npc_id?: string; hint?: string }
            s.setNpcThinking(d.npc_id ?? null, d.hint ?? '')
            break
          }
          case 'state_update': {
            const stateData = data as Record<string, unknown>
            if (stateData.state && typeof stateData.state === 'object') {
              s.setWorldState(stateData.state as Record<string, unknown>)
            }
            break
          }
          case 'done': {
            s.incrementTurnCount()
            s.setProcessing(false)
            s.setIsThinking(false)
            s.setStreamingText('')
            s.addNarrativeEntry({ type: 'separator', content: '---' })
            disconnectRef.current()
            break
          }
          case 'token_usage': {
            const d = data as {
              usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
              latest?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
            }
            const update: {
              total?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
              latest?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
            } = {}
            if (d.usage) update.total = d.usage
            if (d.latest) update.latest = d.latest
            s.setTokenUsage(update)
            break
          }
          case 'error': {
            const d = data as { message?: string }
            s.setError(d.message ?? 'Server error')
            disconnectRef.current()
            break
          }
        }
      }

      async function attempt(): Promise<void> {
        let retries = 0
        try {
          while (retries <= MAX_RETRIES) {
            try {
              const response = await fetch(STREAM_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal: controller.signal,
              })

              if (!response.ok) {
                throw new Error(`HTTP ${response.status}`)
              }

              if (cancelledRef.current) return

              if (!response.body) {
                throw new Error('Response body is null or undefined')
              }
              const reader = response.body.getReader()
              readerRef.current = reader
              retries = 0
              setIsConnecting(false)

              // Stream connected — activate game UI and show thinking indicator
              const gs = useGameStore.getState()
              gs.setIsActive(true)
              gs.setIsThinking(true)
              gs.setProcessing(true)

              // Read the SSE stream chunk by chunk
              while (true) {
                if (cancelledRef.current) {
                  reader.cancel()
                  return
                }
                const { done, value } = await reader.read()
                if (done) break

                // Accumulate raw bytes in a buffer, decoding as we go
                bufferRef.current += decoderRef.current.decode(value, {
                  stream: true,
                })

                // Process all complete SSE blocks (delimited by \n\n)
                let lineBreak = bufferRef.current.indexOf('\n\n')
                while (lineBreak !== -1) {
                  const block = bufferRef.current.slice(0, lineBreak)
                  bufferRef.current = bufferRef.current.slice(lineBreak + 2)

                  let eventType = ''
                  let eventData = ''
                  const lines = block.split('\n')
                  for (const line of lines) {
                    if (line.startsWith('event: ')) {
                      eventType = line.slice(7).trim()
                    } else if (line.startsWith('data: ')) {
                      // SSE spec: multiple data: lines joined with \n
                      eventData += (eventData ? '\n' : '') + line.slice(6)
                    }
                  }

                  if (eventType && eventData) {
                    try {
                      const parsed = JSON.parse(eventData)
                      processStreamEvent(eventType, parsed)
                    } catch {
                      // Malformed JSON — skip
                    }
                  }

                  lineBreak = bufferRef.current.indexOf('\n\n')
                }
              }
              // Stream ended normally — success, exit attempt
              return
            } catch (err) {
              if (cancelledRef.current) return
              if (err instanceof DOMException && err.name === 'AbortError') {
                return
              }

              // Exponential backoff retry
              if (retries < MAX_RETRIES) {
                retries++
                const delay = Math.pow(2, retries - 1) * 1000
                await new Promise((r) => setTimeout(r, delay))
                if (cancelledRef.current) return
                // Loop again to retry
              } else {
                const message = err instanceof Error ? err.message : 'Connection failed'
                setLocalError(message)
                setIsConnecting(false)
                return
              }
            }
          }
        } finally {
          if (!cancelledRef.current) {
            disconnect()
          }
          fetchedRef.current = false
        }
      }

      attempt()
    },
    [disconnect],
  )

  return { connect, disconnect, isConnecting, error }
}
