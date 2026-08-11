<template>
  <div>
    <el-card style="margin-bottom:16px">
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span>时间范围:</span>
        <el-date-picker v-model="range" type="daterange" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" />
        <el-button type="primary" @click="fetchAll">查询</el-button>
        <el-button @click="exportExcel">导出Excel报表</el-button>
      </div>
    </el-card>

    <!-- 4个图表 -->
    <el-row :gutter="16">
      <el-col :span="12" style="margin-bottom:16px">
        <el-card><template #header>营业额统计</template><div ref="chartTurnover" style="height:300px" /></el-card>
      </el-col>
      <el-col :span="12" style="margin-bottom:16px">
        <el-card><template #header>用户统计</template><div ref="chartUser" style="height:300px" /></el-card>
      </el-col>
      <el-col :span="12" style="margin-bottom:16px">
        <el-card><template #header>订单统计</template><div ref="chartOrder" style="height:300px" /></el-card>
      </el-col>
      <el-col :span="12" style="margin-bottom:16px">
        <el-card><template #header>销量Top10</template><div ref="chartTop10" style="height:300px" /></el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import request from '@/utils/request'

const range = ref([])

function fmt(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
const chartTurnover = ref(null), chartUser = ref(null), chartOrder = ref(null), chartTop10 = ref(null)
let instances = []

function initChart(ref, option) {
  if (ref) {
    const c = echarts.init(ref)
    c.setOption(option)
    instances.push(c)
    return c
  }
}

async function fetchAll() {
  // 未选择时间范围时默认取最近 7 天
  let b, e
  if (range.value && range.value.length === 2) {
    ;[b, e] = range.value
  } else {
    const end = new Date()
    const begin = new Date(end.getTime() - 6 * 24 * 3600 * 1000)
    b = fmt(begin)
    e = fmt(end)
    range.value = [b, e]
  }
  const t = await request.get('/admin/report/turnoverStatistics', { params: { begin: b, end: e } })
  const u = await request.get('/admin/report/userStatistics', { params: { begin: b, end: e } })
  const o = await request.get('/admin/report/ordersStatistics', { params: { begin: b, end: e } })
  const top = await request.get('/admin/report/top10', { params: { begin: b, end: e } })

  await nextTick()
  restoreCharts()

  const xTurnover = (t.dateList || '').split(',').filter(Boolean)
  const yTurnover = (t.turnoverList || '').split(',').filter(Boolean).map(Number)
  initChart(chartTurnover.value, {
    tooltip: { trigger: 'axis' },
    xAxis: { data: xTurnover },
    yAxis: {},
    series: [{ data: yTurnover, type: 'line', smooth: true, areaStyle: {} }],
  })

  const xUser = (u.dateList || '').split(',').filter(Boolean)
  initChart(chartUser.value, {
    tooltip: { trigger: 'axis' },
    legend: { data: ['新增用户', '累计用户'] },
    xAxis: { data: xUser },
    yAxis: {},
    series: [
      { name: '新增用户', data: (u.newUserList||'').split(',').filter(Boolean).map(Number), type: 'bar' },
      { name: '累计用户', data: (u.totalUserList||'').split(',').filter(Boolean).map(Number), type: 'line', smooth: true },
    ],
  })

  const xOrder = (o.dateList || '').split(',').filter(Boolean)
  initChart(chartOrder.value, {
    tooltip: { trigger: 'axis' },
    legend: { data: ['总订单', '有效订单'] },
    xAxis: { data: xOrder },
    yAxis: {},
    series: [
      { name: '总订单', data: (o.orderCountList||'').split(',').filter(Boolean).map(Number), type: 'bar' },
      { name: '有效订单', data: (o.validOrderCountList||'').split(',').filter(Boolean).map(Number), type: 'bar' },
    ],
  })

  const names = (top.nameList || '').split(',').filter(Boolean)
  const nums = (top.numberList || '').split(',').filter(Boolean).map(Number)
  initChart(chartTop10.value, {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: names.reverse(), axisLabel: { interval: 0 } },
    series: [{ data: nums.reverse(), type: 'bar', label: { show: true, position: 'right' } }],
  })
}

function restoreCharts() {
  instances.forEach(c => c.dispose())
  instances = []
}

async function exportExcel() {
  const resp = await fetch('/admin/report/export', { headers: { token: localStorage.getItem('adminToken') } })
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = '运营数据报表.xlsx'; a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

onMounted(fetchAll)
// 组件卸载时释放 ECharts 实例(避免内存泄漏)
onBeforeUnmount(() => {
  instances.forEach(c => c.dispose())
  instances = []
})
</script>
