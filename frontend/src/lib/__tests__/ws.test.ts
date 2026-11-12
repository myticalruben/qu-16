import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { connectMixerSocket, disconnectMixerSocket } from '../ws'
import { useMixerStore } from '../../store/mixer'

/**
 * Socket mínimo de mentira: permite abrir, emitir mensajes y cerrar sin red.
 * El cliente real solo usa `onopen`, `onmessage`, `onclose`, `close` y las
 * constantes de `readyState`.
 */
class MockWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3
  static instances: MockWebSocket[] = []

  readyState = MockWebSocket.CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((event: { data: unknown }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null
  readonly url: string

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  open(): void {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.()
  }

  receive(message: unknown): void {
    this.onmessage?.({ data: JSON.stringify(message) })
  }

  close(): void {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }
}

const getSocket = (): MockWebSocket => {
  const socket = MockWebSocket.instances[0]
  if (socket === undefined) throw new Error('No se abrió ningún socket')
  return socket
}

describe('mixer WebSocket', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
    useMixerStore.getState().reset()
  })

  afterEach(() => {
    disconnectMixerSocket()
    vi.unstubAllGlobals()
  })

  it('confirma el enlace con hello y aplica el state normalizado', () => {
    connectMixerSocket()

    const socket = getSocket()
    expect(useMixerStore.getState().linkActive).toBe(true)
    expect(useMixerStore.getState().connectionState).toBe('connecting')

    socket.open()
    socket.receive({ type: 'hello', payload: { version: '0.1.0' } })

    expect(useMixerStore.getState().connectionState).toBe('connected')
    expect(useMixerStore.getState().serverVersion).toBe('0.1.0')

    socket.receive({
      type: 'state',
      payload: {
        connected: true,
        model: 'QU-16',
        firmware: '1.97',
        updated_at: '2026-11-12T01:10:00+00:00',
        channels: [
          { index: 4, name: 'coro2', level_db: 6.5, kind: 'input' },
          { index: 1, name: 'coro1', level_db: null, kind: 'input' },
        ],
      },
    })

    const state = useMixerStore.getState()
    expect(state.connected).toBe(true)
    expect(state.model).toBe('QU-16')
    expect(state.updatedAt).toBe('2026-11-12T01:10:00+00:00')
    expect(state.channels.map((channel) => channel.index)).toEqual([1, 4])
    expect(state.channels[0]?.levelDb).toBeNull()
    expect(state.connectionState).toBe('connected')
  })

  it('refleja en la insignia una mesa apagada aunque el socket siga abierto', () => {
    connectMixerSocket()
    const socket = getSocket()

    socket.open()
    socket.receive({ type: 'hello', payload: { version: '0.1.0' } })
    socket.receive({
      type: 'state',
      payload: {
        connected: false,
        model: null,
        firmware: null,
        updated_at: null,
        channels: [],
      },
    })

    const state = useMixerStore.getState()
    expect(state.connectionState).toBe('disconnected')
    expect(state.linkActive).toBe(true)
    expect(state.connected).toBe(false)
    expect(state.channels).toEqual([])
  })
})
