import { http } from './http'

export type KnowledgeBase = { id: string; name: string; created_at: string }

export async function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  const res = await http.get('/api/v1/knowledge-bases')
  return (res.data?.data?.items || []) as KnowledgeBase[]
}

export async function createKnowledgeBase(name: string, description = ''): Promise<KnowledgeBase> {
  const res = await http.post('/api/v1/knowledge-bases', { name, description })
  const raw = res.data?.data as Partial<KnowledgeBase> | undefined
  if (!raw?.id) {
    throw new Error('创建知识库失败')
  }
  return {
    id: raw.id,
    name: raw.name ?? name,
    created_at: raw.created_at ?? '',
  }
}

export async function renameKnowledgeBase(kbId: string, name: string): Promise<KnowledgeBase> {
  const res = await http.patch(`/api/v1/knowledge-bases/${kbId}`, { name })
  const raw = res.data?.data as Partial<KnowledgeBase> | undefined
  if (!raw?.id) {
    throw new Error('重命名知识库失败')
  }
  return {
    id: raw.id,
    name: raw.name ?? name,
    created_at: raw.created_at ?? '',
  }
}

export async function deleteKnowledgeBase(kbId: string): Promise<void> {
  await http.delete(`/api/v1/knowledge-bases/${kbId}`)
}

