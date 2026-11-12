import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Con `globals: true` Testing Library ya limpia, pero lo hacemos explícito
// para que el comportamiento no dependa de la configuración global.
afterEach(() => {
  cleanup()
})
