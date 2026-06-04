import { expect, test } from '@playwright/test'

const mockUser = {
  id: 'user-smoke-1',
  email: 'smoke@docpaws.test',
  username: 'Smoke',
}

function jsonData(data: unknown) {
  return {
    contentType: 'application/json',
    body: JSON.stringify({ data }),
  }
}

test.describe('DocPaws smoke', () => {
  test('login page renders', async ({ page }) => {
    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill({ status: 401, ...jsonData(null) })
    })

    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'DocPaws' })).toBeVisible()
    await expect(page.locator('form').getByRole('button', { name: '登录' })).toBeVisible()
  })

  test('authenticated home loads and can send a mocked chat', async ({ page }) => {
    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonData(mockUser))
    })
    await page.route('**/api/v1/knowledge-bases', async (route) => {
      await route.fulfill(
        jsonData({
          items: [{ id: 'kb-smoke-1', name: '演示知识库', created_at: new Date().toISOString() }],
        }),
      )
    })
    await page.route('**/api/v1/conversations**', async (route) => {
      await route.fulfill(jsonData({ items: [], total: 0, page: 1, page_size: 50 }))
    })
    await page.route('**/api/v1/chat/stream', async (route) => {
      const sse = [
        'data: {"event":"meta","conversation_id":"conv-smoke-1"}\n\n',
        'data: {"event":"answer_chunk","content":"你好，这是 smoke 测试回答。"}\n\n',
        'data: {"event":"finished","finished":true,"citations":[{"chunk_id":"c1","snippet":"引用片段","source":"demo.pdf","page_no":1}]}\n\n',
      ].join('')
      await route.fulfill({
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
        body: sse,
      })
    })

    await page.goto('/')
    await expect(page.getByText('猫爪轻轻一拍，就给你答案')).toBeVisible()

    await page.getByRole('button', { name: '@' }).click()
    await page.getByText('演示知识库').click()

    const textarea = page.locator('textarea').first()
    await textarea.fill('Smoke 测试问题')
    await expect(page.locator('.composer-send-btn').first()).toBeEnabled()
    await page.locator('.composer-send-btn').first().click()

    await expect(page.locator('.modal-message-text', { hasText: '你好，这是 smoke 测试回答。' })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('引用来源')).toBeVisible()
    await expect(page.getByText('demo.pdf')).toBeVisible()
  })
})
