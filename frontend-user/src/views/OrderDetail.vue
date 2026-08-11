<template>
  <div>
    <van-nav-bar title="订单详情" left-text="返回" @click-left="$router.back()" />
    <div v-if="order" style="padding:12px">
      <van-cell-group style="border-radius:8px;overflow:hidden;margin-bottom:12px">
        <van-cell title="订单号" :value="order.number" />
        <van-cell title="状态" :value="statusText[order.status]" />
        <van-cell title="下单时间" :value="order.orderTime?.slice(0,16)" />
        <van-cell title="支付状态" :value="['未支付','已支付','退款'][order.payStatus]" />
        <van-cell title="备注" :value="order.remark || '-'" />
        <van-cell v-if="order.cancelReason" title="取消原因" :value="order.cancelReason" />
      </van-cell-group>
      <div style="background:#fff;border-radius:8px;padding:12px;margin-bottom:12px">
        <div style="font-weight:500;margin-bottom:8px">商品明细</div>
        <div v-for="d in order.orderDetailList" :key="d.id" style="display:flex;align-items:center;padding:6px 0;border-bottom:1px solid #f5f5f5">
          <span style="flex:1">{{ d.name }} ×{{ d.number }}</span>
          <span style="color:#666">¥{{ d.amount }}</span>
        </div>
        <div style="text-align:right;font-weight:500;margin-top:8px">实付: ¥{{ order.amount }}</div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <van-button v-if="order.status===1||order.status===2" type="danger" @click="cancel">取消订单</van-button>
        <van-button v-if="order.status===2" type="warning" @click="remind">催单</van-button>
        <van-button plain @click="repeat">再来一单</van-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { showToast } from 'vant'
import request from '@/utils/request'

const route = useRoute()
const order = ref(null)
const statusText = { 1: '待付款', 2: '待接单', 3: '已接单', 4: '派送中', 5: '已完成', 6: '已取消' }

async function fetch() {
  order.value = await request.get(`/user/order/orderDetail/${route.params.id}`)
}

async function cancel() { await request.put(`/user/order/cancel/${order.value.id}`); showToast('已取消'); fetch() }
async function remind() { await request.get(`/user/order/reminder/${order.value.id}`); showToast('已催单') }
async function repeat() {
  await request.post(`/user/order/repetition/${order.value.id}`)
  showToast('已加入购物车')
}

// 收到 WebSocket 订单状态变更推送时自动刷新
onMounted(() => {
  fetch()
  window.addEventListener('order-status-change', fetch)
})
onBeforeUnmount(() => { window.removeEventListener('order-status-change', fetch) })
</script>
