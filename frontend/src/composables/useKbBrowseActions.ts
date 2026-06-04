import type { Ref } from 'vue'

import { deleteKbFolder, renameKbFolder, type KbFolderSummary } from '../api/folders'
import { deleteDocument, downloadDocumentBlob, renameDocument } from '../api/documents'
import type { KbBrowseListingDoc } from './useKbBrowseListing'
import type { KbBrowseCard } from '../types/kbBrowseCard'

type KbRef = Ref<{ id: string; name: string } | null>
type DocRef = Ref<KbBrowseListingDoc | null>

export type UseKbBrowseActionsOptions = {
  selectedKb: KbRef
  selectedFolderId: Ref<string | null>
  selectedDoc: DocRef
  previewDoc: DocRef
  showPreviewModal: Ref<boolean>
  kbFolders: Ref<KbFolderSummary[]>
  documents: Ref<KbBrowseListingDoc[]>
  directDocsInFolder: (folderId: string) => KbBrowseListingDoc[]
  pathNavigateTo: (folderId: string | null) => void
  loadDocuments: () => Promise<void>
  loadFolders: () => Promise<void>
  markKbSessionsStale: () => void
}

export function useKbBrowseActions(options: UseKbBrowseActionsOptions) {
  const {
    selectedKb,
    selectedFolderId,
    selectedDoc,
    previewDoc,
    showPreviewModal,
    kbFolders,
    documents,
    directDocsInFolder,
    pathNavigateTo,
    loadDocuments,
    loadFolders,
    markKbSessionsStale,
  } = options

  const renameItem = async (item: KbBrowseCard) => {
    const newName = prompt('请输入新名称', item.name)?.trim()
    if (!newName) return
    try {
      if (item.kind === 'file' && item.docId) {
        await renameDocument(item.docId, newName)
      } else if (item.kind === 'folder' && item.folderId && selectedKb.value) {
        await renameKbFolder(selectedKb.value.id, item.folderId, newName)
        if (selectedFolderId.value === item.folderId) {
          await loadFolders()
        }
      }
      await loadDocuments()
    } catch (error) {
      console.error('Rename failed:', error)
      alert('重命名失败')
    }
  }

  const deleteDoc = async (docId: string) => {
    if (!confirm('确定删除该文件吗？')) return
    try {
      await deleteDocument(docId)
      await loadDocuments()
      if (selectedDoc.value?.id === docId) {
        selectedDoc.value = null
      }
      if (previewDoc.value?.id === docId) {
        showPreviewModal.value = false
        previewDoc.value = null
        markKbSessionsStale()
      }
    } catch (error) {
      console.error('Delete failed:', error)
      alert('删除失败，请稍后重试')
    }
  }

  const deleteItem = async (item: KbBrowseCard) => {
    if (item.kind === 'file' && item.docId) {
      await deleteDoc(item.docId)
      return
    }
    if (!item.folderId || !selectedKb.value) return
    const docsInFolder = directDocsInFolder(item.folderId)
    if (docsInFolder.length > 0) {
      if (!confirm(`确定删除文件夹“${item.name}”及其 ${docsInFolder.length} 个文件吗？`)) return
      try {
        for (const doc of docsInFolder) {
          await deleteDocument(doc.id)
        }
      } catch (error) {
        console.error('Delete folder files failed:', error)
        alert('删除文件失败')
        return
      }
    } else if (!confirm(`确定删除空文件夹“${item.name}”吗？`)) {
      return
    }
    try {
      await deleteKbFolder(selectedKb.value.id, item.folderId)
      if (selectedFolderId.value === item.folderId) {
        const deleted = kbFolders.value.find((f) => f.id === item.folderId)
        pathNavigateTo(deleted?.parent_id ?? null)
        selectedDoc.value = null
      }
      await loadDocuments()
    } catch (error) {
      console.error('Delete folder failed:', error)
      alert('删除文件夹失败')
    }
  }

  const downloadDoc = async (docId: string) => {
    try {
      const res = await downloadDocumentBlob(docId)
      const blobUrl = window.URL.createObjectURL(res.data)
      const link = document.createElement('a')
      const matched = documents.value.find((d) => d.id === docId)
      link.href = blobUrl
      link.download = `${matched?.title || 'document'}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(blobUrl)
    } catch (error) {
      console.error('Download failed:', error)
      alert('下载失败，请稍后重试')
    }
  }

  return { renameItem, deleteItem, deleteDoc, downloadDoc }
}
