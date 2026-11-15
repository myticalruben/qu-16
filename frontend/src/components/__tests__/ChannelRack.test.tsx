import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { ChannelRack } from '../ChannelRack'
import type { MixerStatePayload } from '../../store/mixer'
import {
  DEFAULT_VISIBLE_CHANNELS,
  useMixerStore,
} from '../../store/mixer'

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

/** Volcado realista: 16 entradas físicas y 44 mezclas/FX/destinos. */
const FULL_SNAPSHOT: MixerStatePayload = {
  ...SNAPSHOT,
  channels: Array.from({ length: 60 }, (_, index) => ({
    index,
    name: index < 16 ? `canal ${index + 1}` : `mezcla ${index + 1}`,
    level_db: -6,
    kind: index < 16 ? ('input' as const) : ('other' as const),
  })),
}

describe('ChannelRack', () => {
  beforeEach(() => {
    localStorage.clear()
    useMixerStore.getState().reset()
    useMixerStore.getState().setVisibleChannels(DEFAULT_VISIBLE_CHANNELS)
    useMixerStore.getState().applyState(SNAPSHOT)
  })

  it('pinta todos los canales de entrada recibidos, tengan nombre o no', () => {
    render(<ChannelRack />)

    expect(screen.getAllByRole('listitem')).toHaveLength(4)
    expect(
      screen.getByRole('heading', { level: 3, name: 'coro1' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 3, name: 'coro2' }),
    ).toBeInTheDocument()

    const unnamed = screen.getByLabelText('Canal 2: sin nombre')
    expect(unnamed).toHaveAttribute('data-unnamed', 'true')
    expect(within(unnamed).getByText('−∞')).toBeInTheDocument()
    expect(within(unnamed).getByText('OT')).toBeInTheDocument()
  })

  it('con 60 canales en el payload pinta como máximo los 16 de entrada', () => {
    useMixerStore.getState().applyState(FULL_SNAPSHOT)

    render(<ChannelRack />)

    const strips = screen.getAllByRole('listitem')
    expect(strips).toHaveLength(16)
    expect(screen.getByLabelText('Canal 0: canal 1')).toBeInTheDocument()
    // El índice 15 es el canal 16 de la mesa; los índices >= 16 no se pintan.
    expect(screen.getByLabelText('Canal 15: canal 16')).toBeInTheDocument()
    expect(screen.queryByLabelText('Canal 16: mezcla 17')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Canal 59: mezcla 60')).not.toBeInTheDocument()
  })

  it('solo pinta los canales marcados en la selección', () => {
    useMixerStore.getState().setVisibleChannels([1, 4])

    render(<ChannelRack />)

    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByLabelText('Canal 1: coro1')).toBeInTheDocument()
    expect(screen.getByLabelText('Canal 4: coro2')).toBeInTheDocument()
    expect(screen.queryByLabelText('Canal 2: sin nombre')).not.toBeInTheDocument()
    expect(screen.getByText('2 en pantalla')).toBeInTheDocument()
  })

  it('muestra el aviso y ningún canal si la selección está vacía', () => {
    useMixerStore.getState().setVisibleChannels([])

    render(<ChannelRack />)

    expect(screen.getByText('Ningún canal seleccionado')).toBeInTheDocument()
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)

    fireEvent.click(screen.getByRole('button', { name: 'Mostrar los 16' }))
    expect(screen.getAllByRole('listitem')).toHaveLength(4)
  })

  it('conecta cada medidor con el índice de canal del store', () => {
    useMixerStore.getState().applyMeters([null, -12, null, null, -2.9])

    render(<ChannelRack />)

    const coro1Meter = screen.getByRole('meter', {
      name: 'Medidor de coro1',
    })
    expect(
      coro1Meter.querySelector('.meter-bar__fill'),
    ).toHaveStyle({ height: '80%' })

    const coro2Meter = screen.getByRole('meter', {
      name: 'Medidor de coro2',
    })
    expect(
      coro2Meter.querySelector('.meter-bar__fill'),
    ).toHaveStyle({ height: '95%' })
  })

  it('muestra el estado vacío si aún no hay volcado', () => {
    useMixerStore.getState().reset()

    render(<ChannelRack />)

    expect(screen.getByText(/Sin datos de la mesa/)).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
  })
})
