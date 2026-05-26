import axios from 'axios'

import { clearSession } from '../auth/session'
import { API_BASE_URL } from './config'

export const http = axios.create({
  baseURL: API_BASE_URL || undefined,
  withCredentials: true,
})

http.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status !== 401) return Promise.reject(err)

    const url = String(err.config?.url ?? '')

    if (url.includes('/auth/login') || url.includes('/auth/register')) {
      return Promise.reject(err)
    }

    if (url.includes('/users/me')) {
      clearSession()
      return Promise.reject(err)
    }

    clearSession()
    window.dispatchEvent(new CustomEvent('docpaws:unauthorized'))
    return Promise.reject(err)
  },
)
