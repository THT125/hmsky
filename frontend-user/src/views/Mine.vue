<template>
  <div>
    <div style="text-align:center;padding:30px 0;background:#fff;margin-bottom:12px" @click="$router.push('/profile')">
      <van-image v-if="avatar" :src="avatar" width="56" height="56" round fit="cover" />
      <van-icon v-else name="contact" size="48" color="#1989fa" />
      <div style="font-size:18px;font-weight:bold;margin-top:8px">{{ displayName }}</div>
      <div style="color:#999;font-size:13px;margin-top:4px">{{ phone || ('用户ID: ' + userId) }}</div>
      <div style="color:#1989fa;font-size:12px;margin-top:8px">点击编辑资料 ›</div>
    </div>
    <van-cell-group style="border-radius:8px;overflow:hidden">
      <van-cell title="我的地址" is-link icon="location-o" to="/address" />
      <van-cell title="我的订单" is-link icon="orders-o" to="/orders" />
      <van-cell title="联系商家" is-link icon="chat-o" to="/chat" />
      <van-cell title="修改密码" is-link icon="lock" to="/change-password" />
      <van-cell title="退出登录" is-link icon="close" @click="logout" />
    </van-cell-group>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showSuccessToast } from 'vant'
import request from '@/utils/request'
import { logoutLocal } from '@/utils/auth'

const router = useRouter()
const profile = ref({})

const displayName = computed(() => profile.value.username || localStorage.getItem('username') || '-')
const avatar = computed(() => profile.value.avatar || '')
const phone = computed(() => profile.value.phone || '')
const userId = computed(() => profile.value.id || localStorage.getItem('userId') || '-')

async function fetchProfile() {
  try {
    profile.value = await request.get('/user/user/profile')
  } catch {}
}

async function logout() {
  try {
    await showConfirmDialog({ title: '提示', message: '确认退出登录吗？' })
  } catch {
    return
  }
  try {
    await request.post('/user/user/logout')
  } catch {}
  logoutLocal()
  showSuccessToast('已退出登录')
  router.replace('/login')
}

onMounted(fetchProfile)
</script>
