<template>
  <div>
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between">
          <div style="display:flex;gap:12px">
            <el-select v-model="filterType" placeholder="分类类型" clearable style="width:140px" @change="fetchPage">
              <el-option label="菜品分类" :value="1" /><el-option label="套餐分类" :value="2" />
            </el-select>
            <el-input v-model="searchName" placeholder="搜索名称" clearable style="width:200px" @keyup.enter="fetchPage" />
          </div>
          <el-button type="primary" @click="openDialog()">新增分类</el-button>
        </div>
      </template>
      <el-table :data="tableData" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{row}">{{ row.type===1?'菜品分类':'套餐分类' }}</template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="80" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{row}"><el-tag :type="row.status===1?'success':'danger'">{{ row.status===1?'启用':'禁用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{row}">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" :type="row.status===1?'danger':'success'" @click="toggleStatus(row)">{{ row.status===1?'禁用':'启用' }}</el-button>
            <el-button size="small" type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total,prev,pager,next" @change="fetchPage" />
    </el-card>

    <el-dialog :title="isEdit?'编辑分类':'新增分类'" v-model="dialogVisible" width="460px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="类型" prop="type"><el-select v-model="form.type" style="width:100%"><el-option label="菜品分类" :value="1" /><el-option label="套餐分类" :value="2" /></el-select></el-form-item>
        <el-form-item label="排序" prop="sort"><el-input-number v-model="form.sort" :min="0" /></el-form-item>
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
const searchName = ref(''), filterType = ref(null), dialogVisible = ref(false), isEdit = ref(false), submitting = ref(false)
const formRef = ref(null)
const form = reactive({ id: null, name: '', type: 1, sort: 0 })
const rules = { name: [{ required: true, message: '必填', trigger: 'blur' }] }

async function fetchPage() {
  loading.value = true
  const res = await request.get('/admin/category/page', { params: { name: searchName.value, type: filterType.value, page: page.value, pageSize: pageSize.value } })
  tableData.value = res.records || []
  total.value = res.total || 0
  loading.value = false
}

function openDialog(row) {
  isEdit.value = !!row
  if (row) Object.assign(form, { id: row.id, name: row.name, type: row.type, sort: row.sort })
  dialogVisible.value = true
}

function resetForm() { Object.assign(form, { id: null, name: '', type: 1, sort: 0 }) }

async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) await request.put('/admin/category', form)
    else await request.post('/admin/category', form)
    ElMessage.success('操作成功'); dialogVisible.value = false; fetchPage()
  } finally { submitting.value = false }
}

async function toggleStatus(row) {
  const s = row.status === 1 ? 0 : 1
  await request.post(`/admin/category/status/${s}`, null, { params: { id: row.id } })
  row.status = s; ElMessage.success('操作成功')
}

async function del(row) {
  await ElMessageBox.confirm('确认删除该分类?', '提示', { type: 'warning' })
  await request.delete('/admin/category', { params: { id: row.id } })
  ElMessage.success('删除成功'); fetchPage()
}

onMounted(fetchPage)
</script>
