import { create } from 'zustand'

/** Los tres estados visibles del enlace con el backend. */
export type ConnectionState = 'disconnected' | 'connecting' | 'connected'

/** Naturaleza del canal tal y como la reporta el backend. */
export type ChannelKind = 'input' | 'stereo' | 'other'

/** Canal ya normalizado para la UI (camelCase y nombres no vacíos limpios). */
export interface Channel {
  /** Índice de canal que usa el protocolo de la Qu-16. */
  index: number
  name: string
  /** Nivel del fader en dB; `null` equivale a −∞. */
  levelDb: number | null
  kind: ChannelKind
}

/** Volcado completo de la mesa, tal y como lo consume la interfaz. */
export interface MixerSnapshot {
  /** `true` solo si el backend tiene enlace con la mesa física. */
  connected: boolean
  model: string | null
  firmware: string | null
  /** Marca temporal ISO del último volcado. */
  updatedAt: string | null
  channels: Channel[]
}

/** Canal tal y como viaja por el WebSocket (snake_case). */
export interface ChannelPayload {
  index: number
  name: string
  level_db: number | null
  kind: ChannelKind
}

/** Mensaje `state` del backend sin normalizar. */
export interface MixerStatePayload {
  connected: boolean
  model: string | null
  firmware: string | null
  updated_at: string | null
  channels: ChannelPayload[]
}

export const FADER_MIN_DB = -60
export const FADER_MAX_DB = 10

const EMPTY_SNAPSHOT: MixerSnapshot = {
  connected: false,
  model: null,
  firmware: null,
  updatedAt: null,
  channels: [],
}

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)

/** Descarta cadenas vacías o de solo espacios; el resto se recorta. */
const normalizeText = (value: unknown): string =>
  typeof value === 'string' ? value.trim() : ''

const normalizeKind = (value: unknown): ChannelKind =>
  value === 'input' || value === 'stereo' ? value : 'other'

/** Normaliza un canal del protocolo y tolera campos ausentes o corruptos. */
function normalizeChannel(payload: ChannelPayload): Channel {
  return {
    index: isFiniteNumber(payload?.index) ? payload.index : 0,
    name: normalizeText(payload?.name),
    levelDb: isFiniteNumber(payload?.level_db) ? payload.level_db : null,
    kind: normalizeKind(payload?.kind),
  }
}

interface MixerState extends MixerSnapshot {
  /** Estado del socket con el backend, que no es lo mismo que la mesa. */
  connectionState: ConnectionState
  /** `true` mientras el usuario mantiene el enlace abierto (aunque reintente). */
  linkActive: boolean
  serverVersion: string | null
  setConnectionState: (state: ConnectionState) => void
  setLinkActive: (active: boolean) => void
  setServerVersion: (version: string | null) => void
  /** Aplica un mensaje `state`: normaliza snake_case, ordena y guarda. */
  applyState: (payload: MixerStatePayload) => void
  reset: () => void
}

export const useMixerStore = create<MixerState>()((set) => ({
  ...EMPTY_SNAPSHOT,
  connectionState: 'disconnected',
  linkActive: false,
  serverVersion: null,

  setConnectionState: (connectionState) => set({ connectionState }),

  setLinkActive: (linkActive) => set({ linkActive }),

  setServerVersion: (serverVersion) => set({ serverVersion }),

  applyState: (payload) =>
    set({
      connected: payload?.connected === true,
      model: normalizeText(payload?.model) || null,
      firmware: normalizeText(payload?.firmware) || null,
      updatedAt: normalizeText(payload?.updated_at) || null,
      channels: (Array.isArray(payload?.channels) ? payload.channels : [])
        .map(normalizeChannel)
        .sort((a, b) => a.index - b.index),
    }),

  reset: () =>
    set({
      ...EMPTY_SNAPSHOT,
      channels: [],
      connectionState: 'disconnected',
      linkActive: false,
      serverVersion: null,
    }),
}))

/** Número total de canales recibidos. */
export const channelCount = (state: MixerState): number => state.channels.length

/** Canales con nombre visible; el rack los muestra por defecto. */
export const namedChannels = (state: MixerState): Channel[] =>
  state.channels.filter((channel) => channel.name.trim() !== '')
