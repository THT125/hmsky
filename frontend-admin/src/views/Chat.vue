<template>
  <el-card style="height:calc(100vh - 140px);display:flex;flex-direction:column">
    <div style="display:flex;flex:1;min-height:0">
      <!-- 左侧:会话列表 -->
      <div style="width:280px;border-right:1px solid #eee;overflow-y:auto">
        <div v-for="s in sessions" :key="s.userId"
             @click="selectSession(s)"
             :style="{padding:'10px 14px',cursor:'pointer',borderBottom:'1px solid #f5f5f5',background:current?.userId===s.userId?'#f0f7ff':'#fff'}">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-weight:500">{{ s.username }} <span style="color:#999;font-weight:normal;font-size:12px">{{ s.phone }}</span></span>
            <el-badge v-if="s.unread > 0" :value="s.unread" :max="99" />
          </div>
          <div style="color:#999;font-size:12px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
            {{ s.lastContent }}
          </div>
          <div style="color:#ccc;font-size:11px;margin-top:2px">{{ formatTime(s.lastTime) }}</div>
        </div>
        <div v-if="!sessions.length" style="text-align:center;color:#999;padding:40px 0">暂无会话</div>
      </div>

      <!-- 右侧:聊天窗口 -->
      <div style="flex:1;display:flex;flex-direction:column;min-width:0">
        <template v-if="current">
          <div style="padding:10px 16px;border-bottom:1px solid #eee;font-weight:500">
            与 {{ current.username }} 的会话
          </div>
          <div ref="listRef" style="flex:1;overflow-y:auto;padding:14px;background:#f7f8fa">
            <div v-for="m in messages" :key="m.id"
                 :style="{display:'flex',flexDirection:'column',alignItems:m.senderType==='admin'?'flex-end':'flex-start',marginBottom:'10px'}">
              <div :style="{
                maxWidth:'70%',padding:'8px 12px',borderRadius:'8px',fontSize:'14px',wordBreak:'break-all',
                background:m.senderType==='admin'?'#409EFF':'#fff',color:m.senderType==='admin'?'#fff':'#333'
              }">{{ m.content }}</div>
              <div style="font-size:11px;color:#bbb;margin-top:2px">{{ formatTime(m.createTime) }}</div>
            </div>
            <div v-if="!messages.length" style="text-align:center;color:#999;padding:40px 0">暂无消息,等待用户咨询</div>
          </div>
          <div style="display:flex;gap:8px;padding:10px 14px;border-top:1px solid #eee;align-items:center">
            <el-input v-model="reply" placeholder="输入回复内容" @keyup.enter="send" :maxlength="500" />
            <el-button type="primary" :loading="sending" @click="send">发送</el-button>
          </div>
        </template>
        <div v-else style="flex:1;display:flex;align-items:center;justify-content:center;color:#999">
          选择左侧会话开始沟通
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import request from '@/utils/request'

const sessions = ref([])
const current = ref(null)
const messages = ref([])
const reply = ref('')
const sending = ref(false)
const listRef = ref(null)

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

async function loadSessions() {
  sessions.value = (await request.get('/admin/chat/sessions')) || []
}

async function selectSession(s) {
  current.value = s
  messages.value = (await request.get('/admin/chat/messages', { params: { userId: s.userId } })) || []
  scrollToBottom()
  try {
    await request.post('/admin/chat/read', null, { params: { userId: s.userId } })
    s.unread = 0
  } catch {}
}

async function send() {
  const content = reply.value.trim()
  if (!content || !current.value) return
  sending.value = true
  try {
    const msg = await request.post('/admin/chat/messages', { userId: current.value.userId, content })
    messages.value.push(msg)
    reply.value = ''
    scrollToBottom()
    loadSessions()  // 刷新会话列表(最后消息更新)
  } finally { sending.value = false }
}

// 用户新消息推送:刷新会话列表;若正在看该会话则追加并标记已读
async function onChatPush() {
  loadSessions()
  if (current.value) {
    messages.value = (await request.get('/admin/chat/messages', { params: { userId: current.value.userId } })) || []
    scrollToBottom()
    try {
      await request.post('/admin/chat/read', null, { params: { userId: current.value.userId } })
    } catch {}
  }
}

onMounted(() => {
  loadSessions()
  window.addEventListener('chat-push-admin', onChatPush)
})
onBeforeUnmount(() => window.removeEventListener('chat-push-admin', onChatPush))
</script>
