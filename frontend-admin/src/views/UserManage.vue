<template>
  <div>
    <el-card>
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <!-- ========== 用户列表 ========== -->
        <el-tab-pane label="用户列表" name="list">
          <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px">
            <el-input v-model="q.username" placeholder="用户名" clearable style="width:130px" @keyup.enter="search" />
            <el-input v-model="q.phone" placeholder="手机号" clearable style="width:130px" @keyup.enter="search" />
            <el-select v-model="q.status" placeholder="状态" clearable style="width:100px" @change="search">
              <el-option label="正常" :value="1" />
              <el-option label="封禁" :value="0" />
            </el-select>
            <el-date-picker v-model="dateRange" type="daterange" range-separator="~"
              start-placeholder="注册起" end-placeholder="注册止"
              value-format="YYYY-MM-DD" style="width:230px" @change="search" />
            <el-input-number v-model="q.minAmount" :min="0" :controls="false" placeholder="消费≥"
              style="width:100px" />
            <el-input-number v-model="q.maxAmount" :min="0" :controls="false" placeholder="消费≤"
              style="width:100px" />
            <el-button type="primary" @click="search">查询</el-button>
            <el-button @click="resetQuery">重置</el-button>
            <div style="margin-left:auto;display:flex;gap:8px">
              <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
              <el-button type="primary" :disabled="!selected.length" @click="openGrant">
                批量发券{{ selected.length ? `(${selected.length})` : '' }}
              </el-button>
            </div>
          </div>

          <el-table :data="tableData" stripe v-loading="loading" @selection-change="v => selected = v">
            <el-table-column type="selection" width="45" :selectable="row => row.status === 1" />
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="username" label="用户名" width="130" />
            <el-table-column prop="phone" label="手机号" width="125" />
            <el-table-column label="性别" width="60">
              <template #default="{row}">{{ row.sex === '1' ? '男' : row.sex === '0' ? '女' : '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="75">
              <template #default="{row}">
                <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
                  {{ row.status === 1 ? '正常' : '封禁' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="累计消费" width="100" align="right">
              <template #default="{row}">¥{{ Number(row.totalSpend || 0).toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="注册时间" width="155">
              <template #default="{row}">{{ fmt(row.createTime) }}</template>
            </el-table-column>
            <el-table-column label="最近登录" width="155">
              <template #default="{row}">{{ fmt(row.lastLoginTime) || '从未登录' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="170" fixed="right">
              <template #default="{row}">
                <el-button size="small" @click="openDetail(row)">详情</el-button>
                <el-button size="small" :type="row.status === 1 ? 'danger' : 'success'"
                  @click="toggleStatus(row)">{{ row.status === 1 ? '封禁' : '解封' }}</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination style="margin-top:16px;justify-content:flex-end"
            v-model:current-page="page" v-model:page-size="pageSize"
            :total="total" layout="total,prev,pager,next" @change="fetchPage" />
        </el-tab-pane>

        <!-- ========== 风险监控 ========== -->
        <el-tab-pane label="风险监控" name="risk">
          <div style="margin-bottom:12px;color:#909399;font-size:13px">
            基于登录日志实时分析:多 IP 登录(账号可能被盗)、同 IP 多账号(撞库)、登录失败率过高(被爆破)。
            IP 归属地需自行核查,系统不做解析(避免引入外部依赖)。
          </div>
          <el-table :data="riskData" stripe v-loading="riskLoading">
            <el-table-column label="风险等级" width="95">
              <template #default="{row}">
                <el-tag :type="row.riskLevel === 'RISK' ? 'danger' : 'warning'" size="small">
                  {{ row.riskLevel === 'RISK' ? '高危' : '关注' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="userId" label="用户ID" width="80" />
            <el-table-column prop="username" label="用户名" width="130" />
            <el-table-column prop="phone" label="手机号" width="125" />
            <el-table-column label="命中信号" min-width="240">
              <template #default="{row}">
                <el-tag v-for="s in row.signals" :key="s" type="warning" size="small"
                  style="margin:2px 4px 2px 0">{{ s }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="近期 IP" min-width="200">
              <template #default="{row}">
                <div v-for="ip in row.ips" :key="ip.ip" style="font-size:12px;line-height:18px">
                  <span :style="{ color: ip.shared ? '#f56c6c' : '#606266' }">{{ ip.ip }}</span>
                  <span style="color:#909399;margin-left:4px">{{ ip.region || '未知' }}</span>
                  <span style="color:#c0c4cc"> ×{{ ip.count }}</span>
                  <el-tag v-if="ip.shared" type="danger" size="small" style="margin-left:4px">共用</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{row}">
                <el-button size="small" @click="openDetailById(row.userId)">详情</el-button>
                <el-button size="small" type="danger" :disabled="row.status === 0"
                  @click="ban(row.userId, row.username)">封禁</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- ========== 用户详情抽屉 ========== -->
    <el-drawer v-model="drawerVisible" title="用户详情" size="640px">
      <div v-if="detail" v-loading="detailLoading">
        <!-- 基本信息 -->
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="用户名">{{ detail.username }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detail.phone }}</el-descriptions-item>
          <el-descriptions-item label="性别">
            {{ detail.sex === '1' ? '男' : detail.sex === '0' ? '女' : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detail.status === 1 ? 'success' : 'danger'" size="small">
              {{ detail.status === 1 ? '正常' : '封禁' }}
            </el-tag>
            <span v-if="detail.banReason" style="color:#f56c6c;font-size:12px;margin-left:6px">
              原因:{{ detail.banReason }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="注册时间">{{ fmt(detail.createTime) }}</el-descriptions-item>
          <el-descriptions-item label="最近登录">{{ fmt(detail.lastLoginTime) || '从未登录' }}</el-descriptions-item>
          <el-descriptions-item label="最近登录IP">
            {{ detail.lastLoginIp || '-' }}
            <span v-if="detail.lastLoginRegion" style="color:#909399;margin-left:6px">
              {{ detail.lastLoginRegion }}
            </span>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 统计卡片 -->
        <div style="display:flex;gap:12px;margin:16px 0">
          <div class="stat-box"><div class="stat-num">{{ detail.orderCount }}</div><div class="stat-label">下单总数</div></div>
          <div class="stat-box"><div class="stat-num">{{ detail.validOrderCount }}</div><div class="stat-label">已完成</div></div>
          <div class="stat-box"><div class="stat-num">¥{{ Number(detail.totalSpend || 0).toFixed(2) }}</div><div class="stat-label">累计消费</div></div>
        </div>

        <!-- 最近订单 -->
        <div style="font-weight:600;margin:16px 0 8px">最近订单</div>
        <el-table :data="detail.recentOrders" size="small" border>
          <el-table-column prop="number" label="订单号" width="170" />
          <el-table-column label="状态" width="90">
            <template #default="{row}">{{ ORDER_STATUS[row.status] || row.status }}</template>
          </el-table-column>
          <el-table-column label="金额" width="90" align="right">
            <template #default="{row}">¥{{ Number(row.amount).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="下单时间">
            <template #default="{row}">{{ fmt(row.orderTime) }}</template>
          </el-table-column>
        </el-table>

        <!-- 登录日志 -->
        <div style="font-weight:600;margin:16px 0 8px">登录日志</div>
        <el-table :data="logs" size="small" border v-loading="logsLoading">
          <el-table-column label="结果" width="70">
            <template #default="{row}">
              <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
                {{ row.status === 1 ? '成功' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="IP" width="210">
            <template #default="{row}">
              {{ row.ip }}
              <span v-if="row.region" style="color:#909399;font-size:12px;margin-left:4px">
                {{ row.region }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="userAgent" label="User-Agent" show-overflow-tooltip />
          <el-table-column label="时间" width="155">
            <template #default="{row}">{{ fmt(row.createTime) }}</template>
          </el-table-column>
        </el-table>
        <el-pagination style="margin-top:10px;justify-content:flex-end" small
          v-model:current-page="logPage" :page-size="10" :total="logTotal"
          layout="total,prev,pager,next" @change="fetchLogs" />
      </div>
    </el-drawer>

    <!-- ========== 封禁对话框 ========== -->
    <el-dialog v-model="banVisible" title="封禁用户" width="440px">
      <el-alert type="warning" :closable="false" style="margin-bottom:12px"
        title="封禁后该用户会立即被踢下线,且无法登录和下单。" />
      <el-input v-model="banReason" type="textarea" :rows="3" maxlength="200" show-word-limit
        placeholder="请填写封禁原因(必填,会记录到审计字段)" />
      <template #footer>
        <el-button @click="banVisible = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="confirmBan">确认封禁</el-button>
      </template>
    </el-dialog>

    <!-- ========== 批量发券对话框 ========== -->
    <el-dialog v-model="grantVisible" title="批量发券" width="460px">
      <el-form label-width="80px">
        <el-form-item label="优惠券">
          <el-select v-model="grantCouponId" placeholder="请选择要发放的优惠券" style="width:100%">
            <el-option v-for="c in couponOptions" :key="c.id"
              :label="`${c.name}(剩余 ${c.stock})`" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false"
        :title="`将发放给已选中的 ${selected.length} 位用户。已领取过的会自动跳过。`" />
      <template #footer>
        <el-button @click="grantVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="confirmGrant">确认发放</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const ORDER_STATUS = { 1: '待付款', 2: '待接单', 3: '已接单', 4: '派送中', 5: '已完成', 6: '已取消', 7: '退款' }

const activeTab = ref('list')
// ---- 列表 ----
const tableData = ref([]), loading = ref(false)
const page = ref(1), pageSize = ref(10), total = ref(0)
const q = reactive({ username: '', phone: '', status: null, minAmount: null, maxAmount: null })
const dateRange = ref([])
const selected = ref([])
const exporting = ref(false)
// ---- 风控 ----
const riskData = ref([]), riskLoading = ref(false)
// ---- 详情 ----
const drawerVisible = ref(false), detailLoading = ref(false), detail = ref(null)
const logs = ref([]), logsLoading = ref(false), logPage = ref(1), logTotal = ref(0)
let detailUserId = null
// ---- 对话框 ----
const banVisible = ref(false), banReason = ref(''), banTarget = ref(null)
const grantVisible = ref(false), grantCouponId = ref(null), couponOptions = ref([])
const submitting = ref(false)

function fmt(t) { return t ? String(t).replace('T', ' ').slice(0, 19) : '' }

function params() {
  return {
    username: q.username || undefined,
    phone: q.phone || undefined,
    status: q.status ?? undefined,
    begin: dateRange.value?.[0] || undefined,
    end: dateRange.value?.[1] || undefined,
    minAmount: q.minAmount ?? undefined,
    maxAmount: q.maxAmount ?? undefined,
  }
}

async function fetchPage() {
  loading.value = true
  try {
    const res = await request.get('/admin/user/page', {
      params: { ...params(), page: page.value, pageSize: pageSize.value },
    })
    tableData.value = res.records || []
    total.value = res.total || 0
  } finally { loading.value = false }
}

function search() { page.value = 1; fetchPage() }

function resetQuery() {
  Object.assign(q, { username: '', phone: '', status: null, minAmount: null, maxAmount: null })
  dateRange.value = []
  search()
}

async function fetchRisk() {
  riskLoading.value = true
  try { riskData.value = await request.get('/admin/user/risk') } finally { riskLoading.value = false }
}

function onTabChange(name) { if (name === 'risk') fetchRisk() }

// ---- 导出 ----
async function exportExcel() {
  exporting.value = true
  try {
    // 导出返回的是文件流,不能用 request 封装(它会把响应当 JSON 解包)
    const res = await axios.get('/admin/user/export', {
      params: params(),
      headers: { token: localStorage.getItem('adminToken') || '' },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `用户列表${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } finally { exporting.value = false }
}

// ---- 详情 ----
async function openDetail(row) { openDetailById(row.id) }

async function openDetailById(userId) {
  detailUserId = userId
  detail.value = null
  drawerVisible.value = true
  detailLoading.value = true
  logPage.value = 1
  try {
    detail.value = await request.get(`/admin/user/${userId}`)
    await fetchLogs()
  } finally { detailLoading.value = false }
}

async function fetchLogs() {
  logsLoading.value = true
  try {
    const res = await request.get(`/admin/user/${detailUserId}/loginLogs`, {
      params: { page: logPage.value, pageSize: 10 },
    })
    logs.value = res.records || []
    logTotal.value = res.total || 0
  } finally { logsLoading.value = false }
}

// ---- 封禁 / 解封 ----
async function toggleStatus(row) {
  if (row.status === 1) return ban(row.id, row.username)
  try {
    await ElMessageBox.confirm(`确认解封用户「${row.username}」?`, '解封确认', { type: 'warning' })
  } catch { return }
  await request.post(`/admin/user/status/1`, null, { params: { id: row.id } })
  ElMessage.success('已解封')
  fetchPage()
  if (activeTab.value === 'risk') fetchRisk()
}

function ban(userId, username) {
  banTarget.value = { id: userId, username }
  banReason.value = ''
  banVisible.value = true
}

async function confirmBan() {
  if (!banReason.value.trim()) return ElMessage.warning('请填写封禁原因')
  submitting.value = true
  try {
    await request.post(`/admin/user/status/0`, null,
      { params: { id: banTarget.value.id, reason: banReason.value.trim() } })
    ElMessage.success('已封禁,该用户已下线')
    banVisible.value = false
    fetchPage()
    if (activeTab.value === 'risk') fetchRisk()
  } finally { submitting.value = false }
}

// ---- 批量发券 ----
async function openGrant() {
  grantCouponId.value = null
  const res = await request.get('/admin/coupon/page', { params: { status: 1, page: 1, pageSize: 100 } })
  couponOptions.value = (res.records || []).filter(c => c.stock > 0)
  if (!couponOptions.value.length) return ElMessage.warning('没有可发放的优惠券(需启用且有余量)')
  grantVisible.value = true
}

async function confirmGrant() {
  if (!grantCouponId.value) return ElMessage.warning('请选择优惠券')
  submitting.value = true
  try {
    const res = await request.post('/admin/user/grantCoupon', {
      couponId: grantCouponId.value,
      userIds: selected.value.map(u => u.id),
    })
    ElMessage.success(`发放成功 ${res.granted} 张,跳过 ${res.skipped} 人,剩余 ${res.stockLeft} 张`)
    grantVisible.value = false
    fetchPage()
  } finally { submitting.value = false }
}

onMounted(fetchPage)
</script>

<style scoped>
.stat-box {
  flex: 1;
  background: #f5f7fa;
  border-radius: 6px;
  padding: 14px 0;
  text-align: center;
}
.stat-num { font-size: 20px; font-weight: 600; color: #303133; }
.stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
</style>
