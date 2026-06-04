import { ref } from 'vue'

export function useAttachmentPicker() {
  const inputRef = ref<HTMLInputElement | null>(null)
  const fileName = ref('')

  const open = () => {
    inputRef.value?.click()
  }

  const clear = () => {
    fileName.value = ''
  }

  const onChange = (event: Event) => {
    const input = event.target as HTMLInputElement
    fileName.value = input.files?.[0]?.name || ''
    input.value = ''
  }

  return {
    inputRef,
    fileName,
    open,
    clear,
    onChange,
  }
}
