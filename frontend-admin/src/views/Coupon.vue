<template>
  <div>
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px">
          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <el-input v-model="searchName" placeholder="搜索券名称" clearable style="width:180px" @keyup.enter="fetchPage" />
            <el-select v-model="searchStatus" placeholder="状态" clearable style="width:100px" @change="fetchPage">
              <el-option label="启用" :value="1" /><el-option label="停用" :value="0" />
            </el-select>
          </div>
          <el-button type="primary" @click="openDialog()">新增优惠券</el-button>
        </div>
      </template>
      <el-table :data="tableData" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" width="140" />
        <el-table-column prop="type" label="类型" width="70">
          <template #default="{row}">{{ row.type===1?'满减':'折扣' }}</template>
        </el-table-column>
        <el-table-column label="面值" width="100">
          <template #default="{row}">{{ row.type===1 ? '¥'+row.amount : row.amount+'折' }}</template>
        </el-table-column>
        <el-table-column label="门槛" width="90">
          <template #default="{row}">{{ Number(row.minAmount)>0 ? '满¥'+row.minAmount : '无门槛' }}</template>
        </el-table-column>
        <el-table-column prop="total" label="总量" width="70" />
        <el-table-column prop="stock" label="剩余" width="70">
          <template #default="{row}">
            <el-tag v-if="row.stock===0" type="danger" size="small">抢完</el-tag>
            <span v-else>{{ row.stock }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="perUserLimit" label="限领" width="70" />
        <el-table-column label="有效期" width="90">
          <template #default="{row}">领取后 {{ row.validDays }} 天</template>
        </el-table-column>
        <el-table-column label="可领时间" min-width="180">
          <template #default="{row}">{{ fmt(row.startTime) }} ~ {{ fmt(row.endTime) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="70">
          <template #default="{row}"><el-tag :type="row.status===1?'success':'danger'">{{ row.status===1?'启用':'停用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{row}">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" :type="row.status===1?'danger':'success'" @click="toggleStatus(row)">{{ row.status===1?'停用':'启用' }}</el-button>
            <el-button size="small" type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total,prev,pager,next" @change="fetchPage" />
    </el-card>

    <!-- 新增/编辑 Dialog -->
    <el-dialog :title="isEdit?'编辑优惠券':'新增优惠券'" v-model="dialogVisible" width="520px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="券名称" prop="name"><el-input v-model="form.name" maxlength="50" /></el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio :value="1">满减</el-radio>
            <el-radio :value="2">折扣</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="面值" prop="amount">
          <el-input-number v-model="form.amount" :precision="2" :min="0.01" :max="9999" />
          <span style="color:#999;font-size:12px;margin-left:8px">{{ form.type===1 ? '减免金额(元)' : '折扣率,如 8.5 = 85折' }}</span>
        </el-form-item>
        <el-form-item label="使用门槛"><el-input-number v-model="form.minAmount" :precision="2" :min="0" :max="99999" /><span style="color:#999;font-size:12px;margin-left:8px">满X元可用,0=无门槛</span></el-form-item>
        <el-form-item label="发放总量" prop="total"><el-input-number v-model="form.total" :min="1" :max="999999" /></el-form-item>
        <el-form-item label="每人限领"><el-input-number v-model="form.perUserLimit" :min="1" :max="99" /></el-form-item>
        <el-form-item label="有效天数">
          <el-input-number v-model="form.validDays" :min="1" :max="365" />
          <span style="color:#999;font-size:12px;margin-left:8px">领取后 N 天内有效,过期自动失效</span>
        </el-form-item>
        <el-form-item v-if="isEdit" label="剩余量(补货)">
          <el-input-number v-model="form.stock" :min="0" :max="999999" />
          <span style="color:#999;font-size:12px;margin-left:8px">不填保持原剩余</span>
        </el-form-item>
        <el-form-item label="可领时间" prop="startTime">
          <el-date-picker v-model="form.startTime" type="datetime" placeholder="开始时间" value-format="YYYY-MM-DD HH:mm:ss" style="width:220px" />
          <span style="margin:0 6px">~</span>
          <el-date-picker v-model="form.endTime" type="datetime" placeholder="结束时间" value-format="YYYY-MM-DD HH:mm:ss" style="width:220px" />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="submit" :loading="submitting">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const tableData = ref([]), loading = ref(false), page = ref(1), pageSize = ref(10), total = ref(0)
const searchName = ref(''), searchStatus = ref(null)
const dialogVisible = ref(false), isEdit = ref(false), submitting = ref(false)
const formRef = ref(null)
const form = reactive({ id: null, name: '', type: 1, amount: 0, minAmount: 0, total: 100, stock: null, perUserLimit: 1, validDays: 7, startTime: '', endTime: '' })
const rules = {
  name: [{ required: true, message: '必填', trigger: 'blur' }],
  amount: [{ required: true, message: '必填', trigger: 'blur' }],
  total: [{ required: true, message: '必填', trigger: 'blur' }],
}

function fmt(t) { return t ? String(t).slice(0, 16) : '' }

async function fetchPage() {
  loading.value = true
  const res = await request.get('/admin/coupon/page', { params: { name: searchName.value, status: searchStatus.value, page: page.value, pageSize: pageSize.value } })
  tableData.value = res.records || []
  total.value = res.total || 0
  loading.value = false
}

function openDialog(row) {
  isEdit.value = !!row
  if (row) Object.assign(form, {
    id: row.id, name: row.name, type: row.type, amount: Number(row.amount),
    minAmount: Number(row.minAmount || 0), total: row.total, stock: null,
    perUserLimit: row.perUserLimit, validDays: row.validDays || 7,
    startTime: fmt(row.startTime) + ':00', endTime: fmt(row.endTime) + ':00',
  })
  dialogVisible.value = true
}

function resetForm() {
  Object.assign(form, { id: null, name: '', type: 1, amount: 0, minAmount: 0, total: 100, stock: null, perUserLimit: 1, validDays: 7, startTime: '', endTime: '' })
}

async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) await request.put('/admin/coupon', form)
    else await request.post('/admin/coupon', form)
    ElMessage.success('操作成功'); dialogVisible.value = false; fetchPage()
  } finally { submitting.value = false }
}

async function toggleStatus(row) {
  const s = row.status === 1 ? 0 : 1
  await request.post(`/admin/coupon/status/${s}`, null, { params: { id: row.id } })
  row.status = s; ElMessage.success('操作成功')
}

async function del(row) {
  await ElMessageBox.confirm('确认删除?已有用户领取的券无法删除', '提示', { type: 'warning' })
  await request.delete('/admin/coupon', { params: { ids: String(row.id) } })
  ElMessage.success('删除成功'); fetchPage()
}

onMounted(fetchPage)
</script>
