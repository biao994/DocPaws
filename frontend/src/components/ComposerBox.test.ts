import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ComposerBox from './ComposerBox.vue'

describe('ComposerBox', () => {
  it('renders placeholder and emits send when enabled', async () => {
    const wrapper = mount(ComposerBox, {
      props: {
        modelValue: '测试问题',
        placeholder: '请输入问题',
        disabledSend: false,
      },
    })

    expect(wrapper.find('.composer-textarea').attributes('placeholder')).toBe('请输入问题')
    await wrapper.find('.composer-send-btn').trigger('click')
    expect(wrapper.emitted('send')).toHaveLength(1)
  })

  it('does not emit send when disabled', async () => {
    const wrapper = mount(ComposerBox, {
      props: {
        modelValue: '',
        disabledSend: true,
      },
    })

    await wrapper.find('.composer-send-btn').trigger('click')
    expect(wrapper.emitted('send')).toBeUndefined()
  })
})
