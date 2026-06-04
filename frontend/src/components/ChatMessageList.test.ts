import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChatMessageList from './ChatMessageList.vue'

describe('ChatMessageList', () => {
  it('renders user and assistant messages', () => {
    const wrapper = mount(ChatMessageList, {
      props: {
        variant: 'page',
        messages: [
          { id: 'u1', role: 'user', content: '你好' },
          { id: 'a1', role: 'assistant', content: '您好，有什么可以帮您？' },
        ],
      },
    })

    expect(wrapper.text()).toContain('你好')
    expect(wrapper.text()).toContain('您好，有什么可以帮您？')
  })

  it('shows citation sources for assistant messages', () => {
    const wrapper = mount(ChatMessageList, {
      props: {
        messages: [
          {
            id: 'a1',
            role: 'assistant',
            content: '根据文档…',
            citations: [
              {
                chunk_id: 'c1',
                snippet: '引用片段',
                source: 'demo.pdf',
                page_no: 1,
              },
            ],
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('引用来源')
    expect(wrapper.text()).toContain('demo.pdf')
    expect(wrapper.text()).toContain('引用片段')
  })
})
