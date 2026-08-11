<template>
  <div>
    <van-nav-bar title="我的订单" />
    <van-tabs v-model:active="activeTab" @change="fetchOrders">
      <van-tab title="全部" name="" />
      <van-tab title="待付款" name="1" />
      <van-tab title="待接单" name="2" />
      <van-tab title="已完成" name="5" />
      <van-tab title="已取消" name="6" />
    </van-tabs>
    <van-pull-refresh v-model="refreshing" @refresh="fetchOrders">
      <van-list v-model:loading="loading" :finished="finished" @load="loadMore">
        <div v-for="o in orders" :key="o.id" style="background:#fff;margin:10px;padding:12px;border-radius:8px" @click="$router.push(`/order/detail/${o.id}`)">
          <div style="display:flex;justify-content:space-between;margin-bottom:8px">
            <span style="color:#999;font-size:13px">{{ o.orderTime?.slice(0,16) }}</span>
            <van-tag :type="['','warning','primary','','info','success','danger'][o.status]" size="medium">{{ statusText[o.status] }}</van-tag>
          </div>
          <div v-for="d in o.orderDetailList" :key="d.id" style="display:flex;align-items:center;margin-bottom:4px">
            <span style="flex:1;font-size:14px">{{ d.name }} ×{{ d.number }}</span>
            <span style="color:#666;font-size:13px">¥{{ d.amount }}</span>
          </div>
          <div style="text-align:right;font-weight:500;margin-top:6px">合计: ¥{{ o.amount }}</div>
          <div v-if="['1','2','3','4','5'].includes(String(o.status))" style="text-align:right;margin-top:6px">
            <van-button v-if="o.status===1||o.status===2" size="small" type="danger" @click.stop="cancel(o)">取消</van-button>
            <van-button v-if="o.status===2" size="small" type="warning" @click.stop="remind(o)">催单</van-button>
            <van-button size="small" plain @click.stop="$router.push(`/order/detail/${o.id}`)">详情</van-button>
          </div>
        </div>
      </van-list>
    </van-pull-refresh>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { showToast } from 'vant'
import request from '@/utils/request'

const statusText = { 1: '待付款', 2: '待接单', 3: '已接单', 4: '派送中', 5: '已完成', 6: '已取消' }
const activeTab = ref('')
const orders = ref([])
const page = ref(1)
const loading = ref(false), finished = ref(false), refreshing = ref(false)

async function fetchOrders() {
  page.value = 1; orders.value = []; finished.value = false
  await loadMore()
}

// 轮询静默刷新:仅更新第一页数据,不重置分页位置(避免用户浏览位置丢失)
async function pollRefresh() {
  try {
    const res = await request.get('/user/order/historyOrders', { params: { page: 1, pageSize: 10, status: activeTab.value || undefined } })
    if (orders.value.length === 0) {
      orders.value = res.records || []
      finished.value = orders.value.length >= (res.total || 0)
    } else {
      // 已有列表:合并新数据,更新已存在订单的状态
      const newRecords = res.records || []
      const map = new Map(orders.value.map(o => [o.id, o]))
      for (const o of newRecords) {
        const old = map.get(o.id)
        if (old) { old.status = o.status; old.amount = o.amount; old.orderDetailList = o.orderDetailList }
        else map.set(o.id, o)
      }
      orders.value = [...map.values()].sort((a, b) => new Date(b.orderTime) - new Date(a.orderTime))
      finished.value = orders.value.length >= (res.total || 0)
    }
  } catch {}
}

async function loadMore() {
  loading.value = true
  const res = await request.get('/user/order/historyOrders', { params: { page: page.value, pageSize: 10, status: activeTab.value || undefined } })
  orders.value.push(...(res.records || []))
  finished.value = orders.value.length >= (res.total || 0)
  page.value++; loading.value = false; refreshing.value = false
}

async function cancel(o) {
  await request.put(`/user/order/cancel/${o.id}`)
  showToast('已取消'); o.status = 6
}

async function remind(o) {
  await request.get(`/user/order/reminder/${o.id}`)
  showToast('已催单')
}

// 收到 WebSocket 订单状态变更推送时自动刷新
// 30s 轮询:覆盖定时任务(超时自动取消)导致的订单变化
let pollTimer = null
onMounted(() => {
  window.addEventListener('order-status-change', pollRefresh)
  pollTimer = setInterval(pollRefresh, 30000)
})
onBeforeUnmount(() => {
  window.removeEventListener('order-status-change', pollRefresh)
  clearInterval(pollTimer)
})
</script>
