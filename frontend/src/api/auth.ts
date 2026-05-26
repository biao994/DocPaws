import { http } from './http'

export type UserMe = {
  id: string
  email: string
  username: string
}

export async function fetchMe(): Promise<UserMe> {
  const r = await http.get('/api/v1/users/me')
  return r.data.data as UserMe
}

export async function login(email: string, password: string): Promise<UserMe> {
  const r = await http.post('/api/v1/auth/login', { email, password })
  return r.data.data as UserMe
}

export async function register(
  email: string,
  username: string,
  password: string,
): Promise<UserMe> {
  const r = await http.post('/api/v1/auth/register', { email, username, password })
  return r.data.data as UserMe
}

export async function logout(): Promise<void> {
  await http.post('/api/v1/auth/logout')
}
