<template>
  <div style="min-height:100vh;background:#f7f8fa">
    <van-nav-bar title="领券中心" left-text="返回" @click-left="$router.back()" />
    <div style="padding:12px">
      <div v-for="c in coupons" :key="c.id" style="display:flex;background:#fff;border-radius:8px;margin-bottom:10px;overflow:hidden">
        <!-- 左侧面值 -->
        <div style="width:90px;background:#ee0a24;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center">
          <div style="font-size:22px;font-weight:bold">{{ c.type===1 ? '¥'+c.amount : c.amount+'折' }}</div>
          <div style="font-size:11px;opacity:0.85">{{ c.type===1 ? '满减券' : '折扣券' }}</div>
        </div>
        <!-- 右侧信息 -->
        <div style="flex:1;padding:10px 12px">
          <div style="font-size:15px;font-weight:500">{{ c.name }}</div>
          <div style="color:#999;font-size:12px;margin-top:4px">
            {{ Number(c.minAmount)>0 ? '满 ¥'+c.minAmount+' 可用' : '无门槛' }}
            · 每人限领 {{ c.perUserLimit }} 张
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
            <span style="color:#999;font-size:12px">
              <template v-if="c.grabStatus==='available'">剩余 {{ c.stock }} 张</template>
              <template v-else-if="c.grabStatus==='not_started'">未开始</template>
              <template v-else-if="c.grabStatus==='ended'">已结束</template>
              <template v-else-if="c.grabStatus==='sold_out'">已抢完</template>
              <template v-else>已领取</template>
            </span>
            <van-button size="small" round type="danger" plain
              :disabled="c.grabStatus!=='available'" :loading="grabbingId===c.id"
              @click="grab(c)">{{ btnText(c.grabStatus) }}</van-button>
          </div>
        </div>
      </div>
      <div v-if="!coupons.length" style="text-align:center;padding:60px 0;color:#999">暂无可用优惠券</div>
    </div>
    <van-cell title="我的优惠券" is-link icon="coupon-o" to="/my-coupon" style="margin-top:4px" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import request from '@/utils/request'

const coupons = ref([])
const grabbingId = ref(0)

function btnText(s) {
  return { available: '立即领取', grabbed: '已领取', sold_out: '已抢完', not_started: '未开始', ended: '已结束' }[s] || '立即领取'
}

async function load() {
  coupons.value = (await request.get('/user/coupon/list')) || []
}

async function grab(c) {
  grabbingId.value = c.id
  try {
    await request.post(`/user/coupon/grab/${c.id}`)
    showToast('领取成功!')
    load()
  } finally { grabbingId.value = 0 }
}

onMounted(load)
</script>
