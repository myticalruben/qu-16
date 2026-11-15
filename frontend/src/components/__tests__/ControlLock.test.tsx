import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../../App'
import { useMixerStore } from '../../store/mixer'

/** Respuesta mínima con la forma que consume `getMixerConfig`. */
const jsonResponse = (body: unknown, status = 200): Response =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as Response

const fetchMock = vi.fn<
  (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
>()

function mockConfig(writeEnabled: boolean): void {
  fetchMock.mockResolvedValue(
    jsonResponse({ write_enabled: writeEnabled, model: 'QU-16', connected: true }),
  )
}

describe('ControlLock', () => {
  beforeEach(() => {
    useMixerStore.getState().reset()
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('arranca apagado y exige confirmación antes de activarse', async () => {
    mockConfig(true)
    render(<App />)

    await waitFor(() => {
      expect(useMixerStore.getState().writeConfig).not.toBeNull()
    })

    const trigger = screen.getByRole('button', { name: 'Control' })
    expect(trigger).toBeEnabled()
    expect(trigger).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('Listo para activar')).toBeInTheDocument()
    expect(useMixerStore.getState().controlEnabled).toBe(false)

    // Primer estado: pulsar no activa nada, abre la confirmación.
    fireEvent.click(trigger)
    const dialog = screen.getByRole('dialog', {
      name: 'Activar control de escritura',
    })
    expect(
      within(dialog).getByText(
        'Vas a poder mover faders de la mesa real. El sonido cambiará.',
      ),
    ).toBeInTheDocument()
    expect(useMixerStore.getState().controlPending).toBe(true)
    expect(useMixerStore.getState().controlEnabled).toBe(false)

    // Cancelar vuelve al estado apagado sin abrir el candado.
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(useMixerStore.getState().controlEnabled).toBe(false)

    // Confirmar sí lo abre.
    fireEvent.click(trigger)
    fireEvent.click(
      screen.getByRole('button', { name: 'Activar control' }),
    )

    expect(useMixerStore.getState().controlEnabled).toBe(true)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Control' }),
    ).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Control activo')).toBeInTheDocument()

    // El candado no dispara peticiones extra: solo se leyó la configuración.
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/mixer/config')
  })

  it('queda deshabilitado y lo anuncia si el servidor no permite escribir', async () => {
    mockConfig(false)
    render(<App />)

    await waitFor(() => {
      expect(useMixerStore.getState().writeConfig).not.toBeNull()
    })

    const trigger = screen.getByRole('button', { name: 'Control' })
    expect(trigger).toBeDisabled()
    expect(screen.getByText('Bloqueado en el servidor')).toBeInTheDocument()

    fireEvent.click(trigger)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(useMixerStore.getState().controlPending).toBe(false)
    expect(useMixerStore.getState().controlEnabled).toBe(false)
  })
})
