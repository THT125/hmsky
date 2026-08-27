<template>
  <el-container style="height:100vh">
    <!-- 侧边栏 -->
    <el-aside width="220px" style="background:#304156;overflow-y:auto">
      <div style="height:60px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:18px;font-weight:bold;border-bottom:1px solid #4a5a6a">
        苍穹外卖管理端
      </div>
      <el-menu
        :default-active="route.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
        style="border-right:none"
      >
        <el-menu-item index="/dashboard"><el-icon><Monitor /></el-icon>工作台</el-menu-item>
        <el-menu-item index="/employee"><el-icon><User /></el-icon>员工管理</el-menu-item>
        <el-menu-item index="/category"><el-icon><Grid /></el-icon>分类管理</el-menu-item>
        <el-menu-item index="/dish"><el-icon><DishDot /></el-icon>菜品管理</el-menu-item>
        <el-menu-item index="/setmeal"><el-icon><Collection /></el-icon>套餐管理</el-menu-item>
        <el-menu-item index="/order"><el-icon><Document /></el-icon>订单管理</el-menu-item>
        <el-menu-item index="/chat"><el-icon><ChatDotRound /></el-icon>客服消息</el-menu-item>
        <el-menu-item index="/report"><el-icon><DataAnalysis /></el-icon>数据统计</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶部栏 -->
      <el-header style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #dcdfe6;height:60px">
        <span style="font-size:16px;font-weight:500">{{ $route.meta.title || '管理端' }}</span>
        <div style="display:flex;align-items:center;gap:12px">
          <el-switch
            v-model="shopOpen"
            active-text="营业"
            inactive-text="打烊"
            @change="toggleShop"
          />
          <span>{{ username }}</span>
          <el-button text @click="logout">退出</el-button>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main style="background:#f0f2f5">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()
const route = useRoute()
const username = ref(localStorage.getItem('adminName') || '')
const shopOpen = ref(true)
let ws = null

// 店铺状态
async function fetchShopStatus() {
  const s = await request.get('/admin/shop/status')
  shopOpen.value = s === 1
}
async function toggleShop(val) {
  await request.put(`/admin/shop/${val ? 1 : 0}`)
}

// WebSocket 推送(新订单/催单)
function connectWs() {
  ws = new WebSocket(`ws://${location.host}/ws/admin-console`)
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data)
    if (msg.type === 1) {
      ElNotification({ title: '新订单', message: msg.content, type: 'info' })
      // 广播事件:订单页/工作台自动刷新数据
      window.dispatchEvent(new CustomEvent('order-push'))
    } else if (msg.type === 2) {
      ElNotification({ title: '催单提醒', message: msg.content, type: 'warning' })
    } else if (msg.type === 6) {
      // 客服消息:提示 + 广播事件,客服页会话列表自动刷新
      const from = msg.chat && msg.chat.userId
      ElNotification({ title: '用户消息', message: msg.content, type: 'info' })
      window.dispatchEvent(new CustomEvent('chat-push-admin'))
    }
  }
  ws.onclose = () => { setTimeout(connectWs, 5000) }
}

function logout() {
  request.post('/admin/employee/logout').finally(() => {
    localStorage.removeItem('adminToken')
    localStorage.removeItem('adminName')
    router.push('/login')
  })
}

import { ElNotification } from 'element-plus'

onMounted(() => {
  fetchShopStatus()
  connectWs()
})
onBeforeUnmount(() => {
  if (ws) ws.close()
})
</script>
