import { computed, type Ref } from 'vue'
import type { KbFolderSummary } from '../api/folders'
import type { KbBrowseCard } from '../types/kbBrowseCard'
import { isReadyDocument } from '../utils/kbUploadProgress'

export type KbBrowseSortMode = 'created_desc' | 'created_asc' | 'name_asc' | 'name_desc'

/** 与个人知识库列表 API 对齐的最小文档形状 */
export type KbBrowseListingDoc = {
  id: string
  title: string
  status: string
  created_at: string
  updated_at?: string
  folder_id?: string | null
  folder_path?: string | null
}

/** 兼容旧数据：无 folder_id 时从 folder_path / title 推断一级目录名 */
export function effectiveTopFolder<T extends Pick<KbBrowseListingDoc, 'title' | 'folder_path' | 'folder_id'>>(
  doc: T,
  foldersById?: Map<string, KbFolderSummary>,
): string | null {
  if (doc.folder_id && foldersById?.has(doc.folder_id)) {
    const f = foldersById.get(doc.folder_id)!
    if (!f.parent_id) return f.name
    const path = (f.path ?? '').replace(/\\/g, '/').trim()
    const segs = path.split('/').filter(Boolean)
    return segs[0] ?? f.name
  }
  const raw = (doc.folder_path ?? '').replace(/\\/g, '/').trim()
  if (raw) {
    const segs = raw.split('/').filter(Boolean)
    return segs[0] ?? null
  }
  const t = (doc.title || '').replace(/\\/g, '/')
  if (!t.includes('/')) return null
  const first = t.split('/')[0]
  return first || null
}

export function docBelongsToFolder<T extends KbBrowseListingDoc>(
  doc: T,
  folder: KbFolderSummary,
): boolean {
  if (doc.folder_id) {
    return doc.folder_id === folder.id
  }
  const top = effectiveTopFolder(doc)
  return top === folder.name
}

type FolderRow<TDoc> = { folder: KbFolderSummary; docs: TDoc[] }

function docTimeMs<T extends Pick<KbBrowseListingDoc, 'created_at' | 'updated_at'>>(d: T) {
  const c = new Date(d.created_at).getTime()
  const u = d.updated_at ? new Date(d.updated_at).getTime() : c
  return Math.max(c, u)
}

function formatDocLocaleTime<T extends Pick<KbBrowseListingDoc, 'created_at' | 'updated_at'>>(d: T) {
  return new Date(docTimeMs(d)).toLocaleDateString('zh-CN')
}

/** 文件夹卡片日期：有文档用最新文档时间，空夹用服务端 created_at */
function folderDisplayTimeMs(folder: KbFolderSummary, docs: KbBrowseListingDoc[]): number | null {
  if (docs.length) {
    return Math.max(...docs.map((d) => docTimeMs(d)))
  }
  const created = new Date(folder.created_at).getTime()
  return Number.isNaN(created) ? null : created
}

function formatFolderCardTime(folder: KbFolderSummary, docs: KbBrowseListingDoc[]): string {
  const ms = folderDisplayTimeMs(folder, docs)
  if (ms == null) return '-'
  return new Date(ms).toLocaleDateString('zh-CN')
}

export function useKbBrowseListing<TDoc extends KbBrowseListingDoc>(
  documents: Ref<TDoc[]>,
  kbFolders: Ref<KbFolderSummary[]>,
  selectedFolderId: Ref<string | null>,
  searchQuery: Ref<string>,
  sortMode: Ref<KbBrowseSortMode>,
) {
  const readyDocuments = computed(() => documents.value.filter(isReadyDocument))

  const foldersById = computed(() => new Map(kbFolders.value.map((f) => [f.id, f])))

  const rootFolders = computed(() => kbFolders.value.filter((f) => !f.parent_id))

  /** 当前层级下的子文件夹（根目录为 parent_id 为空） */
  const foldersAtCurrentLevel = computed(() => {
    const pid = selectedFolderId.value
    if (!pid) return rootFolders.value
    return kbFolders.value.filter((f) => f.parent_id === pid)
  })

  const folderItems = computed<FolderRow<TDoc>[]>(() =>
    rootFolders.value.map((folder) => ({
      folder,
      docs: readyDocuments.value.filter((doc) => docBelongsToFolder(doc, folder)),
    })),
  )

  function directDocsInFolder(folderId: string) {
    return readyDocuments.value.filter((doc) => doc.folder_id === folderId)
  }

  function childFolderCount(folderId: string) {
    return kbFolders.value.filter((f) => f.parent_id === folderId).length
  }

  function folderCardSizeLabel(folderId: string, docs: TDoc[]) {
    const sub = childFolderCount(folderId)
    const n = docs.length
    if (sub && n) return `${sub}夹 · ${n}项`
    if (sub) return `${sub}个文件夹`
    return `${n}项`
  }

  const selectedFolder = computed(() =>
    selectedFolderId.value ? foldersById.value.get(selectedFolderId.value) ?? null : null,
  )

  const filteredDocsByFolder = computed(() => {
    if (!selectedFolderId.value) return [] as TDoc[]
    return directDocsInFolder(selectedFolderId.value)
  })

  const buildFolderCards = (folders: KbFolderSummary[]) =>
    folders
      .map((folder) => ({
        folder,
        docs: directDocsInFolder(folder.id),
      }))
      .filter(({ folder }) => {
        const keyword = searchQuery.value.trim().toLowerCase()
        if (!keyword) return true
        return folder.name.toLowerCase().includes(keyword)
      })
      .sort((a, b) => {
        const aTs = folderDisplayTimeMs(a.folder, a.docs) ?? 0
        const bTs = folderDisplayTimeMs(b.folder, b.docs) ?? 0
        if (sortMode.value === 'created_desc') {
          return bTs - aTs
        }
        if (sortMode.value === 'created_asc') {
          return aTs - bTs
        }
        if (sortMode.value === 'name_asc') {
          return a.folder.name.localeCompare(b.folder.name, 'zh-CN')
        }
        return b.folder.name.localeCompare(a.folder.name, 'zh-CN')
      })
      .map(({ folder, docs }) => ({
        id: `folder-${folder.id}`,
        kind: 'folder' as const,
        name: folder.name,
        type: 'folder' as const,
        typeLabel: '',
        size: folderCardSizeLabel(folder.id, docs),
        updatedAt: formatFolderCardTime(folder, docs),
        folderId: folder.id,
      }))

  const folderCards = computed<KbBrowseCard[]>(() => buildFolderCards(rootFolders.value))

  const subfolderCards = computed<KbBrowseCard[]>(() =>
    selectedFolderId.value ? buildFolderCards(foldersAtCurrentLevel.value) : [],
  )

  const docCards = computed<KbBrowseCard[]>(() =>
    filteredDocsByFolder.value
      .filter((doc) => {
        const keyword = searchQuery.value.trim().toLowerCase()
        if (!keyword) return true
        const hay = `${(doc.folder_path || '').toLowerCase()}\n${doc.title.toLowerCase()}`
        return hay.includes(keyword)
      })
      .sort((a, b) => {
        if (sortMode.value === 'created_desc') {
          return docTimeMs(b) - docTimeMs(a)
        }
        if (sortMode.value === 'created_asc') {
          return docTimeMs(a) - docTimeMs(b)
        }
        if (sortMode.value === 'name_asc') {
          return a.title.localeCompare(b.title, 'zh-CN')
        }
        return b.title.localeCompare(a.title, 'zh-CN')
      })
      .map((doc) => {
        const lower = doc.title.toLowerCase()
        const isPdf = true
        const isWord = lower.endsWith('.docx') || lower.endsWith('.doc')
        const type = isPdf ? ('pdf' as const) : isWord ? ('word' as const) : ('file' as const)
        return {
          id: doc.id,
          kind: 'file' as const,
          name: doc.title,
          type,
          typeLabel: isPdf ? 'PDF' : isWord ? 'Word' : '文档',
          size: '',
          updatedAt: formatDocLocaleTime(doc),
          docId: doc.id,
        }
      }),
  )

  const rootFileCards = computed<KbBrowseCard[]>(() =>
    readyDocuments.value
      .filter((doc) => !doc.folder_id && !effectiveTopFolder(doc, foldersById.value))
      .filter((doc) => {
        const keyword = searchQuery.value.trim().toLowerCase()
        if (!keyword) return true
        const hay = `${(doc.folder_path || '').toLowerCase()}\n${doc.title.toLowerCase()}`
        return hay.includes(keyword)
      })
      .sort((a, b) => {
        if (sortMode.value === 'created_desc') {
          return docTimeMs(b) - docTimeMs(a)
        }
        if (sortMode.value === 'created_asc') {
          return docTimeMs(a) - docTimeMs(b)
        }
        if (sortMode.value === 'name_asc') {
          return a.title.localeCompare(b.title, 'zh-CN')
        }
        return b.title.localeCompare(a.title, 'zh-CN')
      })
      .map((doc) => {
        const lower = doc.title.toLowerCase()
        const isPdf = true
        const isWord = lower.endsWith('.docx') || lower.endsWith('.doc')
        const type = isPdf ? ('pdf' as const) : isWord ? ('word' as const) : ('file' as const)
        return {
          id: `root-${doc.id}`,
          kind: 'file' as const,
          name: doc.title,
          type,
          typeLabel: isPdf ? 'PDF' : isWord ? 'Word' : '文档',
          size: '',
          updatedAt: formatDocLocaleTime(doc),
          docId: doc.id,
        }
      }),
  )

  const visibleCards = computed<KbBrowseCard[]>(() => {
    if (selectedFolderId.value) {
      return [...subfolderCards.value, ...docCards.value]
    }
    return [...folderCards.value, ...rootFileCards.value]
  })

  return {
    folderItems,
    selectedFolder,
    filteredDocsByFolder,
    folderCards,
    subfolderCards,
    docCards,
    rootFileCards,
    visibleCards,
    directDocsInFolder,
    childFolderCount,
  }
}
