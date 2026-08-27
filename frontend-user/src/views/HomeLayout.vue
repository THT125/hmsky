<template>
  <div style="padding-bottom:50px">
    <router-view />
  </div>
  <van-tabbar v-model="active" route>
    <van-tabbar-item to="/home" icon="shop-o">首页</van-tabbar-item>
    <van-tabbar-item to="/cart" icon="cart-o">购物车</van-tabbar-item>
    <van-tabbar-item to="/orders" icon="orders-o">订单</van-tabbar-item>
    <van-tabbar-item to="/mine" icon="contact">我的</van-tabbar-item>
  </van-tabbar>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { showNotify } from 'vant'

const active = ref(0)
let ws = null

// WebSocket 连接(用户端):接收管理端订单状态变更推送(type=3)
// sid 格式 user-{userId}-{随机}:后端按 userId 定向推送,其他用户收不到本用户订单通知
function connectWs() {
  const userId = localStorage.getItem('userId') || '0'
  ws = new WebSocket(`ws://${location.host}/ws/user-${userId}-${Date.now()}`)
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data)
      if (msg.type === 3) {
        // 订单状态变更:提示并广播事件,订单列表/详情页自动刷新
        showNotify({ type: 'primary', message: msg.content })
        window.dispatchEvent(new CustomEvent('order-status-change'))
      } else if (msg.type === 4) {
        // 店铺营业状态变更:提示并广播事件,首页状态条自动更新
        showNotify({ type: msg.content.includes('打烊') ? 'warning' : 'success', message: msg.content })
        window.dispatchEvent(new CustomEvent('shop-status-change'))
      } else if (msg.type === 5) {
        // 菜单变更:首页分类/菜品自动刷新
        window.dispatchEvent(new CustomEvent('menu-update'))
      } else if (msg.type === 6) {
        // 客服消息:提示并广播事件,聊天页实时追加
        showNotify({ type: 'primary', message: '商家回复: ' + msg.content })
        window.dispatchEvent(new CustomEvent('chat-push-user'))
      }
    } catch {}
  }
  ws.onclose = () => { setTimeout(connectWs, 5000) }
}

onMounted(connectWs)
onBeforeUnmount(() => { if (ws) ws.close() })
</script>
