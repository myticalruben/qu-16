import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { MixerStatePayload } from '../mixer'
import {
  channelCount,
  levelFor,
  namedChannels,
  useMixerStore,
} from '../mixer'

const SNAPSHOT: MixerStatePayload = {
  connected: true,
  model: 'QU-16',
  firmware: '1.97',
  updated_at: '2026-11-12T01:10:00+00:00',
  channels: [
    { index: 4, name: 'coro2', level_db: 6.5, kind: 'input' },
    { index: 1, name: 'coro1', level_db: 4.9, kind: 'input' },
    { index: 3, name: '', level_db: null, kind: 'other' },
    { index: 2, name: '  ', level_db: -12, kind: 'stereo' },
  ],
}

describe('mixer store', () => {
  beforeEach(() => {
    useMixerStore.getState().reset()
  })

  it('arranca vacío, desconectado y sin versión', () => {
    const state = useMixerStore.getState()

    expect(state.connectionState).toBe('disconnected')
    expect(state.connected).toBe(false)
    expect(state.serverVersion).toBeNull()
    expect(state.model).toBeNull()
    expect(state.firmware).toBeNull()
    expect(state.updatedAt).toBeNull()
    expect(state.channels).toEqual([])
    expect(state.levels).toEqual([])
    expect(state.controlEnabled).toBe(false)
    expect(state.controlPending).toBe(false)
    expect(state.writeConfig).toBeNull()
    expect(state.lastError).toBeNull()
    expect(state.draggingChannels).toEqual([])
  })

  it('actualiza el estado de conexión del socket', () => {
    useMixerStore.getState().setConnectionState('connecting')
    expect(useMixerStore.getState().connectionState).toBe('connecting')

    useMixerStore.getState().setConnectionState('connected')
    expect(useMixerStore.getState().connectionState).toBe('connected')

    useMixerStore.getState().setConnectionState('disconnected')
    expect(useMixerStore.getState().connectionState).toBe('disconnected')
  })

  it('guarda la versión del servidor', () => {
    useMixerStore.getState().setServerVersion('1.2.3')
    expect(useMixerStore.getState().serverVersion).toBe('1.2.3')

    useMixerStore.getState().setServerVersion(null)
    expect(useMixerStore.getState().serverVersion).toBeNull()
  })

  it('normaliza, ordena por índice y guarda levelDb null', () => {
    useMixerStore.getState().applyState(SNAPSHOT)

    const state = useMixerStore.getState()
    expect(state.connected).toBe(true)
    expect(state.model).toBe('QU-16')
    expect(state.firmware).toBe('1.97')
    expect(state.updatedAt).toBe('2026-11-12T01:10:00+00:00')
    expect(state.channels.map((channel) => channel.index)).toEqual([1, 2, 3, 4])

    expect(state.channels[0]).toEqual({
      index: 1,
      name: 'coro1',
      levelDb: 4.9,
      kind: 'input',
    })
    expect(state.channels[1]).toEqual({
      index: 2,
      name: '',
      levelDb: -12,
      kind: 'stereo',
    })
    expect(state.channels[2]).toEqual({
      index: 3,
      name: '',
      levelDb: null,
      kind: 'other',
    })
    expect(state.channels[3]?.levelDb).toBe(6.5)
  })

  it('refleja una mesa desconectada y vacía los canales', () => {
    useMixerStore.getState().applyState({
      connected: false,
      model: null,
      firmware: null,
      updated_at: null,
      channels: [],
    })

    const state = useMixerStore.getState()
    expect(state.connected).toBe(false)
    expect(state.channels).toEqual([])
    expect(state.model).toBeNull()
  })

  it('guarda los medidores y los expone por índice de canal', () => {
    useMixerStore.getState().applyMeters([-104.5, null, -38.7])

    const state = useMixerStore.getState()
    expect(state.levels).toEqual([-104.5, null, -38.7])
    expect(state.levelFor(0)).toBe(-104.5)
    expect(state.levelFor(1)).toBeNull()
    expect(state.levelFor(2)).toBe(-38.7)
    expect(state.levelFor(58)).toBeNull()

    // También se puede usar como selector puro sobre un estado concreto.
    expect(levelFor(state, 2)).toBe(-38.7)
    expect(levelFor(0)).toBe(-104.5)
  })

  it('degrada a silencio los valores inválidos de meters', () => {
    useMixerStore.getState().applyMeters([Number.NaN, 'x', undefined, -12])

    expect(useMixerStore.getState().levels).toEqual([null, null, null, -12])
  })

  it('no notifica si el mensaje meters repite los mismos valores', () => {
    useMixerStore.getState().applyMeters([-12, -6])
    const listener = vi.fn()
    const unsubscribe = useMixerStore.subscribe(listener)

    useMixerStore.getState().applyMeters([-12, -6])
    expect(listener).not.toHaveBeenCalled()

    useMixerStore.getState().applyMeters([-11, -6])
    expect(listener).toHaveBeenCalledTimes(1)

    unsubscribe()
  })

  it('expone selectores de total y de canales con nombre', () => {
    useMixerStore.getState().applyState(SNAPSHOT)

    const state = useMixerStore.getState()
    expect(channelCount(state)).toBe(4)
    expect(namedChannels(state).map((channel) => channel.name)).toEqual([
      'coro1',
      'coro2',
    ])
  })

  it('solo abre el candado con permiso del servidor y lo cierra si se retira', () => {
    const store = useMixerStore.getState()

    // Sin configuración no hay permiso: el candado no se abre.
    store.setControlEnabled(true)
    expect(useMixerStore.getState().controlEnabled).toBe(false)

    store.setWriteConfig({
      write_enabled: true,
      model: 'QU-16',
      connected: true,
    })
    store.setControlEnabled(true)
    expect(useMixerStore.getState().controlEnabled).toBe(true)

    // El backend retira el permiso: se cierra de inmediato.
    store.setWriteConfig({
      write_enabled: false,
      model: 'QU-16',
      connected: true,
    })
    expect(useMixerStore.getState().controlEnabled).toBe(false)
  })

  it('mantiene el nivel optimista del canal en arrastre aunque llegue un state', () => {
    const store = useMixerStore.getState()
    store.applyState(SNAPSHOT)
    store.setChannelLevelDb(1, -6)
    store.beginChannelDrag(1)

    store.applyState({
      ...SNAPSHOT,
      channels: [
        { index: 1, name: 'coro1', level_db: 4.9, kind: 'input' },
        { index: 2, name: '', level_db: -12, kind: 'stereo' },
      ],
    })

    expect(
      useMixerStore.getState().channels.find((channel) => channel.index === 1)
        ?.levelDb,
    ).toBe(-6)

    // Al soltar, el volcado vuelve a mandar.
    store.endChannelDrag(1)
    store.applyState(SNAPSHOT)
    expect(
      useMixerStore.getState().channels.find((channel) => channel.index === 1)
        ?.levelDb,
    ).toBe(4.9)
  })

  it('reset vuelve al estado vacío inicial', () => {
    useMixerStore.getState().applyState(SNAPSHOT)
    useMixerStore.getState().setConnectionState('connected')
    useMixerStore.getState().setLinkActive(true)
    useMixerStore.getState().setServerVersion('0.1.0')
    useMixerStore.getState().applyMeters([-12, null])
    useMixerStore
      .getState()
      .setWriteConfig({ write_enabled: true, model: 'QU-16', connected: true })
    useMixerStore.getState().setControlEnabled(true)
    useMixerStore.getState().setControlPending(true)
    useMixerStore.getState().setLastError('fallo')
    useMixerStore.getState().beginChannelDrag(1)

    useMixerStore.getState().reset()

    const state = useMixerStore.getState()
    expect(state.connectionState).toBe('disconnected')
    expect(state.linkActive).toBe(false)
    expect(state.serverVersion).toBeNull()
    expect(state.channels).toEqual([])
    expect(state.levels).toEqual([])
    expect(state.connected).toBe(false)
    expect(state.controlEnabled).toBe(false)
    expect(state.controlPending).toBe(false)
    expect(state.writeConfig).toBeNull()
    expect(state.lastError).toBeNull()
    expect(state.draggingChannels).toEqual([])
  })
})
