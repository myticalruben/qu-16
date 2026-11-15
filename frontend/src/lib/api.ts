/**
 * Cliente HTTP tipado del backend. El backend de la Fase 1 todavía puede no
 * estar levantado: `getHealth` y `getMixerStatus` rechazan con un error claro
 * y la UI decide si lo muestra o lo ignora.
 */

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error' | string
  version?: string
  mixer_connected?: boolean
  uptime_s?: number
}

export interface MixerChannelStatus {
  id: number
  name: string
  fader_db?: number
  level?: number
  muted?: boolean
}

export interface MixerStatusResponse {
  connected: boolean
  model?: string
  firmware?: string
  server_version?: string
  sample_rate?: number
  channels?: MixerChannelStatus[]
}

/** Permiso de escritura que publica el backend para la mesa real. */
export interface MixerConfigResponse {
  write_enabled: boolean
  model: string | null
  connected: boolean
}

/** Respuesta del POST de nivel, ya normalizada. */
export interface ChannelLevelResponse {
  index: number
  value: number | null
  db: number | null
}

const REQUEST_TIMEOUT_MS = 5_000

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Solo se crea un temporizador cuando el llamante no aporta su propio
 * `AbortSignal`; así los componentes pueden cancelar al desmontarse sin dejar
 * un timeout pendiente.
 */
function requestSignal(signal?: AbortSignal): AbortSignal {
  return signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS)
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal: requestSignal(signal),
  })

  if (!response.ok) {
    throw new ApiError(
      `El backend respondió ${response.status} en ${path}`,
      response.status,
    )
  }

  return (await response.json()) as T
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

const readNumber = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null

/** Estado del proceso backend y de su enlace con la mesa. */
export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson<HealthResponse>('/api/health', signal)
}

/** Volcado resumido de la mesa: modelo, firmware y canales. */
export function getMixerStatus(signal?: AbortSignal): Promise<MixerStatusResponse> {
  return getJson<MixerStatusResponse>('/api/mixer/status', signal)
}

/**
 * Permiso de escritura del backend. Un campo corrupto se degrada a «sin
 * permiso»: el candado de la consola nunca se abre por accidente.
 */
export async function getMixerConfig(
  signal?: AbortSignal,
): Promise<MixerConfigResponse> {
  const payload = await getJson<unknown>('/api/mixer/config', signal)
  const record = isRecord(payload) ? payload : {}

  return {
    write_enabled: record.write_enabled === true,
    model: typeof record.model === 'string' ? record.model : null,
    connected: record.connected === true,
  }
}

/**
 * Envía el nivel del fader en dB. El backend devuelve 409 si la escritura está
 * deshabilitada, 404 si el índice no existe y 422 si la petición no es válida;
 * `ApiError.status` permite distinguirlos en la UI.
 */
export async function writeChannelLevel(
  index: number,
  db: number,
  signal?: AbortSignal,
): Promise<ChannelLevelResponse> {
  const path = `/api/mixer/channels/${index}/level`
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ db }),
    signal: requestSignal(signal),
  })

  if (!response.ok) {
    throw new ApiError(
      `El backend respondió ${response.status} en ${path}`,
      response.status,
    )
  }

  const payload: unknown = await response.json()
  const record = isRecord(payload) ? payload : {}

  return {
    index: readNumber(record.index) ?? index,
    value: readNumber(record.value),
    db: readNumber(record.db),
  }
}
