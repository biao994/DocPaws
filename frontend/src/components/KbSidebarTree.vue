<template>
  <div class="sidebar-middle" :class="{ collapsed: collapsed }">
    <div class="sidebar-header">
      <button type="button" class="sidebar-header-collapse" title="收起侧栏" @click="emit('toggleCollapse')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
    </div>
    <div class="folder-tree">
      <div class="tree-section-title-row first-section">
        <div class="tree-section-title">个人知识库</div>
        <button type="button" class="tree-plus-btn" title="新建知识库" @click.stop="emit('createKb')">+</button>
      </div>
      <div
        v-for="kb in knowledgeBases"
        :key="`kb-personal-${kb.id}`"
        class="tree-item tree-root"
        :class="{ active: selectedKbId === kb.id && !selectedFolderId }"
        @click="emit('selectKb', kb)"
      >
        <div class="tree-arrow"></div>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
        </svg>
        <span class="tree-kb-name">{{ kb.name }}</span>
        <span class="tree-kb-menu-wrap" @click.stop>
          <button
            type="button"
            class="tree-kb-menu-btn"
            title="更多操作"
            @click="toggleKbMenu(kb.id)"
          >
            ⋯
          </button>
          <div v-if="openKbMenuId === kb.id" class="tree-kb-menu">
            <button type="button" class="tree-kb-menu-item" @click="emit('renameKb', kb)">
              重命名
            </button>
            <button type="button" class="tree-kb-menu-item danger" @click="emit('deleteKb', kb)">
              删除
            </button>
          </div>
        </span>
      </div>
    </div>
    <!-- 暂隐藏：占位容量与当前知识库（后端未接统计 API） -->
    <div v-if="false" class="storage-info">
      已使用 1.2GB / 10GB
      <div class="storage-bar">
        <div class="storage-used" style="width: 12%"></div>
      </div>
      <div class="storage-text">当前知识库：{{ currentKbLabel || '未选择' }}</div>
    </div>
  </div>
  <button v-if="collapsed" type="button" class="sidebar-return-btn" title="返回侧栏" @click="emit('toggleCollapse')">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="9 6 15 12 9 18"></polyline>
    </svg>
  </button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
/** 与 PersonalKbView 中 Kb 一致，便于点击整行回传 */
export type KbSidebarItem = { id: string; name: string; created_at: string }

defineProps<{
  collapsed: boolean
  knowledgeBases: KbSidebarItem[]
  selectedKbId: string | null
  /** 非空表示正在浏览某文件夹，根级知识库项不高亮 */
  selectedFolderId: string | null
  currentKbLabel?: string | null
}>()

const emit = defineEmits<{
  toggleCollapse: []
  selectKb: [kb: KbSidebarItem]
  createKb: []
  renameKb: [kb: KbSidebarItem]
  deleteKb: [kb: KbSidebarItem]
}>()

const openKbMenuId = ref<string | null>(null)
const toggleKbMenu = (id: string) => {
  openKbMenuId.value = openKbMenuId.value === id ? null : id
}
</script>

<style scoped>
.sidebar-middle {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
}

.sidebar-middle.collapsed {
  width: 0;
  overflow: hidden;
  padding: 0;
  border-right: none;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

.sidebar-header-collapse {
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  border-radius: 6px;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-header-collapse:hover {
  background: #f5f5f5;
}

.sidebar-return-btn {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 6px;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
  z-index: 20;
}

.sidebar-return-btn:hover {
  background: #f5f5f5;
}

.folder-tree {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.tree-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  gap: 8px;
  font-size: 14px;
  color: #6b7280;
}

.tree-item:hover {
  background: #f5f5f5;
}

.tree-item.active {
  background: var(--dp-primary-bg);
  color: var(--dp-primary);
}

.tree-item.tree-root {
  font-weight: 600;
}

.tree-kb-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-kb-menu-wrap {
  position: relative;
  flex: 0 0 auto;
}

.tree-kb-menu-btn {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  color: #94a3b8;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
}

.tree-item:hover .tree-kb-menu-btn {
  opacity: 1;
}

.tree-kb-menu-btn:hover {
  background: #f0f0f0;
  color: #6b7280;
}

.tree-kb-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  width: 120px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.16);
  padding: 6px;
  z-index: 60;
}

.tree-kb-menu-item {
  width: 100%;
  border: none;
  background: transparent;
  text-align: left;
  font-size: 13px;
  color: #6b7280;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.tree-kb-menu-item:hover {
  background: #f5f5f5;
}

.tree-kb-menu-item.danger {
  color: var(--dp-danger-text, #6b7280);
}

.tree-empty {
  padding: 6px 12px 10px;
  font-size: 12px;
  color: #94a3b8;
}

.tree-item-child {
  padding-left: 30px;
  font-size: 13px;
}

.tree-section-title {
  margin-top: 14px;
  padding: 8px 0 4px;
  font-size: 13px;
  color: #6b7280;
  font-weight: 600;
}

.tree-section-title-row {
  margin-top: 14px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 22px;
}

.tree-section-title-row.first-section {
  margin-top: 2px;
}

.tree-section-title-row .tree-section-title {
  flex: 1;
  margin: 0;
  padding: 0;
  min-height: 22px;
  display: flex;
  align-items: center;
  line-height: 22px;
}

.tree-plus-btn {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  padding: 0;
  line-height: 22px;
  font-size: 15px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 22px;
}

.tree-plus-btn:hover {
  background: #f0f0f0;
  color: #18a058;
}

.tree-subtitle {
  padding: 4px 12px;
  font-size: 12px;
  color: #94a3b8;
}

.tree-item-disabled {
  opacity: 0.8;
}

.tree-item svg {
  width: 16px;
  height: 16px;
  color: #94a3b8;
}

.tree-item.active svg {
  color: var(--dp-primary);
}

.tree-arrow {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #94a3b8;
}

.storage-info {
  padding: 12px 16px;
  border-top: 1px solid #f0f0f0;
  font-size: 12px;
  color: #94a3b8;
}

.storage-bar {
  height: 4px;
  background: #f0f0f0;
  border-radius: 2px;
  margin-top: 6px;
  overflow: hidden;
}

.storage-used {
  height: 100%;
  background: #18a058;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.storage-text {
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
}
</style>
