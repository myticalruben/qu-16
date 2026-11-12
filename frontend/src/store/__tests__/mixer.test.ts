import { beforeEach, describe, expect, it } from 'vitest'

import {
  FADER_MAX_DB,
  FADER_MIN_DB,
  demoChannels,
  useMixerStore,
} from '../mixer'

describe('mixer store', () => {
  beforeEach(() => {
    useMixerStore.getState().reset()
  })

  it('arranca desconectado, sin versión y con los canales de ejemplo', () => {
    const state = useMixerStore.getState()

    expect(state.connectionState).toBe('disconnected')
    expect(state.serverVersion).toBeNull()
    expect(state.channels).toHaveLength(8)
    expect(state.channels.map((channel) => channel.name)).toEqual(
      demoChannels.map((channel) => channel.name),
    )
  })

  it('actualiza el estado de conexión', () => {
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

  it('mueve el fader dentro de los límites de la consola', () => {
    useMixerStore.getState().setChannelFader(1, 0)
    expect(useMixerStore.getState().channels[0]?.faderDb).toBe(0)

    useMixerStore.getState().setChannelFader(1, FADER_MAX_DB + 40)
    expect(useMixerStore.getState().channels[0]?.faderDb).toBe(FADER_MAX_DB)

    useMixerStore.getState().setChannelFader(1, FADER_MIN_DB - 40)
    expect(useMixerStore.getState().channels[0]?.faderDb).toBe(FADER_MIN_DB)
  })

  it('alterna el mute de un canal sin tocar los demás', () => {
    const original = useMixerStore.getState().channels[1]?.muted

    useMixerStore.getState().toggleChannelMute(2)

    const channels = useMixerStore.getState().channels
    expect(channels[1]?.muted).toBe(!original)
    expect(channels[0]?.muted).toBe(false)
  })

  it('normaliza el nivel del medidor entre 0 y 1', () => {
    useMixerStore.getState().setChannelMeter(3, 1.8)
    expect(useMixerStore.getState().channels[2]?.meter).toBe(1)

    useMixerStore.getState().setChannelMeter(3, -0.5)
    expect(useMixerStore.getState().channels[2]?.meter).toBe(0)
  })

  it('reemplaza canales con una copia defensiva', () => {
    const replacement = [
      {
        id: 1,
        name: 'voz principal',
        faderDb: -6,
        meter: 0.4,
        muted: false,
        accent: 'cyan' as const,
      },
    ]

    useMixerStore.getState().setChannels(replacement)

    expect(useMixerStore.getState().channels).toEqual(replacement)
    expect(useMixerStore.getState().channels).not.toBe(replacement)
  })
})
