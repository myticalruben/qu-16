import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import App from '../App'
import type { MixerStatePayload } from '../store/mixer'
import { useMixerStore } from '../store/mixer'

const SNAPSHOT: MixerStatePayload = {
  connected: true,
  model: 'QU-16',
  firmware: '1.97',
  updated_at: '2026-11-12T01:10:00+00:00',
  channels: [
    { index: 1, name: 'coro1', level_db: 4.9, kind: 'input' },
    { index: 3, name: 'coro2', level_db: null, kind: 'input' },
  ],
}

describe('App', () => {
  beforeEach(() => {
    useMixerStore.getState().reset()
  })

  it('pinta la cabecera, el estado vacío y la versión', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { level: 1, name: 'Qu-16 Control' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Desconectado')
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    expect(screen.getByText(/Sin datos de la mesa/)).toBeInTheDocument()
    expect(screen.getByText('v0.1.0')).toBeInTheDocument()
  })

  it('pinta los canales y el modelo al recibir un volcado', () => {
    useMixerStore.getState().applyState(SNAPSHOT)
    useMixerStore.getState().setConnectionState('connected')

    render(<App />)

    expect(screen.getByText('QU-16 · fw 1.97')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(
      screen.getByRole('heading', { level: 3, name: 'coro1' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 3, name: 'coro2' }),
    ).toBeInTheDocument()
    expect(screen.getByText('−∞')).toBeInTheDocument()
  })
})
