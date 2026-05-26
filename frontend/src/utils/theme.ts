export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'docpaws-theme'

export function getStoredTheme(): ThemeMode {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (raw === 'light' || raw === 'dark' || raw === 'system') return raw
  return 'system'
}

export function applyTheme(mode: ThemeMode) {
  const root = document.documentElement
  if (mode === 'system') {
    root.removeAttribute('data-theme')
    localStorage.setItem(STORAGE_KEY, 'system')
  } else {
    root.setAttribute('data-theme', mode)
    localStorage.setItem(STORAGE_KEY, mode)
  }
  window.dispatchEvent(new CustomEvent('docpaws:theme-changed', { detail: { mode } }))
}

export function initThemeFromStorage() {
  applyTheme(getStoredTheme())
}

