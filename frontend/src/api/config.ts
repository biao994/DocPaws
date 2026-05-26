export function normalizeBaseUrl(raw: string | undefined | null): string {
  const s = (raw ?? '').trim()
  if (!s) return ''
  return s.endsWith('/') ? s.slice(0, -1) : s
}

/**
 * 可选：当本地开发不走 Vite proxy 时，提供直连后端的 baseUrl。
 * - 不配置时：默认使用相对路径（例如 /api/v1/...），交给 Vite proxy 处理。
 * - 配置时：会把相对路径拼成绝对地址（例如 http://127.0.0.1:8001/api/v1/...）。
 */
export const API_BASE_URL = normalizeBaseUrl(import.meta.env?.VITE_API_BASE_URL)

export function withApiBase(path: string): string {
  if (!API_BASE_URL) return path
  if (/^https?:\/\//i.test(path)) return path
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

