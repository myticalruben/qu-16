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

const REQUEST_TIMEOUT_MS = 5_000

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS)
  const response = await fetch(path, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal: signal ?? timeout,
  })

  if (!response.ok) {
    throw new ApiError(
      `El backend respondió ${response.status} en ${path}`,
      response.status,
    )
  }

  return (await response.json()) as T
}

/** Estado del proceso backend y de su enlace con la mesa. */
export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson<HealthResponse>('/api/health', signal)
}

/** Volcado resumido de la mesa: modelo, firmware y canales. */
export function getMixerStatus(signal?: AbortSignal): Promise<MixerStatusResponse> {
  return getJson<MixerStatusResponse>('/api/mixer/status', signal)
}
