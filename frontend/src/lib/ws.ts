import { useMixerStore } from '../store/mixer'

/**
 * Cliente WebSocket de la consola. Mantiene una única conexión y reintenta con
 * retroceso exponencial simple (1 s, 2 s, 4 s, ... hasta 30 s).
 *
 * No se conecta automáticamente: la Fase 1 debe arrancar en estado
 * `disconnected` aunque el backend no esté levantado. La cabecera ofrece un
 * botón para iniciar el enlace cuando el usuario quiera.
 */

const BASE_RECONNECT_MS = 1_000
const MAX_RECONNECT_MS = 30_000
const JITTER_MS = 250

let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let reconnectAttempt = 0
let active = false

interface HelloMessage {
  serverVersion?: string
  server_version?: string
  version?: string
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

/** Busca la primera cadena no vacía entre varias claves posibles. */
function readString(
  record: Record<string, unknown>,
  keys: string[],
): string | null {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'string' && value.trim() !== '') {
      return value.trim()
    }
  }
  return null
}

function resolveSocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws`
}

function scheduleReconnect(): void {
  if (!active || reconnectTimer !== null) return

  const backoff = Math.min(
    BASE_RECONNECT_MS * 2 ** reconnectAttempt,
    MAX_RECONNECT_MS,
  )
  const delay = backoff + Math.round(Math.random() * JITTER_MS)
  reconnectAttempt += 1

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    openSocket()
  }, delay)
}

function handleMessage(raw: unknown): void {
  if (typeof raw !== 'string') return

  let payload: unknown
  try {
    payload = JSON.parse(raw)
  } catch {
    // Un mensaje que no sea JSON se ignora: la Fase 0 usa binario en la mesa,
    // pero el puente web del backend habla JSON.
    return
  }

  if (!isRecord(payload) || payload.type !== 'hello') return

  const hello = payload as HelloMessage & Record<string, unknown>
  const version = readString(hello, [
    'serverVersion',
    'server_version',
    'version',
  ])
  const store = useMixerStore.getState()

  // Solo un saludo completo confirma el enlace y reinicia el retroceso.
  reconnectAttempt = 0
  store.setConnectionState('connected')
  if (version !== null) {
    store.setServerVersion(version.replace(/^v/i, ''))
  }
}

function openSocket(): void {
  if (!active) return

  useMixerStore.getState().setConnectionState('connecting')

  try {
    socket = new WebSocket(resolveSocketUrl())
  } catch {
    scheduleReconnect()
    return
  }

  socket.onopen = () => {
    // El enlace no se da por bueno hasta recibir `hello`; si el servidor
    // acepta y cierra sin saludar, el retroceso sigue creciendo.
    useMixerStore.getState().setConnectionState('connecting')
  }

  socket.onmessage = (event) => {
    handleMessage(event.data)
  }

  socket.onerror = () => {
    // El navegador ya registra el fallo de red; `onclose` se encarga del
    // reintento y de no inundar la consola con errores propios.
  }

  socket.onclose = () => {
    socket = null

    if (!active) {
      useMixerStore.getState().setConnectionState('disconnected')
      return
    }

    // Seguimos intentándolo: la insignia permanece en «Conectando…» y el
    // botón de la cabecera permite cancelar.
    useMixerStore.getState().setConnectionState('connecting')
    scheduleReconnect()
  }
}

/** Abre el enlace (o lo reintenta) hasta que el usuario lo cancele. */
export function connectMixerSocket(): void {
  if (typeof window === 'undefined' || typeof WebSocket === 'undefined') return
  if (active) return

  active = true
  reconnectAttempt = 0
  openSocket()
}

/** Cierra el enlace y detiene los reintentos. */
export function disconnectMixerSocket(): void {
  active = false

  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  const current = socket
  socket = null

  if (current !== null) {
    current.onopen = null
    current.onmessage = null
    current.onerror = null
    current.onclose = null

    if (
      current.readyState === WebSocket.OPEN ||
      current.readyState === WebSocket.CONNECTING
    ) {
      current.close()
    }
  }

  useMixerStore.getState().setConnectionState('disconnected')
}

/** Expuesto para depuración manual desde la consola del navegador. */
export const mixerSocket = {
  connect: connectMixerSocket,
  disconnect: disconnectMixerSocket,
}
