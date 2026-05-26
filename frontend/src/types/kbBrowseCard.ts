/** 个人知识库文件/文件夹浏览卡片（网格与列表共用） */
export type KbBrowseCard = {
  id: string
  kind: 'folder' | 'file'
  name: string
  type: 'folder' | 'pdf' | 'word' | 'file'
  typeLabel: string
  size: string
  updatedAt: string
  docId?: string
  folderId?: string
}
