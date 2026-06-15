/**
 * CampfireMode — story-driven character creation flow.
 *
 * Orchestrates the "campfire" narrative creation: user answers story
 * questions one at a time with Prev/Next navigation, adjusts ability
 * scores and class, then hits Generate to let the LLM weave a character
 * from the answers. On success, sets generatedCharacter in store and
 * switches creationMode to 'review' so the parent page can show the
 * review screen.
 */

import { useState, useCallback, useMemo } from 'react'
import { useCharacterStore } from '../../stores/characterStore'
import { useConnectionStore } from '../../stores/connectionStore'
import { generateCharacter } from '../../api/endpoints'
import type { GenerateCharacterParams } from '../../api/endpoints'
import StoryProgress from './StoryProgress'
import StoryQuestion from './StoryQuestion'
import AbilityGrid from './AbilityGrid'
import ClassSelector from './ClassSelector'
import styles from './CampfireMode.module.css'

export default function CampfireMode() {
  // ------------------------------------------------------------------
  // Character store reads
  // ------------------------------------------------------------------
  const currentQuestion = useCharacterStore((s) => s.currentQuestion)
  const storyAnswers = useCharacterStore((s) => s.storyAnswers)
  const rules = useCharacterStore((s) => s.rules)
  const abilities = useCharacterStore((s) => s.abilities)
  const selectedClass = useCharacterStore((s) => s.selectedClass)
  const saveCurrentAnswer = useCharacterStore((s) => s.saveCurrentAnswer)
  const nextQuestion = useCharacterStore((s) => s.nextQuestion)
  const prevQuestion = useCharacterStore((s) => s.prevQuestion)
  const setGeneratedCharacter = useCharacterStore((s) => s.setGeneratedCharacter)
  const setCreationMode = useCharacterStore((s) => s.setCreationMode)

  // ------------------------------------------------------------------
  // Connection store reads (for LLM provider settings)
  // ------------------------------------------------------------------
  const connBaseUrl = useConnectionStore((s) => s.baseUrl)
  const connModel = useConnectionStore((s) => s.model)
  const connProviderType = useConnectionStore((s) => s.providerType)
  const connApiKey = useConnectionStore((s) => s.apiKey)

  // ------------------------------------------------------------------
  // Local state
  // ------------------------------------------------------------------
  const [charName, setCharName] = useState('')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ------------------------------------------------------------------
  // Derived values
  // ------------------------------------------------------------------
  const questions = rules?.assisted_creation_questions ?? []
  const totalQuestions = questions.length
  const isLastQuestion = currentQuestion === totalQuestions - 1
  const currentQuestionText = questions[currentQuestion] ?? ''
  const hasConnection =
    connBaseUrl.length > 0 && connModel.length > 0 && connProviderType.length > 0

  const filledCount = useMemo(
    () => storyAnswers.filter((a) => a && a.trim().length > 0).length,
    [storyAnswers],
  )

  // Grab the textarea value for the current question so we can save it
  // before navigating.
  const currentAnswer = storyAnswers[currentQuestion] ?? ''

  // ------------------------------------------------------------------
  // Navigation handlers
  // ------------------------------------------------------------------

  const handlePrev = useCallback(() => {
    setError(null)
    prevQuestion()
  }, [prevQuestion])

  const handleNext = useCallback(() => {
    setError(null)
    nextQuestion()
  }, [nextQuestion])

  // ------------------------------------------------------------------
  // Generate handler
  // ------------------------------------------------------------------

  const handleGenerate = useCallback(async () => {
    setError(null)

    // Save the current answer before submitting
    saveCurrentAnswer(currentAnswer, currentQuestion)

    // Validate at least 3 answers are filled
    if (filledCount < 3) {
      setError(
        'Answer at least 3 questions so the Dungeon Master has enough ' +
          'to weave your story.',
      )
      return
    }

    // Validate connection settings
    if (!hasConnection) {
      setError(
        'No LLM provider configured! Go to the Connection screen ' +
          'and set up a provider first.',
      )
      return
    }

    setGenerating(true)

    // Build the answers object (index → answer string)
    const answersObj: Record<number, string> = {}
    storyAnswers.forEach((answer, idx) => {
      if (answer && answer.trim().length > 0) {
        answersObj[idx] = answer
      }
    })

    // Build the provider config from connection store.
    // The backend accepts base_url, model, api_key, and provider_type.
    const provider: GenerateCharacterParams['provider'] = {
      base_url: connBaseUrl,
      model: connModel,
    }
    if (connProviderType) {
      provider.provider_type = connProviderType
    }
    if (connApiKey) {
      provider.api_key = connApiKey
    }

    const params: GenerateCharacterParams = {
      answers: answersObj,
      character_class: selectedClass || undefined,
      provider,
    }

    // Only send abilities if they differ from defaults
    if (Object.keys(abilities).length > 0) {
      params.abilities = abilities
    }

    // Only send name if user entered one
    const trimmedName = charName.trim()
    if (trimmedName) {
      params.name = trimmedName
    }

    try {
      const response = await generateCharacter(params)
      if (response.ok) {
        setGeneratedCharacter(response.character)
        setCreationMode('review')
      } else {
        setError('Failed to generate character — unexpected response.')
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Unknown error generating character.'
      setError(message)
    } finally {
      setGenerating(false)
    }
  }, [
    currentAnswer,
    currentQuestion,
    saveCurrentAnswer,
    filledCount,
    hasConnection,
    storyAnswers,
    connBaseUrl,
    connModel,
    connProviderType,
    connApiKey,
    selectedClass,
    abilities,
    charName,
    setGeneratedCharacter,
    setCreationMode,
  ])

  // ------------------------------------------------------------------
  // Nothing to render if there are no questions
  // ------------------------------------------------------------------

  if (totalQuestions === 0) {
    return (
      <div className={styles.wrapper}>
        <p className={styles.emptyState}>
          No character creation questions loaded. Check your connection
          and try again.
        </p>
      </div>
    )
  }

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div className={styles.wrapper}>
      {/* ---- Story Progress ---- */}
      <StoryProgress />

      {/* ---- Answers filled indicator ---- */}
      <p className={styles.filledIndicator}>
        {filledCount} of {totalQuestions} questions answered
      </p>

      {/* ---- Character Name ---- */}
      <div className={styles.nameRow}>
        <label className={styles.nameLabel} htmlFor="campfire-name">
          Hero&rsquo;s Name
        </label>
        <input
          id="campfire-name"
          className={styles.nameInput}
          type="text"
          value={charName}
          onChange={(e) => setCharName(e.target.value)}
          placeholder="Leave blank for a surprise…"
        />
      </div>

      {/* ---- Current Story Question ---- */}
      <div className={styles.questionArea}>
        <StoryQuestion
          key={currentQuestion}
          question={currentQuestionText}
          questionIndex={currentQuestion}
        />
      </div>

      {/* ---- Navigation ---- */}
      <nav className={styles.nav} aria-label="Story question navigation">
        <button
          type="button"
          className={styles.navBtn}
          onClick={handlePrev}
          disabled={currentQuestion === 0 || generating}
          aria-label="Previous question"
        >
          &larr; Previous
        </button>

        {isLastQuestion ? (
          <button
            type="button"
            className={`${styles.navBtn} ${styles.generateBtn}`}
            onClick={handleGenerate}
            disabled={generating}
            aria-label="Generate character from story"
          >
            {generating ? (
              <>
                <span className={styles.spinner} aria-hidden="true" />
                Weaving&hellip;
              </>
            ) : (
              <>&#x2728; Weave My Story</>
            )}
          </button>
        ) : (
          <button
            type="button"
            className={styles.navBtn}
            onClick={handleNext}
            disabled={generating}
            aria-label="Next question"
          >
            Next &rarr;
          </button>
        )}
      </nav>

      {/* ---- Error ---- */}
      {error && (
        <div className={styles.errorBanner} role="alert">
          <span className={styles.errorIcon} aria-hidden="true">&#x26A0;&#xFE0F;</span>
          <span>{error}</span>
        </div>
      )}

      {/* ---- Loading overlay when generating ---- */}
      {generating && (
        <div className={styles.loadingOverlay} role="status">
          <div className={styles.loadingContent}>
            <span className={styles.largeSpinner} aria-hidden="true" />
            <p className={styles.loadingText}>
              The Dungeon Master is weaving your story&hellip;
            </p>
          </div>
        </div>
      )}

      {/* ---- Divider ---- */}
      <hr className={styles.divider} />

      {/* ---- Class & Ability Scores ---- */}
      <div className={styles.buildSection}>
        <div className={`${styles.section} ${styles.classSection}`}>
          <ClassSelector />
        </div>
        <AbilityGrid />
      </div>
    </div>
  )
}
