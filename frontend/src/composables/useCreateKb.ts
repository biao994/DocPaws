import { ref } from 'vue'

import { createKnowledgeBase } from '../api/kb'

export function useCreateKb(onCreated: (kbId: string) => void | Promise<void>) {
  const open = ref(false)
  const name = ref('')
  const error = ref('')
  const submitting = ref(false)

  const openDialog = () => {
    name.value = ''
    error.value = ''
    open.value = true
  }

  const closeDialog = () => {
    if (submitting.value) return
    open.value = false
  }

  const submit = async () => {
    const trimmed = name.value.trim()
    if (!trimmed) {
      error.value = '请输入知识库名称'
      return
    }
    submitting.value = true
    error.value = ''
    try {
      const kb = await createKnowledgeBase(trimmed)
      open.value = false
      name.value = ''
      await onCreated(kb.id)
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { user_hint?: string; message?: string } } }
      error.value =
        ax.response?.data?.user_hint ||
        ax.response?.data?.message ||
        (e instanceof Error ? e.message : '创建失败，请稍后重试')
    } finally {
      submitting.value = false
    }
  }

  return {
    open,
    name,
    error,
    submitting,
    openDialog,
    closeDialog,
    submit,
  }
}
