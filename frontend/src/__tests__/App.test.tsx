import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import App from '../App'
import { useMixerStore } from '../store/mixer'

const CHANNEL_NAMES = [
  'coro1',
  'piano',
  'guitar',
  'voz 1',
  'voz 2',
  'bajo',
  'batería',
  'FX 1',
]

describe('App', () => {
  beforeEach(() => {
    useMixerStore.getState().reset()
  })

  it('pinta la cabecera, los ocho canales y la versión', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { level: 1, name: 'Qu-16 Control' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Desconectado')
    expect(screen.getAllByRole('listitem')).toHaveLength(8)
    expect(screen.getByText('v0.1.0')).toBeInTheDocument()

    for (const name of CHANNEL_NAMES) {
      expect(
        screen.getByRole('heading', { level: 3, name }),
      ).toBeInTheDocument()
    }
  })

  it('actualiza el store al mover un fader y al pulsar Mute', () => {
    render(<App />)

    fireEvent.change(screen.getByLabelText('Fader de piano'), {
      target: { value: '0' },
    })
    expect(useMixerStore.getState().channels[1]?.faderDb).toBe(0)

    fireEvent.click(screen.getByLabelText('Silenciar canal piano'))
    expect(useMixerStore.getState().channels[1]?.muted).toBe(true)
    expect(
      screen.getByLabelText('Activar canal piano'),
    ).toHaveAttribute('aria-pressed', 'true')
  })
})
