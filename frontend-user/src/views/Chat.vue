<template>
  <div style="min-height:100vh;background:#f7f8fa;display:flex;flex-direction:column">
    <van-nav-bar title="联系商家" left-text="返回" @click-left="$router.back()" />
    <!-- 消息列表 -->
    <div ref="listRef" style="flex:1;overflow-y:auto;padding:12px">
      <div v-for="m in messages" :key="m.id"
           :style="{display:'flex',flexDirection:'column',alignItems:m.senderType==='user'?'flex-end':'flex-start',marginBottom:'10px'}">
        <div :style="{
          maxWidth:'70%',padding:'8px 12px',borderRadius:'8px',fontSize:'14px',wordBreak:'break-all',
          background:m.senderType==='user'?'#ee0a24':'#fff',color:m.senderType==='user'?'#fff':'#323233'
        }">{{ m.content }}</div>
        <div style="font-size:11px;color:#bbb;margin-top:2px">{{ formatTime(m.createTime) }}</div>
      </div>
      <div v-if="!messages.length" style="text-align:center;padding:60px 0;color:#999">
        还没有聊天记录,有问题可以留言给商家
      </div>
    </div>
    <!-- 输入区 -->
    <div style="display:flex;gap:8px;padding:10px 12px;background:#fff;align-items:center">
      <van-field v-model="input" placeholder="请输入要咨询的问题" :maxlength="500" @keyup.enter="send" />
      <van-button type="danger" size="small" :loading="sending" @click="send">发送</van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { showToast } from 'vant'
import request from '@/utils/request'

const messages = ref([])
const input = ref('')
const sending = ref(false)
const listRef = ref(null)

// 时间显示:当天显示 HH:mm,跨天显示 MM-DD HH:mm
function formatTime(t) {
  if (!t) return ''
  const d = new Date(String(t).replace(' ', 'T'))
  if (isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  const today = new Date()
  if (d.toDateString() === today.toDateString()) return hm
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${hm}`
}

function scrollToBottom() {
  nextTick(() => { if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight })
}

async function load() {
  messages.value = (await request.get('/user/chat/messages')) || []
  scrollToBottom()
  // 进入即已读(商家回复的未读消息)
  try { await request.post('/user/chat/read') } catch {}
}

async function send() {
  const content = input.value.trim()
  if (!content) { showToast('请输入内容'); return }
  sending.value = true
  try {
    const msg = await request.post('/user/chat/messages', { content })
    messages.value.push(msg)
    input.value = ''
    scrollToBottom()
  } finally { sending.value = false }
}

// 商家回复实时推送
function onChatPush() {
  // 重新拉取最新消息(简单可靠;消息量小)
  load()
}

onMounted(() => {
  load()
  window.addEventListener('chat-push-user', onChatPush)
})
onBeforeUnmount(() => window.removeEventListener('chat-push-user', onChatPush))
</script>
