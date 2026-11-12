import { create } from 'zustand'

/** Los tres estados visibles del enlace con el backend. */
export type ConnectionState = 'disconnected' | 'connecting' | 'connected'

/** Acento visual del canal; la consola usa ámbar y cian. */
export type ChannelAccent = 'amber' | 'cyan'

export interface MixerChannel {
  /** Índice de canal que usa el protocolo (1–16 en la Qu-16). */
  id: number
  name: string
  /** Posición del fader en dB. El mínimo de la maqueta es -60 dB. */
  faderDb: number
  /** Nivel instantáneo del medidor, normalizado de 0 a 1. */
  meter: number
  muted: boolean
  accent: ChannelAccent
}

export const FADER_MIN_DB = -60
export const FADER_MAX_DB = 10

/**
 * Canales de ejemplo mientras el backend no entrega el volcado real.
 * Los nombres imitan los que ya usaba la mesa en la Fase 0.
 */
export const demoChannels: MixerChannel[] = [
  { id: 1, name: 'coro1', faderDb: -3.5, meter: 0.64, muted: false, accent: 'cyan' },
  { id: 2, name: 'piano', faderDb: -7, meter: 0.52, muted: false, accent: 'amber' },
  { id: 3, name: 'guitar', faderDb: -1.5, meter: 0.71, muted: false, accent: 'cyan' },
  { id: 4, name: 'voz 1', faderDb: 1.5, meter: 0.82, muted: false, accent: 'amber' },
  { id: 5, name: 'voz 2', faderDb: -5, meter: 0.58, muted: false, accent: 'cyan' },
  { id: 6, name: 'bajo', faderDb: -9, meter: 0.45, muted: false, accent: 'amber' },
  { id: 7, name: 'batería', faderDb: -2, meter: 0.76, muted: false, accent: 'cyan' },
  { id: 8, name: 'FX 1', faderDb: -14, meter: 0.28, muted: true, accent: 'amber' },
]

interface MixerStore {
  connectionState: ConnectionState
  serverVersion: string | null
  channels: MixerChannel[]
  setConnectionState: (state: ConnectionState) => void
  setServerVersion: (version: string | null) => void
  setChannels: (channels: MixerChannel[]) => void
  setChannelFader: (id: number, faderDb: number) => void
  setChannelMeter: (id: number, meter: number) => void
  toggleChannelMute: (id: number) => void
  reset: () => void
}

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value))

const freshDemoChannels = () => demoChannels.map((channel) => ({ ...channel }))

export const useMixerStore = create<MixerStore>()((set) => ({
  connectionState: 'disconnected',
  serverVersion: null,
  channels: freshDemoChannels(),

  setConnectionState: (connectionState) => set({ connectionState }),

  setServerVersion: (serverVersion) => set({ serverVersion }),

  setChannels: (channels) => set({ channels: channels.map((channel) => ({ ...channel })) }),

  setChannelFader: (id, faderDb) =>
    set((state) => ({
      channels: state.channels.map((channel) =>
        channel.id === id
          ? {
              ...channel,
              faderDb: clamp(faderDb, FADER_MIN_DB, FADER_MAX_DB),
            }
          : channel,
      ),
    })),

  setChannelMeter: (id, meter) =>
    set((state) => ({
      channels: state.channels.map((channel) =>
        channel.id === id
          ? { ...channel, meter: clamp(meter, 0, 1) }
          : channel,
      ),
    })),

  toggleChannelMute: (id) =>
    set((state) => ({
      channels: state.channels.map((channel) =>
        channel.id === id ? { ...channel, muted: !channel.muted } : channel,
      ),
    })),

  reset: () =>
    set({
      connectionState: 'disconnected',
      serverVersion: null,
      channels: freshDemoChannels(),
    }),
}))
