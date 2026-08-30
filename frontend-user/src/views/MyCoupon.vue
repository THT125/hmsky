<template>
  <div style="min-height:100vh;background:#f7f8fa">
    <van-nav-bar title="我的优惠券" left-text="返回" @click-left="$router.back()" />
    <van-tabs v-model:active="active" @change="load">
      <van-tab title="未使用"></van-tab>
      <van-tab title="已使用"></van-tab>
      <van-tab title="已过期"></van-tab>
    </van-tabs>
    <div style="padding:12px">
      <div v-for="c in coupons" :key="c.id" :style="{display:'flex',background:'#fff',borderRadius:'8px',marginBottom:'10px',overflow:'hidden',opacity:c.status!==0?0.6:1}">
        <div style="width:90px;background:#ee0a24;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center">
          <div style="font-size:20px;font-weight:bold">{{ c.type===1 ? '¥'+c.amount : c.amount+'折' }}</div>
          <div style="font-size:11px;opacity:0.85">{{ c.type===1 ? '满减券' : '折扣券' }}</div>
        </div>
        <div style="flex:1;padding:10px 12px">
          <div style="font-size:15px;font-weight:500">{{ c.name }}</div>
          <div style="color:#999;font-size:12px;margin-top:4px">
            {{ Number(c.minAmount)>0 ? '满 ¥'+c.minAmount+' 可用' : '无门槛' }}
            · {{ c.status===0 && c.expireTime ? '有效期至 '+String(c.expireTime).slice(0,10) : '领取于 '+String(c.createTime||'').slice(0,10) }}
          </div>
        </div>
      </div>
      <div v-if="!coupons.length" style="text-align:center;padding:60px 0;color:#999">暂无优惠券,去领券中心看看吧</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import request from '@/utils/request'

const active = ref(0)
const coupons = ref([])
const statusMap = [0, 1, 2]  // tab 索引 → 状态参数(未用/已用/过期)

async function load() {
  coupons.value = (await request.get('/user/coupon/my', { params: { status: statusMap[active.value] } })) || []
}

onMounted(load)
</script>
