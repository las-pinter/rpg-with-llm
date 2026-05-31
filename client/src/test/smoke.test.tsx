import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

describe('Vitest setup', () => {
  it('renders a test element', () => {
    render(<div data-testid="smoke">Hello Vitest</div>)
    expect(screen.getByTestId('smoke')).toHaveTextContent('Hello Vitest')
  })
})
