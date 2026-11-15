import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { ChannelMenu } from '../ChannelMenu'
import { ChannelRack } from '../ChannelRack'
import type { MixerStatePayload } from '../../store/mixer'
import {
  DEFAULT_VISIBLE_CHANNELS,
  INPUT_CHANNEL_LIMIT,
  VISIBLE_CHANNELS_STORAGE_KEY,
  useMixerStore,
} from '../../store/mixer'

const FULL_SNAPSHOT: MixerStatePayload = {
  connected: true,
  model: 'QU-16',
  firmware: '1.97',
  updated_at: '2026-11-12T01:10:00+00:00',
  channels: Array.from({ length: 60 }, (_, index) => ({
    index,
    name: index < 16 ? `canal ${index + 1}` : `mezcla ${index + 1}`,
    level_db: -6,
    kind: index < 16 ? ('input' as const) : ('other' as const),
  })),
}

const storedSelection = (): unknown =>
  JSON.parse(localStorage.getItem(VISIBLE_CHANNELS_STORAGE_KEY) ?? 'null')

/** Menú y rack juntos, como los coloca la cabecera y el cuerpo de la consola. */
function renderConsole() {
  return render(
    <>
      <ChannelMenu />
      <ChannelRack />
    </>,
  )
}

describe('ChannelMenu', () => {
  beforeEach(() => {
    localStorage.clear()
    useMixerStore.getState().reset()
    useMixerStore.getState().setVisibleChannels(DEFAULT_VISIBLE_CHANNELS)
    useMixerStore.getState().applyState(FULL_SNAPSHOT)
  })

  it('resume la selección y abre las 16 casillas con el nombre real', () => {
    renderConsole()

    const trigger = screen.getByRole('button', { name: 'Canales: 16/16' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()

    fireEvent.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    const menu = screen.getByRole('group', { name: 'Canales a controlar' })
    expect(menu).toHaveAttribute('id', trigger.getAttribute('aria-controls'))

    const boxes = screen.getAllByRole('checkbox')
    expect(boxes).toHaveLength(INPUT_CHANNEL_LIMIT)
    expect(
      screen.getByRole('checkbox', { name: 'CH 4 · canal 4' }),
    ).toBeChecked()
    expect(screen.getAllByRole('listitem')).toHaveLength(16)
  })

  it('desmarcar un canal reduce el rack, actualiza el resumen y persiste', () => {
    renderConsole()
    fireEvent.click(screen.getByRole('button', { name: 'Canales: 16/16' }))

    fireEvent.click(screen.getByRole('checkbox', { name: 'CH 4 · canal 4' }))

    expect(
      screen.getByRole('checkbox', { name: 'CH 4 · canal 4' }),
    ).not.toBeChecked()
    expect(
      screen.getByRole('button', { name: 'Canales: 15/16' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(15)
    expect(screen.queryByLabelText('Canal 3: canal 4')).not.toBeInTheDocument()

    const stored = storedSelection()
    expect(stored).toHaveLength(15)
    expect(stored).not.toContain(3)
  })

  it('«Ninguno» deja el rack vacío y «Todos» recupera los 16', () => {
    renderConsole()
    const trigger = screen.getByRole('button', { name: 'Canales: 16/16' })
    fireEvent.click(trigger)

    fireEvent.click(screen.getByRole('button', { name: 'Ninguno' }))

    expect(screen.getByText('Ningún canal seleccionado')).toBeInTheDocument()
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    expect(
      screen.getByRole('button', { name: 'Canales: 0/16' }),
    ).toBeInTheDocument()
    expect(storedSelection()).toEqual([])

    fireEvent.click(screen.getByRole('button', { name: 'Todos' }))

    expect(
      screen.queryByText('Ningún canal seleccionado'),
    ).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(16)
    expect(
      screen.getByRole('button', { name: 'Canales: 16/16' }),
    ).toBeInTheDocument()
    expect(storedSelection()).toHaveLength(16)
  })

  it('lee la selección guardada al montar', () => {
    localStorage.setItem(
      VISIBLE_CHANNELS_STORAGE_KEY,
      JSON.stringify([0, 1]),
    )

    renderConsole()

    expect(
      screen.getByRole('button', { name: 'Canales: 2/16' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)

    fireEvent.click(screen.getByRole('button', { name: 'Canales: 2/16' }))
    expect(screen.getByRole('checkbox', { name: 'CH 1 · canal 1' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'CH 2 · canal 2' })).toBeChecked()
    expect(
      screen.getByRole('checkbox', { name: 'CH 3 · canal 3' }),
    ).not.toBeChecked()
  })

  it('se cierra con Escape y al hacer clic fuera', () => {
    renderConsole()
    const trigger = screen.getByRole('button', { name: 'Canales: 16/16' })

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    fireEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    fireEvent.pointerDown(document.body)
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })
})
