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

/**
 * Los medidores llegan a 20 Hz y con huecos (`undefined`) cuando el backend
 * omite canales. Cada posición inválida se degrada a `null`, que la UI pinta
 * como silencio; así la lista conserva la correspondencia índice → canal.
 */
function normalizeLevels(value: unknown): (number | null)[] {
  if (!Array.isArray(value)) return []
  return Array.from(value, (level) => (isFiniteNumber(level) ? level : null))
}

/** Evita notificar a los suscriptores si el mensaje no cambió ningún nivel. */
function sameLevels(
  current: (number | null)[],
  next: (number | null)[],
): boolean {
  if (current.length !== next.length) return false
  for (let index = 0; index < current.length; index += 1) {
    if (current[index] !== next[index]) return false
  }
  return true
}

export interface MixerState extends MixerSnapshot {
  /** Estado del socket con el backend, que no es lo mismo que la mesa. */
  connectionState: ConnectionState
  /** `true` mientras el usuario mantiene el enlace abierto (aunque reintente). */
  linkActive: boolean
  serverVersion: string | null
  /**
   * Últimos niveles de medidor en dB, indexados por `Channel.index`.
   * No forma parte del volcado `state`: se refresca con cada mensaje `meters`.
   */
  levels: (number | null)[]
  setConnectionState: (state: ConnectionState) => void
  setLinkActive: (active: boolean) => void
  setServerVersion: (version: string | null) => void
  /** Aplica un mensaje `state`: normaliza snake_case, ordena y guarda. */
  applyState: (payload: MixerStatePayload) => void
  /**
   * Sustituye la lista completa de medidores. Si los valores son idénticos no
   * toca el estado, de modo que 20 mensajes/s con canales en silencio no
   * despiertan a ningún suscriptor.
   */
  applyMeters: (levels: unknown) => void
  /** Nivel de medidor de un canal; `null` si aún no llegó o está en silencio. */
  levelFor: (index: number) => number | null
  reset: () => void
}

export const useMixerStore = create<MixerState>()((set, get) => ({
  ...EMPTY_SNAPSHOT,
  connectionState: 'disconnected',
  linkActive: false,
  serverVersion: null,
  levels: [],

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

  applyMeters: (levels) => {
    const next = normalizeLevels(levels)
    if (sameLevels(get().levels, next)) return
    set({ levels: next })
  },

  levelFor: (index) => get().levels[index] ?? null,

  reset: () =>
    set({
      ...EMPTY_SNAPSHOT,
      channels: [],
      levels: [],
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

/**
 * Selector puro de nivel de medidor. Acepta `levelFor(state, index)` para
 * suscribirse por canal con Zustand y `levelFor(index)` contra el estado
 * actual, que resulta cómodo en tests y en la consola del navegador.
 */
export function levelFor(index: number): number | null
export function levelFor(state: MixerState, index: number): number | null
export function levelFor(
  stateOrIndex: MixerState | number,
  maybeIndex?: number,
): number | null {
  if (typeof stateOrIndex === 'number') {
    return useMixerStore.getState().levels[stateOrIndex] ?? null
  }
  return maybeIndex === undefined
    ? null
    : (stateOrIndex.levels[maybeIndex] ?? null)
}
