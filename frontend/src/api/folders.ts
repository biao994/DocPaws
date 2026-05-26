import { http } from './http'

export type KbFolderSummary = {
  id: string
  kb_id: string
  parent_id: string | null
  name: string
  path: string | null
  created_at: string
  updated_at: string
}

export async function listKbFolders(kbId: string): Promise<KbFolderSummary[]> {
  const res = await http.get(`/api/v1/knowledge-bases/${kbId}/folders`)
  return (res.data?.data?.items || []) as KbFolderSummary[]
}

export async function createKbFolder(
  kbId: string,
  body: { name: string; parent_id?: string | null },
): Promise<KbFolderSummary> {
  const res = await http.post(`/api/v1/knowledge-bases/${kbId}/folders`, body)
  return res.data?.data as KbFolderSummary
}

export async function renameKbFolder(
  kbId: string,
  folderId: string,
  name: string,
): Promise<KbFolderSummary> {
  const res = await http.patch(`/api/v1/knowledge-bases/${kbId}/folders/${folderId}`, { name })
  return res.data?.data as KbFolderSummary
}

export async function deleteKbFolder(kbId: string, folderId: string) {
  return await http.delete(`/api/v1/knowledge-bases/${kbId}/folders/${folderId}`)
}
