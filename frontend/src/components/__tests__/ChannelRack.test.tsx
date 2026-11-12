import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { ChannelRack } from '../ChannelRack'
import type { MixerStatePayload } from '../../store/mixer'
import { useMixerStore } from '../../store/mixer'

const SNAPSHOT: MixerStatePayload = {
  connected: true,
  model: 'QU-16',
  firmware: '1.97',
  updated_at: '2026-11-12T01:10:00+00:00',
  channels: [
    { index: 4, name: 'coro2', level_db: 6.5, kind: 'input' },
    { index: 2, name: '', level_db: null, kind: 'other' },
    { index: 1, name: 'coro1', level_db: 4.9, kind: 'input' },
    { index: 3, name: '   ', level_db: -12, kind: 'stereo' },
  ],
}

describe('ChannelRack', () => {
  beforeEach(() => {
    useMixerStore.getState().reset()
    useMixerStore.getState().applyState(SNAPSHOT)
  })

  it('pinta solo los canales con nombre por defecto', () => {
    render(<ChannelRack />)

    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(
      screen.getByRole('heading', { level: 3, name: 'coro1' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 3, name: 'coro2' }),
    ).toBeInTheDocument()
    expect(screen.queryByLabelText('Canal 2: sin nombre')).not.toBeInTheDocument()
  })

  it('pinta todos los canales al activar el control y atenúa los vacíos', () => {
    render(<ChannelRack />)

    fireEvent.click(screen.getByRole('checkbox', { name: 'Mostrar todos' }))

    expect(screen.getAllByRole('listitem')).toHaveLength(4)

    const unnamedEmpty = screen.getByLabelText('Canal 2: sin nombre')
    expect(unnamedEmpty).toHaveAttribute('data-unnamed', 'true')
    expect(unnamedEmpty.className).toContain('opacity-60')
    expect(within(unnamedEmpty).getByText('−∞')).toBeInTheDocument()
    expect(within(unnamedEmpty).getByText('OT')).toBeInTheDocument()

    const unnamedBlank = screen.getByLabelText('Canal 3: sin nombre')
    expect(within(unnamedBlank).getByText('ST')).toBeInTheDocument()

    // Los canales con nombre no se atenúan.
    expect(screen.getByLabelText('Canal 1: coro1')).not.toHaveAttribute(
      'data-unnamed',
    )
  })

  it('muestra el estado vacío si aún no hay volcado', () => {
    useMixerStore.getState().reset()

    render(<ChannelRack />)

    expect(screen.getByText(/Sin datos de la mesa/)).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
  })
})
