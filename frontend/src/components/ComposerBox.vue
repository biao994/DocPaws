<template>
  <div class="composer-root">
    <div class="composer-shell" :class="shellVariantClass">
      <div class="composer-main-row">
        <textarea
          ref="textareaEl"
          class="composer-textarea"
          :value="modelValue"
          rows="1"
          :placeholder="placeholder"
          @input="onInput"
          @keydown="onKeydown"
          @focus="$emit('focus')"
          @click="$emit('focus')"
        />
      </div>

      <div v-if="showErrorBanner && errorText" class="composer-error-banner">
        {{ errorText }}
      </div>

      <div class="composer-footer">
        <div class="composer-left">
          <button
            class="composer-pill"
            type="button"
            :class="{ 'is-deep': chatMode === 'deep' }"
            :title="chatMode === 'deep' ? '深度模式：展示思考过程' : '快速模式'"
            @click.stop="toggleChatMode"
          >
            {{ chatModeLabel }}
          </button>
          <button
            v-if="enableKbPicker"
            class="composer-pill"
            type="button"
            @click.stop="openKbDropdown"
          >
            @
          </button>
        </div>
        <div class="composer-right">
          <button class="composer-send-btn" type="button" :disabled="disabledSend" @click="$emit('send')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <div v-if="enableKbPicker && showKbDropdown" ref="kbDropdownEl" class="kb-dropdown">
      <div
        v-for="kb in kbOptions"
        :key="kb.id"
        class="kb-dropdown-item"
        :class="{ active: kb.id === selectedKbId }"
        @click="selectKb(kb)"
      >
        <div class="kb-item-title">{{ kb.type }}</div>
        <div class="kb-item-name">{{ kb.name }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useChatMode } from '../composables/useChatMode'

const { chatMode, chatModeLabel, toggleChatMode } = useChatMode()

type KbOption = { id: string; name: string; type: string }

const props = withDefaults(
  defineProps<{
  modelValue: string
  placeholder?: string
  disabledSend?: boolean
  kbOptions?: KbOption[]
  selectedKbId?: string | null
  errorText?: string
  showErrorBanner?: boolean
  shellVariant?: 'card' | 'bare'
  enableKbPicker?: boolean
}>(),
  {
    kbOptions: () => [],
    enableKbPicker: true,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'send'): void
  (e: 'selectKb', kb: KbOption): void
  (e: 'attachment'): void
  (e: 'clipboard'): void
  (e: 'focus'): void
}>()

const textareaEl = ref<HTMLTextAreaElement | null>(null)
const kbDropdownEl = ref<HTMLElement | null>(null)
const showKbDropdown = ref(false)

const shellVariantClass = computed(() => (props.shellVariant === 'bare' ? 'is-bare' : 'is-card'))

const autoResize = async () => {
  await nextTick()
  const el = textareaEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

const openKbDropdown = () => {
  showKbDropdown.value = true
}

const selectKb = (kb: KbOption) => {
  emit('selectKb', kb)
  showKbDropdown.value = false
  void autoResize()
}

const onInput = (e: Event) => {
  const v = (e.target as HTMLTextAreaElement).value
  emit('update:modelValue', v)
  void autoResize()
}

const onKeydown = (e: KeyboardEvent) => {
  if (props.enableKbPicker && e.key === '@') {
    openKbDropdown()
    return
  }
  if (e.key === 'Enter') {
    e.preventDefault()
    emit('send')
  }
}

const handleClickOutside = (e: MouseEvent) => {
  const target = e.target as HTMLElement | null
  if (!target) return
  if (kbDropdownEl.value && !kbDropdownEl.value.contains(target)) {
    showKbDropdown.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  void autoResize()
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

watch(
  () => props.modelValue,
  () => {
    void autoResize()
  }
)
</script>

<style scoped>
.composer-root{
  position: relative;
  width: 100%;
}

.composer-shell{
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.composer-shell.is-card{
  background: #fff;
  border-radius: 18px;
  padding: 12px 14px 10px;
  border: 1px solid #e6e6e6;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}

.composer-shell.is-bare{
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0;
  border-radius: 0;
}

.composer-main-row{
  display: flex;
  align-items: stretch;
}

.composer-textarea{
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  color: #6b7280;
  font-size: 14px;
  resize: none;
  line-height: 22px;
  padding: 2px 6px;
  min-height: 22px;
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.composer-textarea::placeholder{
  color: #94a3b8;
}

.composer-footer{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
  min-height: 32px;
  padding: 0 6px;
  box-sizing: border-box;
}

.composer-left{
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
}

.composer-pill{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  border: none;
  background: #f7f7f7;
  font-size: 12px;
  line-height: 1;
  color: #6b7280;
  cursor: pointer;
  box-sizing: border-box;
}

.composer-pill:hover{
  background: #efefef;
}

.composer-pill.is-deep{
  background: var(--dp-primary-bg);
  color: var(--dp-primary);
}

.composer-right{
  display: flex;
  align-items: center;
  gap: 8px;
}

.composer-icon-btn{
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}

.composer-send-btn{
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: var(--dp-primary-solid);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.composer-send-btn:disabled{
  background: #ccc;
  cursor: not-allowed;
}

.composer-error-banner{
  margin: 2px 6px 0;
  padding: 8px 10px;
  border-radius: 10px;
  background: #fff1f0;
  border: 1px solid #ffccc7;
  color: #a8071a;
  font-size: 12px;
  line-height: 18px;
}

.kb-dropdown{
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 8px;
  min-width: 220px;
  z-index: 110;
}

.kb-dropdown-item{
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.kb-dropdown-item:hover{
  background: #f5f5f5;
}

.kb-dropdown-item.active{
  background: #e6f7ed;
}

.kb-item-title{
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 2px;
}

.kb-item-name{
  font-size: 14px;
  color: #6b7280;
}
</style>

