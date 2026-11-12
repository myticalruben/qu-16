import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ConnectionBadge } from '../ConnectionBadge'

describe('ConnectionBadge', () => {
  it('muestra el estado desconectado', () => {
    render(<ConnectionBadge state="disconnected" />)

    expect(screen.getByText('Desconectado')).toBeInTheDocument()
    expect(
      screen.getByRole('status', { name: 'Enlace: Desconectado' }),
    ).toBeInTheDocument()
  })

  it('muestra el estado conectando', () => {
    render(<ConnectionBadge state="connecting" />)

    expect(screen.getByText('Conectando…')).toBeInTheDocument()
    expect(screen.queryByText('Conectado')).not.toBeInTheDocument()
  })

  it('muestra el estado conectado y la versión del servidor', () => {
    render(<ConnectionBadge state="connected" serverVersion="0.1.0" />)

    expect(screen.getByText('Conectado')).toBeInTheDocument()
    expect(screen.getByText('v0.1.0')).toBeInTheDocument()
  })

  it('no muestra versión si aún no se recibió hello', () => {
    render(<ConnectionBadge state="connected" />)

    expect(screen.getByText('Conectado')).toBeInTheDocument()
    expect(screen.queryByText(/^v\d/)).not.toBeInTheDocument()
  })
})
