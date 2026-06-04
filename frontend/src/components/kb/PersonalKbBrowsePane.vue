<template>
  <KbContentToolbar
    v-model:search-query="searchQuery"
    :path-crumbs="pathCrumbs"
    :can-go-back="canGoBack"
    :can-go-forward="canGoForward"
    :show-search="showSearch"
    :view-mode="viewMode"
    :sort-label="sortLabel"
    :show-upload-menu="showUploadMenu"
    :upload-tasks="uploadTasks"
    :show-upload-progress-panel="showUploadProgressPanel"
    :upload-enabled="uploadEnabled"
    @path-back="$emit('pathBack')"
    @path-forward="$emit('pathForward')"
    @path-navigate="$emit('pathNavigate', $event)"
    @toggle-search="$emit('toggleSearch')"
    @toggle-view-mode="$emit('toggleViewMode')"
    @toggle-sort-mode="$emit('toggleSortMode')"
    @toggle-upload-menu="$emit('toggleUploadMenu')"
    @open-file="$emit('openFile')"
    @open-folder="$emit('openFolder')"
    @create-folder="$emit('createFolder')"
    @close-upload-progress-panel="$emit('closeUploadProgressPanel')"
    @cancel-upload-task="$emit('cancelUploadTask', $event)"
  />

  <KbDocumentBrowser
    :view-mode="viewMode"
    :items="items"
    :empty-message="emptyMessage"
    :file-scope-active="fileScopeActive"
    :selected-doc-id="selectedDocId"
    :get-thumbnail-src="getThumbnailSrc"
    @open-card="$emit('openCard', $event)"
    @select-file="$emit('selectFile', $event)"
    @open-file="$emit('openFileReader', $event)"
    @rename-item="$emit('renameItem', $event)"
    @delete-item="$emit('deleteItem', $event)"
    @download-doc="$emit('downloadDoc', $event)"
  />

  <KbMainComposerBar
    v-model="composerInput"
    :has-kb="hasKb"
    :attachment-name="attachmentName"
    :placeholder="composerPlaceholder"
    @focus="$emit('composerFocus')"
    @send="$emit('composerSend')"
    @attachment="$emit('composerAttachment')"
    @clear-attachment="$emit('clearAttachment')"
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
    :pending-assistant-id="modalStreamingAssistantId"
    :composer-placeholder="modalInputPlaceholder"
    @close="$emit('closeChatModal')"
    @new-conversation="$emit('newModalConversation')"
    @toggle-history="$emit('toggleModalHistory')"
    @toggle-expand="$emit('toggleModalExpand')"
    @select-conversation="$emit('openModalConversation', $event)"
    @toggle-conversation-menu="$emit('toggleConversationMenu', $event)"
    @rename-conversation="$emit('renameModalConversation', $event)"
    @delete-conversation="$emit('deleteModalConversation', $event)"
    @send="$emit('sendModalQuestion')"
    @attachment="$emit('composerAttachment')"
  />
</template>

<script setup lang="ts">
import type { ChatModalMessage } from '../ChatMessageList.vue'
import KbChatModal, {
  type ChatModalConversation,
  type ChatModalConversationGroup,
} from '../KbChatModal.vue'
import KbContentToolbar, { type ToolbarUploadTask } from '../KbContentToolbar.vue'
import KbDocumentBrowser from '../KbDocumentBrowser.vue'
import KbMainComposerBar from '../KbMainComposerBar.vue'
import type { PathCrumb } from '../../composables/useKbPathNavigation'
import type { KbBrowseCard } from '../../types/kbBrowseCard'

const searchQuery = defineModel<string>('searchQuery', { default: '' })
const composerInput = defineModel<string>('composerInput', { required: true })
const modalInput = defineModel<string>('modalInput', { required: true })

defineProps<{
  pathCrumbs: readonly PathCrumb[]
  canGoBack: boolean
  canGoForward: boolean
  showSearch: boolean
  viewMode: 'grid' | 'list'
  sortLabel: string
  showUploadMenu: boolean
  uploadTasks: ToolbarUploadTask[]
  showUploadProgressPanel: boolean
  uploadEnabled: boolean
  items: readonly KbBrowseCard[]
  emptyMessage: string
  fileScopeActive: boolean
  selectedDocId: string | null
  getThumbnailSrc: (docId?: string) => string
  hasKb: boolean
  attachmentName?: string
  composerPlaceholder: string
  showChatModal: boolean
  chatModalTitle: string
  modalExpanded: boolean
  showModalHistoryPanel: boolean
  modalMessages: ChatModalMessage[]
  modalConversationGroups: ChatModalConversationGroup[]
  modalConversationId: string | null
  openConversationMenuId: string | null
  modalIsStreaming: boolean
  modalStreamingAssistantId: string | null
  modalInputPlaceholder: string
}>()

defineEmits<{
  pathBack: []
  pathForward: []
  pathNavigate: [crumb: PathCrumb]
  toggleSearch: []
  toggleViewMode: []
  toggleSortMode: []
  toggleUploadMenu: []
  openFile: []
  openFolder: []
  createFolder: []
  closeUploadProgressPanel: []
  cancelUploadTask: [taskId: string]
  openCard: [item: KbBrowseCard]
  selectFile: [item: KbBrowseCard]
  openFileReader: [item: KbBrowseCard]
  renameItem: [item: KbBrowseCard]
  deleteItem: [item: KbBrowseCard]
  downloadDoc: [docId: string]
  composerFocus: []
  composerSend: []
  composerAttachment: []
  clearAttachment: []
  closeChatModal: []
  newModalConversation: []
  toggleModalHistory: []
  toggleModalExpand: []
  openModalConversation: [id: string]
  toggleConversationMenu: [id: string]
  renameModalConversation: [item: ChatModalConversation]
  deleteModalConversation: [id: string]
  sendModalQuestion: []
}>()
</script>
