import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ChannelRack } from '../ChannelRack'
import { WriteErrorNotice } from '../WriteErrorNotice'
import type { MixerStatePayload } from '../../store/mixer'
import { useMixerStore } from '../../store/mixer'

const SNAPSHOT: MixerStatePayload = {
  connected: true,
  model: 'QU-16',
  firmware: '1.97',
  updated_at: '2026-11-12T01:10:00+00:00',
  channels: [
    { index: 1, name: 'coro1', level_db: 4.9, kind: 'input' },
    { index: 2, name: '', level_db: -12, kind: 'input' },
  ],
}

const jsonResponse = (body: unknown, status = 200): Response =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as Response

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>()

/** Abre el candado como si el diálogo ya se hubiera confirmado. */
function enableControl(): void {
  useMixerStore
    .getState()
    .setWriteConfig({ write_enabled: true, model: 'QU-16', connected: true })
  useMixerStore.getState().setControlEnabled(true)
}

function levelOf(index: number): number | null {
  return (
    useMixerStore.getState().channels.find((channel) => channel.index === index)
      ?.levelDb ?? null
  )
}

describe('fader interactivo', () => {
  beforeEach(() => {
    useMixerStore.getState().reset()
    useMixerStore.getState().applyState(SNAPSHOT)
    fetchMock.mockReset()
    // El backend devuelve el nivel aplicado: así el test no depende de una
    // respuesta concreta y una respuesta igual no re-renderiza el store.
    fetchMock.mockImplementation(async (_input, init) => {
      const body = JSON.parse(String(init?.body)) as { db: number }
      return jsonResponse({ index: 1, value: 32_000, db: body.db })
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('con el candado apagado es de solo lectura y no dispara peticiones', () => {
    render(<ChannelRack />)

    const fader = screen.getByRole('slider', { name: 'Fader de coro1' })
    expect(fader).toBeDisabled()
    expect(screen.getByText('solo lectura')).toBeInTheDocument()

    fireEvent.pointerDown(fader)
    fireEvent.change(fader, { target: { value: '-6' } })
    fireEvent.pointerUp(fader)

    expect(fetchMock).not.toHaveBeenCalled()
    expect(levelOf(1)).toBe(4.9)
  })

  it('con el candado activo envía el valor al soltar, no durante el arrastre', async () => {
    enableControl()
    render(<ChannelRack />)

    const fader = screen.getByRole('slider', { name: 'Fader de coro1' })
    expect(fader).toBeEnabled()

    fireEvent.pointerDown(fader)
    fireEvent.change(fader, { target: { value: '-6' } })
    expect(fetchMock).not.toHaveBeenCalled()

    fireEvent.pointerUp(fader)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/mixer/channels/1/level')
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ db: -6 }),
    })

    // Optimista: el store ya está en el valor nuevo.
    expect(levelOf(1)).toBe(-6)
    await waitFor(() => expect(levelOf(1)).toBe(-6))
    expect(useMixerStore.getState().lastError).toBeNull()
  })

  it('frena el arrastre: nada antes de 400 ms y como máximo un envío cada 200 ms', () => {
    enableControl()
    // Las respuestas quedan pendientes: aquí solo importa cuántos POST salen.
    fetchMock.mockImplementation(() => new Promise<Response>(() => {}))
    const now = vi.spyOn(performance, 'now').mockReturnValue(0)
    render(<ChannelRack />)

    const fader = screen.getByRole('slider', { name: 'Fader de coro1' })
    fireEvent.pointerDown(fader)

    fireEvent.change(fader, { target: { value: '0' } })
    now.mockReturnValue(399)
    fireEvent.change(fader, { target: { value: '-1' } })
    expect(fetchMock).not.toHaveBeenCalled()

    now.mockReturnValue(401)
    fireEvent.change(fader, { target: { value: '-2' } })
    expect(fetchMock).toHaveBeenCalledTimes(1)

    now.mockReturnValue(550)
    fireEvent.change(fader, { target: { value: '-3' } })
    expect(fetchMock).toHaveBeenCalledTimes(1)

    now.mockReturnValue(601)
    fireEvent.change(fader, { target: { value: '-4' } })
    expect(fetchMock).toHaveBeenCalledTimes(2)

    now.mockReturnValue(700)
    fireEvent.pointerUp(fader)

    // El valor final se manda siempre al soltar.
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[2]?.[1]?.body).toBe(JSON.stringify({ db: -4 }))
  })

  it('revierte el valor y muestra el aviso si la API responde 409', async () => {
    enableControl()
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'write disabled' }, 409))

    render(
      <>
        <ChannelRack />
        <WriteErrorNotice />
      </>,
    )

    const fader = screen.getByRole('slider', { name: 'Fader de coro1' })
    fireEvent.pointerDown(fader)
    fireEvent.change(fader, { target: { value: '-12' } })
    fireEvent.pointerUp(fader)

    // Optimista: primero se mueve, luego la API lo rechaza.
    expect(levelOf(1)).toBe(-12)
    expect(screen.getByText('−12.0')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/bloqueada/i)
    })
    expect(levelOf(1)).toBe(4.9)
    expect(screen.getByText('+4.9')).toBeInTheDocument()
  })

  it('no permite arrastrar canales sin nombre ni con la mesa desconectada', () => {
    enableControl()
    render(<ChannelRack />)

    // Los canales sin nombre solo aparecen con «Mostrar todos».
    fireEvent.click(screen.getByRole('checkbox', { name: 'Mostrar todos' }))
    expect(screen.getByRole('slider', { name: 'Fader de canal 2' })).toBeDisabled()

    act(() => {
      useMixerStore.getState().applyState({ ...SNAPSHOT, connected: false })
    })
    expect(screen.getByRole('slider', { name: 'Fader de coro1' })).toBeDisabled()
  })
})
