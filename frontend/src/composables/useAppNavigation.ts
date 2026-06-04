import { useRouter } from 'vue-router'

export function useAppNavigation() {
  const router = useRouter()

  return {
    goHome: () => router.push({ name: 'home' }),
    goKb: () => router.push({ name: 'kb' }),
    goHistory: (conversationId?: string) =>
      router.push({
        name: 'history',
        query: conversationId ? { id: conversationId } : {},
      }),
  }
}
