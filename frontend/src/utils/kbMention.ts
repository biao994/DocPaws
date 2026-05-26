/**
 * 在输入框中插入 @知识库 提及，并清理手输的 @ 触发符，避免重复 @。
 */
export function applyKbMentionToInput(raw: string, kbName: string): string {
  const mention = `@${kbName} `
  let text = raw
  // 已有完整开头提及时直接返回
  if (text.startsWith(mention)) return text
  // 去掉开头旧提及
  text = text.replace(/^@\S+\s+/, '')
  // 去掉末尾未完成的 @ 提及（含用户只输入单个 @ 的情况）
  text = text.replace(/@\S*$/, '')
  return mention + text.trimStart()
}
