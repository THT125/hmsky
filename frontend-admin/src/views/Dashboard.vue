<template>
  <div>
    <!-- 今日指标卡片 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="4" v-for="card in cards" :key="card.label">
        <el-card shadow="hover">
          <div style="text-align:center">
            <div style="color:#999;font-size:14px">{{ card.label }}</div>
            <div style="font-size:28px;font-weight:bold;margin-top:8px;color:#303133">{{ card.value }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 订单概览 -->
    <el-card title="今日订单概览" style="margin-bottom:16px">
      <template #header><span>今日订单概览</span></template>
      <el-row :gutter="16">
        <el-col :span="4" v-for="o in orderCards" :key="o.label">
          <el-statistic :title="o.label" :value="o.value" />
        </el-col>
      </el-row>
    </el-card>

    <!-- 菜品/套餐概览 -->
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card>
          <template #header><span>菜品概览</span></template>
          <el-row>
            <el-col :span="12"><el-statistic title="已启售" :value="dishData.sold" /></el-col>
            <el-col :span="12"><el-statistic title="已停售" :value="dishData.discontinued" /></el-col>
          </el-row>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header><span>套餐概览</span></template>
          <el-row>
            <el-col :span="12"><el-statistic title="已启售" :value="setmealData.sold" /></el-col>
            <el-col :span="12"><el-statistic title="已停售" :value="setmealData.discontinued" /></el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import request from '@/utils/request'

const cards = ref([])
const orderCards = ref([])
const dishData = reactive({ sold: 0, discontinued: 0 })
const setmealData = reactive({ sold: 0, discontinued: 0 })

async function fetchData() {
  const biz = await request.get('/admin/workspace/businessData')
  cards.value = [
    { label: '今日营业额', value: '¥' + (biz.turnover || 0) },
    { label: '有效订单数', value: biz.validOrderCount || 0 },
    { label: '订单完成率', value: (biz.orderCompletionRate * 100).toFixed(0) + '%' },
    { label: '平均客单价', value: '¥' + (biz.unitPrice || 0) },
    { label: '新增用户数', value: biz.newUsers || 0 },
  ]

  const ov = await request.get('/admin/workspace/overviewOrders')
  orderCards.value = [
    { label: '全部', value: ov.allOrders || 0 },
    { label: '待接单', value: ov.waitingOrders || 0 },
    { label: '待派送', value: ov.deliveredOrders || 0 },
    { label: '已完成', value: ov.completedOrders || 0 },
    { label: '已取消', value: ov.cancelledOrders || 0 },
  ]

  const d = await request.get('/admin/workspace/overviewDishes')
  Object.assign(dishData, d)
  const s = await request.get('/admin/workspace/overviewSetmeals')
  Object.assign(setmealData, s)
}

// 收到 WebSocket 新订单推送时自动刷新工作台数据
// 30s 轮询:覆盖定时任务导致的订单/统计变化
let pollTimer = null
onMounted(() => {
  fetchData()
  window.addEventListener('order-push', fetchData)
  pollTimer = setInterval(fetchData, 30000)
})
onBeforeUnmount(() => {
  window.removeEventListener('order-push', fetchData)
  clearInterval(pollTimer)
})
</script>
