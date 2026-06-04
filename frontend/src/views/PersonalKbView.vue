<template>
  <div class="page-root" :class="{ 'is-file-reader': showPreviewModal }">
    <PersonalKbTopBar
      v-if="!showPreviewModal"
      :settings-open="showSettings"
      :display-name="kbUserDisplayName"
      @toggle-settings="toggleSettings"
      @navigate-home="goHome"
      @logout="handleLogout"
    />

    <!-- 主布局 -->
    <div class="main-container">
      <KbSidebarTree
        v-if="!showPreviewModal"
        :collapsed="middleCollapsed"
        :knowledge-bases="personalKbs"
        :selected-kb-id="selectedKb?.id ?? null"
        :selected-folder-id="selectedFolderId"
        :current-kb-label="selectedKb?.name"
        @toggle-collapse="toggleMiddleSidebar"
        @select-kb="selectKbFromSidebar"
        @create-kb="openCreateKbModal"
        @rename-kb="renameKbFromSidebar"
        @delete-kb="deleteKbFromSidebar"
      />

      <!-- 右侧内容区（文件网格 + AI 输入栏） -->
      <div class="content-area">
        <PdfReaderWithChat
          v-if="showPreviewModal && previewDoc"
          v-model="modalInput"
          :pdf-src="getPdfReaderSrc(previewDoc.id)"
          :document-title="previewDoc.title"
          :messages="modalMessages"
          :is-streaming="modalIsStreaming"
          :pending-assistant-id="modalStreamingAssistantId"
          :composer-placeholder="modalInputPlaceholder"
          @close="closePreviewModal"
          @send="sendModalQuestion"
          @attachment="openAttachmentDialog"
        />
        <PersonalKbBrowsePane
          v-else
          v-model:search-query="searchQuery"
          v-model:composer-input="questionInput"
          v-model:modal-input="modalInput"
          :path-crumbs="pathCrumbs"
          :can-go-back="pathCanGoBack"
          :can-go-forward="pathCanGoForward"
          :show-search="showSearch"
          :view-mode="viewMode"
          :sort-label="sortLabel"
          :show-upload-menu="showUploadMenu"
          :upload-tasks="uploadTasks"
          :show-upload-progress-panel="uploadProgressPanelOpen"
          :upload-enabled="!!selectedKb"
          :items="visibleCards"
          :empty-message="selectedFolderId ? '当前文件夹为空' : '暂无文件夹或文件'"
          :file-scope-active="!!selectedDoc"
          :selected-doc-id="selectedDoc?.id ?? null"
          :get-thumbnail-src="getDocumentThumbnailSrc"
          :has-kb="!!selectedKb"
          :attachment-name="attachmentFileName || undefined"
          :composer-placeholder="browserInputPlaceholder"
          :show-chat-modal="showChatModal"
          :chat-modal-title="chatModalTitle"
          :modal-expanded="modalExpanded"
          :show-modal-history-panel="showModalHistoryPanel"
          :modal-messages="modalMessages"
          :modal-conversation-groups="modalConversationGroups"
          :modal-conversation-id="modalConversationId"
          :open-conversation-menu-id="openConversationMenuId"
          :modal-is-streaming="modalIsStreaming"
          :modal-streaming-assistant-id="modalStreamingAssistantId"
          :modal-input-placeholder="modalInputPlaceholder"
          @path-back="handlePathBack"
          @path-forward="handlePathForward"
          @path-navigate="handlePathNavigate"
          @toggle-search="toggleSearch"
          @toggle-view-mode="toggleViewMode"
          @toggle-sort-mode="toggleSortMode"
          @toggle-upload-menu="toggleUploadMenu"
          @open-file="openFileDialog"
          @open-folder="openFolderDialog"
          @create-folder="createFolder"
          @close-upload-progress-panel="handleCloseUploadProgressPanel"
          @cancel-upload-task="handleCancelUploadTask"
          @open-card="openCard"
          @select-file="selectFileInGrid"
          @open-file-reader="openFileReader"
          @rename-item="renameItem"
          @delete-item="deleteItem"
          @download-doc="downloadDoc"
          @composer-focus="openChatModalFromInput"
          @composer-send="sendQuestion"
          @composer-attachment="openAttachmentDialog"
          @clear-attachment="clearAttachment"
          @close-chat-modal="closeChatModal"
          @new-modal-conversation="newModalConversation"
          @toggle-modal-history="toggleModalHistory"
          @toggle-modal-expand="toggleModalExpand"
          @open-modal-conversation="openModalConversation"
          @toggle-conversation-menu="toggleConversationMenu"
          @rename-modal-conversation="renameModalConversation"
          @delete-modal-conversation="deleteModalConversation"
          @send-modal-question="sendModalQuestion"
        />
      </div>
    </div>
    <input ref="fileInput" type="file" style="display:none" accept=".pdf,application/pdf" @change="handlePdfFileChange" />
    <input ref="folderInput" type="file" style="display:none" accept=".pdf,application/pdf" webkitdirectory directory multiple @change="handlePdfFolderChange" />
    <input ref="attachmentInputRef" type="file" style="display:none" @change="onAttachmentChange" />

    <NameConflictDialog
      v-if="showNameConflictModal"
      :file-name="conflictDisplayName"
      :allow-replace="conflictAllowReplace"
      :conflict-scope="conflictScope"
      @cancel="cancelNameConflict"
      @replace="resolveNameConflictReplace"
      @keep-all="resolveNameConflictKeepAll"
    />

    <CreateKbDialog
      :open="createKbOpen"
      v-model:name="createKbName"
      :error="createKbError"
      :submitting="createKbSubmitting"
      @close="closeCreateKbModal"
      @submit="submitCreateKb"
    />

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import PersonalKbTopBar from '../components/PersonalKbTopBar.vue'
import KbSidebarTree from '../components/KbSidebarTree.vue'
import PdfReaderWithChat from '../components/PdfReaderWithChat.vue'
import NameConflictDialog from '../components/NameConflictDialog.vue'
import CreateKbDialog from '../components/kb/CreateKbDialog.vue'
import PersonalKbBrowsePane from '../components/kb/PersonalKbBrowsePane.vue'
import type { KbBrowseCard } from '../types/kbBrowseCard'
import { useAppNavigation } from '../composables/useAppNavigation'
import { useAttachmentPicker } from '../composables/useAttachmentPicker'
import { useCreateKb } from '../composables/useCreateKb'
import { useKbBrowseListing, type KbBrowseListingDoc } from '../composables/useKbBrowseListing'
import { useKbPathNavigation, type PathCrumb } from '../composables/useKbPathNavigation'
import { createKbFolder, deleteKbFolder, listKbFolders, renameKbFolder, type KbFolderSummary } from '../api/folders'
import { useKbPersonalUpload } from '../composables/useKbPersonalUpload'
import { useKbBrowseActions } from '../composables/useKbBrowseActions'
import { useKbModalChat } from '../composables/useKbModalChat'
import { scopeInputPlaceholder } from '../api/chatScope'
import { consumeOpenFileChat } from '../utils/openFileChat'
import { logout as authLogout } from '../api/auth'
import { clearSession, currentUser } from '../auth/session'
import { deleteKnowledgeBase, listKnowledgeBases, renameKnowledgeBase } from '../api/kb'
import { documentThumbnailUrl, listKbDocuments } from '../api/documents'

type Kb = { id: string; name: string; created_at: string }
type Doc = KbBrowseListingDoc
const { goHome } = useAppNavigation()
const getDocumentThumbnailSrc = (docId?: string) => (docId ? documentThumbnailUrl(docId) : '')
const getPdfReaderSrc = (docId?: string) => {
  if (!docId) return ''
  return `/api/v1/documents/${docId}/file#page=1&toolbar=0&navpanes=0&scrollbar=0&statusbar=0&messages=0&view=FitH`
}

const middleCollapsed = ref(false)
const showSettings = ref(false)
const viewMode = ref<'grid' | 'list'>('grid')
const knowledgeBases = ref<Kb[]>([])
const selectedKb = ref<Kb | null>(null)
const documents = ref<Doc[]>([])
const selectedFolderId = ref<string | null>(null)
const kbFolders = ref<KbFolderSummary[]>([])
/** 网格中单击高亮，不影响对话范围 */
const selectedDoc = ref<Doc | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)
const questionInput = ref('')
const showSearch = ref(false)
const searchQuery = ref('')
const sortMode = ref<'created_desc' | 'created_asc' | 'name_asc' | 'name_desc'>('created_desc')
const showUploadMenu = ref(false)
const uploadSessionActive = ref(false)
const uploadSessionKbId = ref<string | null>(null)
const uploadSessionFolderId = ref<string | null>(null)

const {
  inputRef: attachmentInputRef,
  fileName: attachmentFileName,
  open: openAttachmentDialog,
  clear: clearAttachment,
  onChange: onAttachmentChange,
} = useAttachmentPicker()

// 先按“个人知识库”展示全部知识库（共享分区暂不做）
const personalKbs = computed(() => knowledgeBases.value || [])

const showPreviewModal = ref(false)
const previewDoc = ref<Doc | null>(null)
const kbNameRef = computed(() => selectedKb.value?.name)

const {
  crumbs: pathCrumbs,
  canGoBack: pathCanGoBack,
  canGoForward: pathCanGoForward,
  resetHistory: resetPathHistory,
  navigateTo: pathNavigateTo,
  navigateToCrumb: pathNavigateToCrumb,
  goBack: pathGoBack,
  goForward: pathGoForward,
} = useKbPathNavigation(selectedFolderId, kbFolders, kbNameRef)

const uploadFolderId = computed(() =>
  uploadSessionActive.value ? uploadSessionFolderId.value : selectedFolderId.value,
)

const uploadFolderPath = computed(() => {
  const fid = uploadFolderId.value
  if (!fid) return null
  return kbFolders.value.find((f) => f.id === fid)?.path ?? null
})

const pinUploadSession = () => {
  if (!uploadSessionActive.value) {
    uploadSessionKbId.value = selectedKb.value?.id ?? null
    uploadSessionFolderId.value = selectedFolderId.value
    uploadSessionActive.value = true
  }
}

const clearUploadSession = () => {
  uploadSessionActive.value = false
  uploadSessionKbId.value = null
  uploadSessionFolderId.value = null
}

const { filteredDocsByFolder, visibleCards, directDocsInFolder } = useKbBrowseListing(
  documents,
  kbFolders,
  selectedFolderId,
  searchQuery,
  sortMode,
)

const showNameConflictModal = ref(false)
const pendingConflictFile = ref<File | null>(null)
const conflictReplaceDocId = ref<string | null>(null)
const conflictDisplayName = ref('')
const conflictAllowReplace = ref(true)
const conflictScope = ref<'file' | 'folder'>('file')
const conflictResolver = ref<((action: 'replace' | 'auto_rename' | 'cancel') => void) | null>(null)

const openNameConflictModalFor = (
  file: File,
  existingDocumentId: string,
  displayName: string,
  allowReplace: boolean,
  scope: 'file' | 'folder' = 'file',
): Promise<'replace' | 'auto_rename' | 'cancel'> => {
  pendingConflictFile.value = file
  conflictReplaceDocId.value = existingDocumentId
  conflictDisplayName.value = displayName
  conflictAllowReplace.value = allowReplace
  conflictScope.value = scope
  showNameConflictModal.value = true
  return new Promise((resolve) => {
    conflictResolver.value = (action) => {
      showNameConflictModal.value = false
      pendingConflictFile.value = null
      conflictReplaceDocId.value = null
      conflictDisplayName.value = ''
      conflictAllowReplace.value = true
      conflictScope.value = 'file'
      conflictResolver.value = null
      resolve(action)
    }
  })
}

const cancelNameConflict = () => {
  conflictResolver.value?.('cancel')
}

const resolveNameConflictReplace = async () => {
  if (!conflictAllowReplace.value) return
  conflictResolver.value?.('replace')
}

const resolveNameConflictKeepAll = async () => {
  conflictResolver.value?.('auto_rename')
}

const sortLabel = computed(() => {
  if (sortMode.value === 'created_desc') return '时间倒序'
  if (sortMode.value === 'created_asc') return '时间正序'
  if (sortMode.value === 'name_asc') return '名称 A-Z'
  return '名称 Z-A'
})
function getChatScope() {
  if (showPreviewModal.value && previewDoc.value) {
    return { scope_type: 'file' as const, document_id: previewDoc.value.id }
  }
  if (selectedFolderId.value) {
    return { scope_type: 'folder' as const, folder_id: selectedFolderId.value }
  }
  return { scope_type: 'kb' as const }
}

function onScopeRestored(scope: {
  scope_type: 'kb' | 'folder' | 'file'
  document_id?: string
  folder_id?: string
}) {
  if (scope.scope_type === 'file' && scope.document_id) {
    const doc = documents.value.find((d) => d.id === scope.document_id)
    if (doc) {
      selectedDoc.value = doc
      if (doc.folder_id) resetPathHistory(doc.folder_id)
      previewDoc.value = doc
      showPreviewModal.value = true
    }
    return
  }
  if (scope.scope_type === 'folder' && scope.folder_id) {
    selectedDoc.value = null
    resetPathHistory(scope.folder_id)
    return
  }
  selectKbScope()
}

const toggleMiddleSidebar = () => {
  middleCollapsed.value = !middleCollapsed.value
}

const toggleSettings = () => {
  showSettings.value = !showSettings.value
}

const kbUserDisplayName = computed(
  () => currentUser.value?.username || currentUser.value?.email || '用户',
)

const handleLogout = async () => {
  showSettings.value = false
  try {
    await authLogout()
  } catch {
    /* noop：cookie 失效时仍清空本地会话 */
  }
  clearSession()
}

const loadKnowledgeBases = async (options?: { selectKbId?: string }) => {
  const items = await listKnowledgeBases()

  knowledgeBases.value = items || []

  const prefer =
    (options?.selectKbId && items.find((kb) => kb.id === options.selectKbId)) || null

  const defaultKb = items.find((kb) => kb.name === '个人知识库') || items[0] || null

  const keep =
    prefer ||
    (selectedKb.value && items.find((kb) => kb.id === selectedKb.value?.id)) ||
    defaultKb
  selectedKb.value = keep
  selectedDoc.value = null
}

const KB_SELECT_REQUIRED_MSG = '请先在左侧选择一个知识库'

const requireSelectedKb = (): boolean => {
  if (uploadSessionActive.value && uploadSessionKbId.value) return true
  if (selectedKb.value) return true
  alert(KB_SELECT_REQUIRED_MSG)
  showUploadMenu.value = false
  return false
}

const ensureSelectedKb = async (): Promise<Kb | null> => {
  if (uploadSessionActive.value && uploadSessionKbId.value) {
    const kb = knowledgeBases.value.find((k) => k.id === uploadSessionKbId.value)
    if (kb) return kb
  }
  return selectedKb.value
}

const loadFolders = async () => {
  if (!selectedKb.value) {
    kbFolders.value = []
    return
  }
  kbFolders.value = await listKbFolders(selectedKb.value.id)
}

const loadDocuments = async () => {
  if (!selectedKb.value) {
    documents.value = []
    return
  }
  await loadFolders()
  documents.value = await listKbDocuments(selectedKb.value.id)
  await restorePendingUploadTasks(documents.value)
  if (selectedFolderId.value) {
    const exists = kbFolders.value.some((f) => f.id === selectedFolderId.value)
    if (!exists) {
      resetPathHistory(null)
    }
  }
  if (selectedDoc.value) {
    const matched = documents.value.find((d) => d.id === selectedDoc.value?.id)
    if (!matched) {
      selectedDoc.value = null
    }
  }
  if (previewDoc.value) {
    const matched = documents.value.find((d) => d.id === previewDoc.value?.id)
    if (!matched) {
      showPreviewModal.value = false
      previewDoc.value = null
      markKbSessionsStale()
    }
  }
}

const {
  uploadTasks,
  uploadProgressPanelOpen,
  closeUploadProgressPanel,
  handlePdfFileChange,
  handlePdfFolderChange,
  restorePendingUploadTasks,
  cancelUploadTask,
} = useKbPersonalUpload({
  uploadFolderId,
  uploadFolderPath,
  showNameConflictModal,
  ensureSelectedKb,
  reloadDocuments: loadDocuments,
  promptNameConflict: (p) =>
    openNameConflictModalFor(
      p.file,
      p.existingDocumentId,
      p.displayName,
      p.allowReplace,
      p.scope ?? 'file',
    ),
})

const {
  showChatModal,
  modalMessages,
  modalInput,
  modalIsStreaming,
  modalStreamingAssistantId,
  modalConversationId,
  showModalHistoryPanel,
  modalExpanded,
  openConversationMenuId,
  effectiveScope,
  modalConversationGroups,
  markKbSessionsStale,
  loadLatestConversationForReader,
  openModalConversation,
  openReaderWithConversation,
  openChatModalFromInput,
  newModalConversation,
  toggleModalHistory,
  toggleModalExpand,
  toggleConversationMenu,
  renameModalConversation,
  deleteModalConversation,
  askInModal,
  sendModalQuestion,
  closeChatModal,
} = useKbModalChat({
  ensureSelectedKb,
  getChatScope,
  onScopeRestored,
})

const { renameItem, deleteItem, downloadDoc } = useKbBrowseActions({
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
})

const {
  open: createKbOpen,
  name: createKbName,
  error: createKbError,
  submitting: createKbSubmitting,
  openDialog: openCreateKbDialog,
  closeDialog: closeCreateKbModal,
  submit: submitCreateKb,
} = useCreateKb(async (kbId) => {
  await loadKnowledgeBases({ selectKbId: kbId })
  resetPathHistory(null)
  markKbSessionsStale()
  await loadDocuments()
})

const openCreateKbModal = () => {
  showUploadMenu.value = false
  openCreateKbDialog()
}

const browserInputPlaceholder = computed(() => scopeInputPlaceholder(getChatScope()))
const modalInputPlaceholder = computed(() => scopeInputPlaceholder(effectiveScope.value))

const chatModalTitle = computed(() => {
  const kb = selectedKb.value?.name || '个人知识库'
  const scope = effectiveScope.value
  if (scope.scope_type === 'file') {
    const doc =
      previewDoc.value ||
      selectedDoc.value ||
      documents.value.find((d) => d.id === scope.document_id)
    const name = doc?.title || '当前文件'
    return `${name} · 对话`
  }
  if (scope.scope_type === 'folder') {
    return `${kb} · 文件夹对话`
  }
  return `${kb} · 对话`
})

const selectKbFromSidebar = async (kb: Kb) => {
  selectedKb.value = kb
  selectedDoc.value = null
  resetPathHistory(null)
  markKbSessionsStale()
  await loadDocuments()
}

const renameKbFromSidebar = async (kb: Kb) => {
  const nextName = prompt('请输入新的知识库名称', kb.name)?.trim()
  if (!nextName || nextName === kb.name) return
  try {
    const updated = await renameKnowledgeBase(kb.id, nextName)
    knowledgeBases.value = (knowledgeBases.value || []).map((x) =>
      x.id === kb.id ? { ...x, name: updated.name } : x,
    )
    if (selectedKb.value?.id === kb.id) {
      selectedKb.value = { ...selectedKb.value, name: updated.name }
    }
  } catch (error) {
    console.error('Rename kb failed:', error)
    alert('重命名失败，请稍后重试')
  }
}

const deleteKbFromSidebar = async (kb: Kb) => {
  if (!confirm(`确定删除知识库“${kb.name}”吗？`)) return
  try {
    await deleteKnowledgeBase(kb.id)
  } catch (error) {
    console.error('Delete kb failed:', error)
    alert('删除失败，请稍后重试')
    return
  }

  const remaining = (knowledgeBases.value || []).filter((x) => x.id !== kb.id)
  knowledgeBases.value = remaining

  if (selectedKb.value?.id === kb.id) {
    selectedKb.value = remaining[0] || null
    resetPathHistory(null)
    selectedDoc.value = null
    markKbSessionsStale()
    await loadDocuments()
  }
}

const syncScopeAfterPathChange = () => {
  selectedDoc.value = null
  markKbSessionsStale()
}

const handlePathBack = () => {
  pathGoBack()
  syncScopeAfterPathChange()
}

const handlePathForward = () => {
  pathGoForward()
  syncScopeAfterPathChange()
}

const handlePathNavigate = (crumb: PathCrumb) => {
  pathNavigateToCrumb(crumb)
  syncScopeAfterPathChange()
}

const selectFolder = (folderId: string) => {
  pathNavigateTo(folderId)
  syncScopeAfterPathChange()
}

const openCard = (item: KbBrowseCard) => {
  if (item.kind === 'folder' && item.folderId) {
    selectFolder(item.folderId)
  }
}

const findDocById = (docId: string) =>
  filteredDocsByFolder.value.find((d) => d.id === docId) ||
  documents.value.find((d) => d.id === docId) ||
  null

const selectFileInGrid = (item: KbBrowseCard) => {
  if (!item.docId) return
  const doc = findDocById(item.docId)
  if (!doc) return
  selectedDoc.value = doc
}

const openFileReader = async (item: KbBrowseCard) => {
  if (!item.docId) return
  const doc = findDocById(item.docId)
  if (!doc) return
  selectedDoc.value = doc
  previewDoc.value = doc
  showPreviewModal.value = true
  markKbSessionsStale()
  await loadLatestConversationForReader()
}

const selectKbScope = () => {
  pathNavigateTo(null)
  syncScopeAfterPathChange()
}

const closePreviewModal = () => {
  showPreviewModal.value = false
  previewDoc.value = null
  markKbSessionsStale()
}

const toggleSearch = () => {
  showSearch.value = !showSearch.value
  if (!showSearch.value) {
    searchQuery.value = ''
  }
}

const toggleViewMode = () => {
  viewMode.value = viewMode.value === 'grid' ? 'list' : 'grid'
}

const toggleSortMode = () => {
  const order: Array<typeof sortMode.value> = ['created_desc', 'created_asc', 'name_asc', 'name_desc']
  const idx = order.indexOf(sortMode.value)
  sortMode.value = order[(idx + 1) % order.length]
}

const toggleUploadMenu = () => {
  if (!requireSelectedKb()) return
  showUploadMenu.value = !showUploadMenu.value
}

const openFileDialog = () => {
  if (!requireSelectedKb()) return
  pinUploadSession()
  showUploadMenu.value = false
  fileInput.value?.click()
}

const openFolderDialog = () => {
  if (!requireSelectedKb()) return
  pinUploadSession()
  showUploadMenu.value = false
  folderInput.value?.click()
}

const createFolder = async () => {
  if (!requireSelectedKb()) return
  pinUploadSession()
  showUploadMenu.value = false
  const name = prompt('请输入新文件夹名称')?.trim()
  if (!name) return
  if (name.includes('/')) {
    alert('文件夹名称不能包含 "/"')
    return
  }
  try {
    await createKbFolder(selectedKb.value!.id, {
      name,
      parent_id: selectedFolderId.value ?? undefined,
    })
    await loadFolders()
  } catch (error) {
    console.error('Create folder failed:', error)
    alert('创建文件夹失败')
  }
}

const handleCloseUploadProgressPanel = () => {
  closeUploadProgressPanel()
  clearUploadSession()
}

const handleCancelUploadTask = async (taskId: string) => {
  const task = uploadTasks.value.find((t) => t.id === taskId)
  if (!task) return
  await cancelUploadTask(task)
}

const sendQuestion = async () => {
  if (!questionInput.value.trim()) return
  await openChatModalFromInput()
  let question = questionInput.value.trim()
  if (attachmentFileName.value) {
    question = `${question}\n[附件占位] ${attachmentFileName.value}`
  }
  questionInput.value = ''
  clearAttachment()
  void askInModal(question)
}

const handleClickOutside = (e: MouseEvent) => {
  const target = e.target as HTMLElement | null
  if (!target) return
  const settingsMenu = document.querySelector('.settings-menu')
  const userInfo = document.querySelector('.user-info')
  if (settingsMenu && userInfo && !settingsMenu.contains(target) && !userInfo.contains(target)) {
    showSettings.value = false
  }
  if (!target.closest('.upload-menu-wrap') && !target.closest('.upload-progress-continue-wrap')) {
    showUploadMenu.value = false
  }
  if (!target.closest('.chat-history-menu-wrap')) {
    openConversationMenuId.value = null
  }
}

const openFileChatFromHistory = async (payload: {
  conversationId: string
  documentId: string
  kbId: string
}) => {
  await loadKnowledgeBases({ selectKbId: payload.kbId })
  await loadDocuments()
  const doc = documents.value.find((d) => d.id === payload.documentId)
  if (!doc) {
    alert('该文件不存在或已删除，无法打开对话')
    return
  }
  if (doc.folder_id) {
    resetPathHistory(doc.folder_id)
  } else {
    resetPathHistory(null)
  }
  selectedDoc.value = doc
  previewDoc.value = doc
  showPreviewModal.value = true
  await openReaderWithConversation(payload.conversationId)
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  void (async () => {
    await loadKnowledgeBases()
    await loadDocuments()
    const pending = consumeOpenFileChat()
    if (pending) {
      await openFileChatFromHistory(pending)
    }
  })()
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.page-root {
  height: 100vh;
  background: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

* {
  box-sizing: border-box;
}

/* 主布局 */
.main-container {
  display: flex;
  height: calc(100vh - 48px);
  position: relative;
}

.page-root.is-file-reader .main-container {
  height: 100vh;
}

/* 右侧内容区 */
.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
  position: relative;
}
</style>

