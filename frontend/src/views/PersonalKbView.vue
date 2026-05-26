<template>
  <div class="page-root" :class="{ 'is-file-reader': showPreviewModal }">
    <PersonalKbTopBar
      v-if="!showPreviewModal"
      :settings-open="showSettings"
      :display-name="kbUserDisplayName"
      @toggle-settings="toggleSettings"
      @navigate-home="() => navigate('home')"
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
          :composer-placeholder="modalInputPlaceholder"
          @close="closePreviewModal"
          @send="sendModalQuestion"
          @attachment="openAttachmentDialog"
        />
        <template v-else>
        <KbContentToolbar
          v-model:search-query="searchQuery"
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
        />

        <KbDocumentBrowser
          :view-mode="viewMode"
          :items="visibleCards"
          :empty-message="selectedFolderId ? '当前文件夹为空' : '暂无文件夹或文件'"
          :file-scope-active="selectedScopeType === 'file'"
          :selected-doc-id="selectedDoc?.id ?? null"
          :get-pdf-card-src="getPdfCardPreviewSrc"
          @open-card="openCard"
          @rename-item="renameItem"
          @delete-item="deleteItem"
          @download-doc="downloadDoc"
        />

        <KbMainComposerBar
          v-model="questionInput"
          :has-kb="!!selectedKb"
          :attachment-name="selectedAttachmentName || undefined"
          :placeholder="browserInputPlaceholder"
          @focus="openChatModalFromInput"
          @send="sendQuestion"
          @attachment="openAttachmentDialog"
          @clear-attachment="clearAttachment"
        />

        <KbChatModal
          v-if="showChatModal"
          v-model="modalInput"
          :modal-title="chatModalTitle"
          :expanded="modalExpanded"
          :show-history="showModalHistoryPanel"
          :messages="modalMessages"
          :conversation-groups="modalConversationGroups"
          :active-conversation-id="modalConversationId"
          :open-conversation-menu-id="openConversationMenuId"
          :is-streaming="modalIsStreaming"
          :composer-placeholder="modalInputPlaceholder"
          @close="closeChatModal"
          @new-conversation="newModalConversation"
          @toggle-history="toggleModalHistory"
          @toggle-expand="toggleModalExpand"
          @select-conversation="openModalConversation"
          @toggle-conversation-menu="toggleConversationMenu"
          @rename-conversation="renameModalConversation"
          @delete-conversation="deleteModalConversation"
          @send="sendModalQuestion"
          @attachment="openAttachmentDialog"
        />
        </template>
      </div>
    </div>
    <input ref="fileInput" type="file" style="display:none" accept=".pdf,application/pdf" @change="handlePdfFileChange" />
    <input ref="folderInput" type="file" style="display:none" accept=".pdf,application/pdf" webkitdirectory directory multiple @change="handlePdfFolderChange" />
    <input ref="attachmentInput" type="file" style="display:none" @change="handleAttachmentChange" />

    <NameConflictDialog
      v-if="showNameConflictModal"
      :file-name="conflictDisplayName"
      :allow-replace="conflictAllowReplace"
      :conflict-scope="conflictScope"
      @cancel="cancelNameConflict"
      @replace="resolveNameConflictReplace"
      @keep-all="resolveNameConflictKeepAll"
    />

    <div v-if="showCreateKbModal" class="create-kb-mask" @click.self="closeCreateKbModal">
      <div class="create-kb-dialog">
        <div class="create-kb-title">新建个人知识库</div>
        <p class="create-kb-desc">将创建归属于当前账号的知识库，可随后上传文档并与 AI 对话。</p>
        <input
          v-model="newKbName"
          class="create-kb-input"
          type="text"
          placeholder="知识库名称，例如「项目资料」"
          maxlength="120"
          :disabled="createKbSubmitting"
          @keyup.enter="submitCreateKb"
        />
        <p v-if="createKbError" class="create-kb-error">{{ createKbError }}</p>
        <div class="create-kb-actions">
          <button type="button" class="create-kb-btn secondary" :disabled="createKbSubmitting" @click="closeCreateKbModal">
            取消
          </button>
          <button type="button" class="create-kb-btn primary" :disabled="createKbSubmitting" @click="submitCreateKb">
            {{ createKbSubmitting ? '创建中…' : '创建' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import PersonalKbTopBar from '../components/PersonalKbTopBar.vue'
import KbSidebarTree from '../components/KbSidebarTree.vue'
import KbMainComposerBar from '../components/KbMainComposerBar.vue'
import KbChatModal from '../components/KbChatModal.vue'
import PdfReaderWithChat from '../components/PdfReaderWithChat.vue'
import NameConflictDialog from '../components/NameConflictDialog.vue'
import KbContentToolbar from '../components/KbContentToolbar.vue'
import KbDocumentBrowser from '../components/KbDocumentBrowser.vue'
import type { KbBrowseCard } from '../types/kbBrowseCard'
import { useKbBrowseListing, type KbBrowseListingDoc } from '../composables/useKbBrowseListing'
import { useKbPathNavigation, type PathCrumb } from '../composables/useKbPathNavigation'
import { createKbFolder, deleteKbFolder, listKbFolders, renameKbFolder, type KbFolderSummary } from '../api/folders'
import { useKbPersonalUpload } from '../composables/useKbPersonalUpload'
import { useKbModalChat } from '../composables/useKbModalChat'
import { scopeInputPlaceholder } from '../api/chatScope'
import { consumeOpenFileChat } from '../utils/openFileChat'
import { logout as authLogout } from '../api/auth'
import { clearSession, currentUser } from '../auth/session'
import { createKnowledgeBase, deleteKnowledgeBase, listKnowledgeBases, renameKnowledgeBase } from '../api/kb'
import {
  deleteDocument,
  downloadDocumentBlob,
  listKbDocuments,
  renameDocument,
} from '../api/documents'

type ViewName = 'home' | 'kb' | 'history'
type Kb = { id: string; name: string; created_at: string }
type Doc = KbBrowseListingDoc
const getPdfCardPreviewSrc = (docId?: string) => {
  if (!docId) return ''
  return `/api/v1/documents/${docId}/file#page=1&toolbar=0&navpanes=0&scrollbar=0&statusbar=0&messages=0&view=FitH`
}
const getPdfReaderSrc = (docId?: string) => {
  if (!docId) return ''
  return `/api/v1/documents/${docId}/file#page=1&toolbar=0&navpanes=0&scrollbar=0&statusbar=0&messages=0&view=FitH`
}
const emit = defineEmits<{
  (e: 'navigate', view: ViewName): void
}>()

const middleCollapsed = ref(false)
const showSettings = ref(false)
const viewMode = ref<'grid' | 'list'>('grid')
const knowledgeBases = ref<Kb[]>([])
const selectedKb = ref<Kb | null>(null)
const documents = ref<Doc[]>([])
const selectedFolderId = ref<string | null>(null)
const kbFolders = ref<KbFolderSummary[]>([])
const selectedDoc = ref<Doc | null>(null)
const selectedScopeType = ref<'kb' | 'file'>('kb')
const fileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)
const attachmentInput = ref<HTMLInputElement | null>(null)
const questionInput = ref('')
const selectedAttachmentName = ref('')
const showSearch = ref(false)
const searchQuery = ref('')
const sortMode = ref<'created_desc' | 'created_asc' | 'name_asc' | 'name_desc'>('created_desc')
const showUploadMenu = ref(false)
const uploadSessionActive = ref(false)
const uploadSessionKbId = ref<string | null>(null)
const uploadSessionFolderId = ref<string | null>(null)
const showCreateKbModal = ref(false)
const newKbName = ref('')
const createKbError = ref('')
const createKbSubmitting = ref(false)

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
  if (selectedScopeType.value === 'file' && selectedDoc.value) {
    return { scope_type: 'file' as const, document_id: selectedDoc.value.id }
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
      selectedScopeType.value = 'file'
      selectedDoc.value = doc
      if (doc.folder_id) resetPathHistory(doc.folder_id)
    }
    return
  }
  if (scope.scope_type === 'folder' && scope.folder_id) {
    selectedScopeType.value = 'kb'
    selectedDoc.value = null
    resetPathHistory(scope.folder_id)
    return
  }
  selectKbScope()
}

const navigate = (view: ViewName) => {
  emit('navigate', view)
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
  selectedScopeType.value = 'kb'
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
      selectedScopeType.value = 'kb'
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

const browserInputPlaceholder = computed(() => scopeInputPlaceholder(getChatScope()))
const modalInputPlaceholder = computed(() => scopeInputPlaceholder(effectiveScope.value))

const chatModalTitle = computed(() => {
  const kb = selectedKb.value?.name || '个人知识库'
  const scope = effectiveScope.value
  if (scope.scope_type === 'file') {
    const doc =
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
  selectedScopeType.value = 'kb'
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
    selectedScopeType.value = 'kb'
    markKbSessionsStale()
    await loadDocuments()
  }
}

const openCreateKbModal = () => {
  showUploadMenu.value = false
  newKbName.value = ''
  createKbError.value = ''
  showCreateKbModal.value = true
}

const closeCreateKbModal = () => {
  if (createKbSubmitting.value) return
  showCreateKbModal.value = false
}

const submitCreateKb = async () => {
  const name = newKbName.value.trim()
  if (!name) {
    createKbError.value = '请输入知识库名称'
    return
  }
  createKbSubmitting.value = true
  createKbError.value = ''
  try {
    const kb = await createKnowledgeBase(name)
    showCreateKbModal.value = false
    newKbName.value = ''
    await loadKnowledgeBases({ selectKbId: kb.id })
    resetPathHistory(null)
    markKbSessionsStale()
    await loadDocuments()
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { user_hint?: string; message?: string } } }
    createKbError.value =
      ax.response?.data?.user_hint ||
      ax.response?.data?.message ||
      (e instanceof Error ? e.message : '创建失败，请稍后重试')
  } finally {
    createKbSubmitting.value = false
  }
}

const syncScopeAfterPathChange = () => {
  selectedScopeType.value = 'kb'
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
    return
  }
  if (item.docId) {
    handleFileClick(item.docId)
  }
}

const selectKbScope = () => {
  pathNavigateTo(null)
  syncScopeAfterPathChange()
}

const selectFileScope = (doc: Doc) => {
  selectedDoc.value = doc
  selectedScopeType.value = 'file'
  markKbSessionsStale()
}

const handleFileClick = (docId: string) => {
  const doc =
    filteredDocsByFolder.value.find((d) => d.id === docId) ||
    documents.value.find((d) => d.id === docId)
  if (!doc) return
  selectFileScope(doc)
  previewDoc.value = doc
  showPreviewModal.value = true
  void loadLatestConversationForReader()
}

const closePreviewModal = () => {
  showPreviewModal.value = false
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

const openAttachmentDialog = () => {
  attachmentInput.value?.click()
}

const handleAttachmentChange = (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  selectedAttachmentName.value = file?.name || ''
  input.value = ''
}

const clearAttachment = () => {
  selectedAttachmentName.value = ''
}

const getDocById = (docId: string) => documents.value.find((d) => d.id === docId) || null

const updateDocTitle = async (docId: string, newTitle: string) => {
  await renameDocument(docId, newTitle)
}

const renameItem = async (item: KbBrowseCard) => {
  const newName = prompt('请输入新名称', item.name)?.trim()
  if (!newName) return
  try {
    if (item.kind === 'file' && item.docId) {
      await updateDocTitle(item.docId, newName)
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
      selectedScopeType.value = 'kb'
    }
    await loadDocuments()
  } catch (error) {
    console.error('Delete folder failed:', error)
    alert('删除文件夹失败')
  }
}

const deleteDoc = async (docId: string) => {
  if (!confirm('确定删除该文件吗？')) return
  try {
    await deleteDocument(docId)
    await loadDocuments()
    if (selectedDoc.value?.id === docId) {
      selectedDoc.value = null
      selectedScopeType.value = 'kb'
    }
  } catch (error) {
    console.error('Delete failed:', error)
    alert('删除失败，请稍后重试')
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

const sendQuestion = async () => {
  if (!questionInput.value.trim()) return
  await openChatModalFromInput()
  let question = questionInput.value.trim()
  if (selectedAttachmentName.value) {
    question = `${question}\n[附件占位] ${selectedAttachmentName.value}`
  }
  questionInput.value = ''
  selectedAttachmentName.value = ''
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
  selectedScopeType.value = 'file'
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

.create-kb-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4000;
}

.create-kb-dialog {
  width: min(420px, 92vw);
  background: #fff;
  border-radius: 10px;
  padding: 20px 22px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
}

.create-kb-title {
  font-size: 16px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 8px;
}

.create-kb-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 0 0 14px;
  line-height: 1.5;
}

.create-kb-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}

.create-kb-input:focus {
  border-color: var(--dp-primary);
}

.create-kb-error {
  margin: 10px 0 0;
  font-size: 13px;
  color: #c53030;
}

.create-kb-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

.create-kb-btn {
  min-width: 88px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  border: none;
}

.create-kb-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.create-kb-btn.secondary {
  background: #f5f5f5;
  color: #6b7280;
}

.create-kb-btn.primary {
  background: var(--dp-primary);
  color: #fff;
}
</style>

