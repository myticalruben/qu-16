import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MeterBar } from '../MeterBar'

const renderFill = (levelDb: number | null): HTMLElement => {
  const { container } = render(
    <MeterBar levelDb={levelDb} label="Medidor de prueba" />,
  )
  const fill = container.querySelector<HTMLElement>('.meter-bar__fill')
  if (fill === null) throw new Error('El medidor no pintó el relleno')
  return fill
}

describe('MeterBar', () => {
  it('pinta 0 % en el suelo de −60 dB', () => {
    expect(renderFill(-60)).toHaveStyle({ height: '0%' })
  })

  it('pinta 100 % a 0 dB', () => {
    expect(renderFill(0)).toHaveStyle({ height: '100%' })
  })

  it('pinta 0 % con un nivel nulo', () => {
    expect(renderFill(null)).toHaveStyle({ height: '0%' })
  })

  it('mantiene la escala lineal en dB', () => {
    expect(renderFill(-30)).toHaveStyle({ height: '50%' })
    expect(renderFill(-12)).toHaveStyle({ height: '80%' })
  })

  it('respeta los umbrales de color verde, ámbar y rojo', () => {
    expect(renderFill(-12)).toHaveAttribute('data-zone', 'green')
    expect(renderFill(-3)).toHaveAttribute('data-zone', 'amber')
    expect(renderFill(-2.9)).toHaveAttribute('data-zone', 'red')
  })
})
