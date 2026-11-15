import { create } from 'zustand'

import type { MixerConfigResponse } from '../lib/api'

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
  /**
   * Candado de escritura. Arranca apagado y no se persiste: cada recarga
   * obliga a confirmar otra vez que se va a mover la mesa real.
   */
  controlEnabled: boolean
  /** `true` mientras el diálogo de confirmación está abierto. */
  controlPending: boolean
  /** Permiso publicado por `GET /api/mixer/config`; `null` = aún sin leer. */
  writeConfig: MixerConfigResponse | null
  /** Último fallo de escritura, para el aviso efímero. */
  lastError: string | null
  /** Canales que se están arrastrando: el WS no debe pisar su nivel. */
  draggingChannels: number[]
  setConnectionState: (state: ConnectionState) => void
  setLinkActive: (active: boolean) => void
  setServerVersion: (version: string | null) => void
  /** Guarda el permiso del backend; si viene denegado, cierra el candado. */
  setWriteConfig: (config: MixerConfigResponse | null) => void
  /** Abre o cierra el candado. Nunca se abre sin permiso del servidor. */
  setControlEnabled: (enabled: boolean) => void
  setControlPending: (pending: boolean) => void
  /** Registra el aviso de error; el componente lo descarta a los 4 s. */
  setLastError: (message: string | null) => void
  clearError: () => void
  /** Marca/desmarca un canal en arrastre para aislarlo del WS. */
  beginChannelDrag: (index: number) => void
  endChannelDrag: (index: number) => void
  /** Aplica el nivel optimista del fader sin esperar al backend. */
  setChannelLevelDb: (index: number, levelDb: number | null) => void
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
  controlEnabled: false,
  controlPending: false,
  writeConfig: null,
  lastError: null,
  draggingChannels: [],

  setConnectionState: (connectionState) => set({ connectionState }),

  setLinkActive: (linkActive) => set({ linkActive }),

  setServerVersion: (serverVersion) => set({ serverVersion }),

  setWriteConfig: (writeConfig) =>
    set((state) => ({
      writeConfig,
      // Si el servidor retira el permiso, el candado se cierra de inmediato.
      controlEnabled:
        writeConfig?.write_enabled === true ? state.controlEnabled : false,
      controlPending:
        writeConfig?.write_enabled === true ? state.controlPending : false,
    })),

  setControlEnabled: (enabled) =>
    set((state) => ({
      controlEnabled: enabled && state.writeConfig?.write_enabled === true,
      controlPending: false,
    })),

  setControlPending: (controlPending) => set({ controlPending }),

  setLastError: (lastError) => set({ lastError }),

  clearError: () => set({ lastError: null }),

  beginChannelDrag: (index) =>
    set((state) =>
      state.draggingChannels.includes(index)
        ? state
        : { draggingChannels: [...state.draggingChannels, index] },
    ),

  endChannelDrag: (index) =>
    set((state) => ({
      draggingChannels: state.draggingChannels.filter(
        (dragged) => dragged !== index,
      ),
    })),

  setChannelLevelDb: (index, levelDb) => {
    const current = get().channels
    const target = current.find((channel) => channel.index === index)
    if (target === undefined || target.levelDb === levelDb) return

    set({
      channels: current.map((channel) =>
        channel.index === index ? { ...channel, levelDb } : channel,
      ),
    })
  },

  applyState: (payload) => {
    const dragging = get().draggingChannels
    const previous = get().channels
    const nextChannels = (Array.isArray(payload?.channels) ? payload.channels : [])
      .map(normalizeChannel)
      .sort((a, b) => a.index - b.index)

    // Mientras el operador arrastra, el sondeo del backend puede devolver el
    // nivel anterior. Se conserva la tira que el usuario tiene en la mano para
    // que el fader no salte bajo el dedo; el resto del volcado sí se aplica.
    const guardedChannels =
      dragging.length === 0
        ? nextChannels
        : nextChannels.map((channel) => {
            if (!dragging.includes(channel.index)) return channel
            const current = previous.find((item) => item.index === channel.index)
            return current ?? channel
          })

    set({
      connected: payload?.connected === true,
      model: normalizeText(payload?.model) || null,
      firmware: normalizeText(payload?.firmware) || null,
      updatedAt: normalizeText(payload?.updated_at) || null,
      channels: guardedChannels,
    })
  },

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
      controlEnabled: false,
      controlPending: false,
      writeConfig: null,
      lastError: null,
      draggingChannels: [],
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
