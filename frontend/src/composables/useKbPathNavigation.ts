import { computed, ref, type Ref } from 'vue'
import type { KbFolderSummary } from '../api/folders'

export type PathCrumb = {
  /** null 表示知识库根 */
  folderId: string | null
  label: string
}

export function buildFolderCrumbs(
  kbName: string,
  folderId: string | null,
  folders: readonly KbFolderSummary[],
): PathCrumb[] {
  const byId = new Map(folders.map((f) => [f.id, f]))
  const crumbs: PathCrumb[] = [{ folderId: null, label: kbName || '知识库' }]
  if (!folderId) return crumbs

  const chain: KbFolderSummary[] = []
  let cur: KbFolderSummary | undefined = byId.get(folderId)
  while (cur) {
    chain.unshift(cur)
    cur = cur.parent_id ? byId.get(cur.parent_id) : undefined
  }
  for (const f of chain) {
    crumbs.push({ folderId: f.id, label: f.name })
  }
  return crumbs
}

/**
 * 文件夹浏览历史：支持后退 / 前进（与面包屑点击共用同一 folderId 栈）。
 */
export function useKbPathNavigation(
  selectedFolderId: Ref<string | null>,
  kbFolders: Ref<KbFolderSummary[]>,
  kbName: Ref<string | null | undefined>,
) {
  const history = ref<(string | null)[]>([null])
  const historyIndex = ref(0)

  const crumbs = computed(() =>
    buildFolderCrumbs(kbName.value || '知识库', selectedFolderId.value, kbFolders.value),
  )

  const canGoBack = computed(() => historyIndex.value > 0)
  const canGoForward = computed(() => historyIndex.value < history.value.length - 1)

  const applyFolderId = (folderId: string | null) => {
    selectedFolderId.value = folderId
  }

  const resetHistory = (folderId: string | null = null) => {
    history.value = [folderId]
    historyIndex.value = 0
    applyFolderId(folderId)
  }

  const navigateTo = (folderId: string | null) => {
    if (selectedFolderId.value === folderId && history.value[historyIndex.value] === folderId) {
      return
    }
    const trimmed = history.value.slice(0, historyIndex.value + 1)
    trimmed.push(folderId)
    history.value = trimmed
    historyIndex.value = trimmed.length - 1
    applyFolderId(folderId)
  }

  const navigateToCrumb = (crumb: PathCrumb) => {
    navigateTo(crumb.folderId)
  }

  const goBack = () => {
    if (!canGoBack.value) return
    historyIndex.value -= 1
    applyFolderId(history.value[historyIndex.value] ?? null)
  }

  const goForward = () => {
    if (!canGoForward.value) return
    historyIndex.value += 1
    applyFolderId(history.value[historyIndex.value] ?? null)
  }

  return {
    crumbs,
    canGoBack,
    canGoForward,
    resetHistory,
    navigateTo,
    navigateToCrumb,
    goBack,
    goForward,
  }
}
