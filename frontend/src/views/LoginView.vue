<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-brand">
        <MascotLogo :size="48" />
        <h1>DocPaws</h1>
        <p class="sub">登录后可使用知识库与对话</p>
      </div>

      <div class="tabs">
        <button type="button" :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button type="button" :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <form class="auth-form" @submit.prevent="submit">
        <label v-if="mode === 'register'" class="field">
          <span>用户名</span>
          <input v-model.trim="username" type="text" autocomplete="username" maxlength="100" />
        </label>
        <label class="field">
          <span>邮箱</span>
          <input v-model.trim="email" type="email" autocomplete="email" />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" />
        </label>
        <p v-if="hint" class="hint">{{ hint }}</p>
        <button type="submit" class="btn-submit" :disabled="submitting">
          {{ mode === 'login' ? '登录' : '注册并登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import MascotLogo from '../components/MascotLogo.vue'
import { currentUser } from '../auth/session'
import * as authApi from '../api/auth'

const emit = defineEmits<{ success: [] }>()

type Mode = 'login' | 'register'
const mode = ref<Mode>('login')

const username = ref('')
const email = ref('')
const password = ref('')
const hint = ref('')
const submitting = ref(false)

const submit = async () => {
  hint.value = ''
  const em = email.value
  const pw = password.value
  if (!em || !pw) {
    hint.value = '请填写邮箱与密码'
    return
  }
  if (mode.value === 'register' && username.value.length < 1) {
    hint.value = '请填写用户名'
    return
  }
  if (pw.length < 8) {
    hint.value = '密码至少 8 位'
    return
  }

  submitting.value = true
  try {
    if (mode.value === 'login') {
      currentUser.value = await authApi.login(em, pw)
    } else {
      currentUser.value = await authApi.register(em, username.value.trim(), pw)
    }
    emit('success')
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { message?: string; user_hint?: string } } }
    hint.value =
      ax.response?.data?.user_hint || ax.response?.data?.message || '请求失败，请检查网络或账号信息'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, #f7f9fc 0%, #eef3fb 100%);
  padding: 24px;
  box-sizing: border-box;
}

.auth-card {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.08);
  padding: 28px 26px 32px;
  box-sizing: border-box;
}

.auth-brand {
  text-align: center;
  margin-bottom: 22px;
}

.auth-brand h1 {
  margin: 10px 0 6px;
  font-size: 1.35rem;
  font-weight: 650;
  color: #111827;
}

.sub {
  margin: 0;
  font-size: 0.88rem;
  color: #6b7280;
}

.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 20px;
  border-radius: 10px;
  background: #f3f4f6;
  padding: 4px;
}

.tabs button {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  color: #6b7280;
}

.tabs button.active {
  background: #fff;
  color: #111827;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field span {
  display: block;
  font-size: 0.8rem;
  color: #374151;
  margin-bottom: 6px;
}

.field input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 0.95rem;
}

.field input:focus {
  outline: none;
  border-color: var(--dp-primary);
  box-shadow: 0 0 0 3px rgba(24, 160, 88, 0.22);
}

.hint {
  margin: 0;
  font-size: 0.82rem;
  color: #b45309;
}

.btn-submit {
  margin-top: 6px;
  border: none;
  border-radius: 10px;
  padding: 12px;
  font-size: 0.95rem;
  font-weight: 600;
  color: #fff;
  background: var(--dp-primary);
  cursor: pointer;
}

.btn-submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-submit:not(:disabled):hover {
  background: var(--dp-primary-hover);
}
</style>
