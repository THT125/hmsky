<template>
  <div style="min-height:100vh;background:#f7f8fa">
    <van-nav-bar title="每日签到" left-text="返回" @click-left="$router.back()" />
    <!-- 头部:连续天数 + 规则 -->
    <div style="background:#ee0a24;color:#fff;padding:24px 16px;text-align:center">
      <div style="font-size:14px;opacity:0.9">已连续签到</div>
      <div style="font-size:42px;font-weight:bold;margin:6px 0">{{ status.consecutiveDays }}<span style="font-size:16px"> 天</span></div>
      <div style="font-size:12px;opacity:0.85">本月已签到 {{ status.totalDays }} 天 · 连续 5 天送 20 元无门槛券</div>
    </div>
    <!-- 本月签到日历 -->
    <div style="background:#fff;margin:12px;border-radius:8px;padding:16px">
      <div style="font-size:15px;font-weight:500;margin-bottom:12px">本月签到({{ currentMonth }})</div>
      <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:8px">
        <template v-for="(d, i) in status.monthDays" :key="i">
          <div :style="{
            width:36,height:36,display:'flex',alignItems:'center',justifyContent:'center',
            borderRadius:'50%',margin:'0 auto',fontSize:13,
            background:d===1 ? '#ee0a24' : '#f2f3f5',
            color:d===1 ? '#fff' : '#999',
          }">{{ i + 1 }}</div>
        </template>
      </div>
    </div>
    <!-- 签到按钮 -->
    <div style="margin:24px 16px">
      <van-button round block type="danger" :disabled="status.signedToday" :loading="signing" @click="doSign">
        {{ status.signedToday ? '今日已签到' : '立即签到' }}
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import request from '@/utils/request'

const status = ref({ signedToday: false, consecutiveDays: 0, monthDays: [], totalDays: 0 })
const signing = ref(false)
const currentMonth = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
})

async function load() {
  status.value = (await request.get('/user/sign/status')) || status.value
}

async function doSign() {
  signing.value = true
  try {
    const r = await request.post('/user/sign')
    showSuccessToast('签到成功!')
    if (r.reward) showToast('🎉 连续签到 5 天,获得 20 元无门槛优惠券!')
    load()
  } finally { signing.value = false }
}

onMounted(load)
</script>
