<template>
  <div>
    <el-card>
      <template #header><span>订单搜索</span></template>
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px">
        <el-input v-model="search.number" placeholder="订单号" clearable style="width:200px" />
        <el-input v-model="search.phone" placeholder="手机号" clearable style="width:150px" />
        <el-select v-model="search.status" placeholder="状态" clearable style="width:120px">
          <el-option label="待付款" :value="1" /><el-option label="待接单" :value="2" />
          <el-option label="已接单" :value="3" /><el-option label="派送中" :value="4" />
          <el-option label="已完成" :value="5" /><el-option label="已取消" :value="6" />
        </el-select>
        <el-date-picker v-model="search.beginTime" type="datetime" placeholder="开始时间" value-format="YYYY-MM-DDTHH:mm:ss" style="width:180px" />
        <el-date-picker v-model="search.endTime" type="datetime" placeholder="结束时间" value-format="YYYY-MM-DDTHH:mm:ss" style="width:180px" />
        <el-button type="primary" @click="fetchPage">查询</el-button>
      </div>
      <el-tabs v-model="activeTab" @tab-change="tabChange">
        <el-tab-pane label="全部" name="" />
        <el-tab-pane label="待付款" name="1" />
        <el-tab-pane label="待接单" name="2" />
        <el-tab-pane label="已接单" name="3" />
        <el-tab-pane label="派送中" name="4" />
        <el-tab-pane label="已完成" name="5" />
        <el-tab-pane label="已取消" name="6" />
      </el-tabs>
      <el-table :data="tableData" stripe v-loading="loading">
        <el-table-column prop="number" label="订单号" width="200" />
        <el-table-column prop="consignee" label="收货人" width="80" />
        <el-table-column prop="phone" label="电话" width="120" />
        <el-table-column prop="amount" label="金额" width="80"><template #default="{row}">¥{{ row.amount }}</template></el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{row}"><el-tag :type="statusType(row.status)">{{ statusText[row.status] }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="orderTime" label="下单时间" width="180" />
        <el-table-column label="菜品" min-width="180">
          <template #default="{row}">{{ row.orderDishes }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280">
          <template #default="{row}">
            <el-button size="small" @click="showDetail(row)">详情</el-button>
            <el-button v-if="row.status===2" size="small" type="success" @click="confirm(row)">接单</el-button>
            <el-button v-if="row.status===2" size="small" type="warning" @click="openReject(row)">拒单</el-button>
            <el-button v-if="row.status===3" size="small" type="primary" @click="delivery(row)">派送</el-button>
            <el-button v-if="row.status===4" size="small" type="success" @click="complete(row)">完成</el-button>
            <el-button v-if="[1,2,3,4,5].includes(row.status)" size="small" type="danger" @click="cancelOrder(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total,prev,pager,next" @change="fetchPage" />
    </el-card>

    <!-- 订单详情 Drawer -->
    <el-drawer v-model="drawerVisible" title="订单详情" size="500px">
      <div v-if="detail" style="padding:0 20px">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="订单号">{{ detail.number }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusText[detail.status] }}</el-descriptions-item>
          <el-descriptions-item label="收货人">{{ detail.consignee }}</el-descriptions-item>
          <el-descriptions-item label="电话">{{ detail.phone }}</el-descriptions-item>
          <el-descriptions-item label="金额">¥{{ detail.amount }}</el-descriptions-item>
          <el-descriptions-item label="支付状态">{{ ['未支付','已支付','退款'][detail.payStatus] }}</el-descriptions-item>
          <el-descriptions-item label="地址" :span="2">{{ detail.address }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ detail.remark }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.cancelReason" label="取消原因" :span="2">{{ detail.cancelReason }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.rejectionReason" label="拒单原因" :span="2">{{ detail.rejectionReason }}</el-descriptions-item>
        </el-descriptions>
        <h4 style="margin-top:16px">商品明细</h4>
        <el-table :data="detail.orderDetailList||[]" size="small">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="number" label="数量" width="60" />
          <el-table-column prop="amount" label="单价" width="80"><template #default="{row}">¥{{ row.amount }}</template></el-table-column>
        </el-table>
      </div>
    </el-drawer>

    <!-- 取消 Dialog -->
    <el-dialog title="取消订单" v-model="cancelVisible" width="400px">
      <el-input v-model="cancelReason" placeholder="请输入取消原因" type="textarea" />
      <template #footer><el-button @click="cancelVisible=false">返回</el-button><el-button type="danger" @click="doCancel">确认取消</el-button></template>
    </el-dialog>

    <!-- 拒单 Dialog -->
    <el-dialog title="拒单" v-model="rejectVisible" width="400px">
      <el-input v-model="rejectReason" placeholder="请输入拒单原因" type="textarea" />
      <template #footer><el-button @click="rejectVisible=false">返回</el-button><el-button type="warning" @click="doReject">确认拒单</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const statusText = { 1: '待付款', 2: '待接单', 3: '已接单', 4: '派送中', 5: '已完成', 6: '已取消' }
function statusType(s) { return [1,2].includes(s)?'warning':s===3?'primary':s===4?'info':s===5?'success':'danger' }

const tableData = ref([]), loading = ref(false), page = ref(1), pageSize = ref(10), total = ref(0)
const activeTab = ref('')
const search = reactive({ number: '', phone: '', status: null, beginTime: '', endTime: '' })
const drawerVisible = ref(false), detail = ref(null)
const cancelVisible = ref(false), cancelId = ref(null), cancelReason = ref('')
const rejectVisible = ref(false), rejectId = ref(null), rejectReason = ref('')

function tabChange(name) { search.status = name ? Number(name) : null; fetchPage() }

async function fetchPage() {
  loading.value = true
  const res = await request.get('/admin/order/conditionSearch', { params: { page: page.value, pageSize: pageSize.value, ...search } })
  tableData.value = res.records || []; total.value = res.total || 0; loading.value = false
}

async function showDetail(row) {
  detail.value = await request.get(`/admin/order/details/${row.id}`)
  drawerVisible.value = true
}

async function confirm(row) { await request.put('/admin/order/confirm', { id: row.id }); ElMessage.success('已接单'); row.status = 3 }
async function delivery(row) { await request.put(`/admin/order/delivery/${row.id}`); ElMessage.success('已派送'); row.status = 4 }
async function complete(row) { await request.put(`/admin/order/complete/${row.id}`); ElMessage.success('已完成'); row.status = 5 }

function cancelOrder(row) {
  cancelId.value = row.id; cancelReason.value = ''; cancelVisible.value = true
}
async function doCancel() {
  await request.put('/admin/order/cancel', { id: cancelId.value, cancelReason: cancelReason.value })
  ElMessage.success('已取消'); cancelVisible.value = false; fetchPage()
}

function openReject(row) {
  rejectId.value = row.id; rejectReason.value = ''; rejectVisible.value = true
}
async function doReject() {
  await request.put('/admin/order/rejection', { id: rejectId.value, rejectionReason: rejectReason.value })
  ElMessage.success('已拒单'); rejectVisible.value = false; fetchPage()
}

// 收到 WebSocket 新订单推送时自动刷新列表(无需手动刷新)
// 30s 轮询:覆盖定时任务(超时自动取消/凌晨自动完成)导致的订单变化
let pollTimer = null
onMounted(() => {
  fetchPage()
  window.addEventListener('order-push', fetchPage)
  pollTimer = setInterval(fetchPage, 30000)
})
onBeforeUnmount(() => {
  window.removeEventListener('order-push', fetchPage)
  clearInterval(pollTimer)
})
</script>
