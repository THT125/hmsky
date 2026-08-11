<template>
  <div>
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px">
          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <el-input v-model="searchName" placeholder="搜索菜品" clearable style="width:180px" @keyup.enter="fetchPage" />
            <el-select v-model="searchCategory" placeholder="分类" clearable style="width:150px" @change="fetchPage">
              <el-option v-for="c in categoryList" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-select v-model="searchStatus" placeholder="状态" clearable style="width:100px" @change="fetchPage">
              <el-option label="起售" :value="1" /><el-option label="停售" :value="0" />
            </el-select>
          </div>
          <el-button type="primary" @click="openDialog()">新增菜品</el-button>
        </div>
      </template>
      <el-table :data="tableData" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="categoryName" label="分类" width="100" />
        <el-table-column prop="price" label="价格" width="80">
          <template #default="{row}">¥{{ row.price }}</template>
        </el-table-column>
        <el-table-column prop="image" label="图片" width="80">
          <template #default="{row}"><el-avatar :src="row.image" shape="square" size="small" /></template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="70">
          <template #default="{row}"><el-tag :type="row.status===1?'success':'danger'">{{ row.status===1?'起售':'停售' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{row}">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" :type="row.status===1?'danger':'success'" @click="toggleStatus(row)">{{ row.status===1?'停售':'起售' }}</el-button>
            <el-button size="small" type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total,prev,pager,next" @change="fetchPage" />
    </el-card>

    <!-- 新增/编辑 Dialog -->
    <el-dialog :title="isEdit?'编辑菜品':'新增菜品'" v-model="dialogVisible" width="600px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="分类" prop="categoryId">
          <el-select v-model="form.categoryId" style="width:100%">
            <el-option v-for="c in categoryList.filter(x=>x.type===1)" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="价格" prop="price"><el-input-number v-model="form.price" :precision="2" :min="0" /></el-form-item>
        <el-form-item label="图片">
          <div style="display:flex;gap:8px;align-items:center">
            <el-input v-model="form.image" placeholder="图片URL" />
            <el-upload :action="uploadUrl" :headers="uploadHeaders" :show-file-list="false" :on-success="onUploadSuccess" accept="image/*">
              <el-button>上传</el-button>
            </el-upload>
          </div>
          <el-image v-if="form.image" :src="form.image" style="width:80px;height:80px;margin-top:8px" fit="cover" />
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
        <el-form-item label="口味">
          <div v-for="(f, i) in form.flavors" :key="i" style="display:flex;gap:8px;margin-bottom:8px">
            <el-input v-model="f.name" placeholder="口味名(如:辣度)" style="width:140px" />
            <el-input v-model="f.value" placeholder='值(如:不辣,微辣 的JSON数组)' style="flex:1" />
            <el-button size="small" @click="form.flavors.splice(i,1)">删除</el-button>
          </div>
          <el-button size="small" @click="form.flavors.push({name:'',value:''})">+ 添加口味</el-button>
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
const searchName = ref(''), searchCategory = ref(null), searchStatus = ref(null)
const dialogVisible = ref(false), isEdit = ref(false), submitting = ref(false)
const formRef = ref(null)
const categoryList = ref([])
const form = reactive({ id: null, name: '', categoryId: null, price: 0, image: '', description: '', status: 1, flavors: [] })
const rules = {
  name: [{ required: true, message: '必填', trigger: 'blur' }],
  categoryId: [{ required: true, message: '必填', trigger: 'change' }],
  price: [{ required: true, message: '必填', trigger: 'blur' }],
}
const uploadUrl = '/admin/common/upload'
const uploadHeaders = { token: localStorage.getItem('adminToken') || '' }

function onUploadSuccess(res) {
  // el-upload 不走 axios 拦截器,res 是完整响应 {code, msg, data},取 data 为图片路径
  form.image = res && res.data
}

async function fetchCategories() {
  const list = await request.get('/admin/category/list')
  categoryList.value = list || []
}

async function fetchPage() {
  loading.value = true
  const res = await request.get('/admin/dish/page', { params: { name: searchName.value, categoryId: searchCategory.value, status: searchStatus.value, page: page.value, pageSize: pageSize.value } })
  tableData.value = res.records || []
  total.value = res.total || 0
  loading.value = false
}

function openDialog(row) {
  isEdit.value = !!row
  if (row) {
    Object.assign(form, {
      id: row.id, name: row.name, categoryId: row.categoryId, price: Number(row.price),
      image: row.image || '', description: row.description || '', status: row.status,
      flavors: (row.flavors || []).map(f => ({ name: f.name, value: f.value })),
    })
  }
  uploadHeaders.token = localStorage.getItem('adminToken') || ''
  dialogVisible.value = true
}

function resetForm() { Object.assign(form, { id: null, name: '', categoryId: null, price: 0, image: '', description: '', status: 1, flavors: [] }) }

async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) await request.put('/admin/dish', form)
    else await request.post('/admin/dish', form)
    ElMessage.success('操作成功'); dialogVisible.value = false; fetchPage()
  } finally { submitting.value = false }
}

async function toggleStatus(row) {
  const s = row.status === 1 ? 0 : 1
  await request.post(`/admin/dish/status/${s}`, null, { params: { id: row.id } })
  row.status = s; ElMessage.success('操作成功')
}

async function del(row) {
  await ElMessageBox.confirm('确认删除?', '提示', { type: 'warning' })
  await request.delete('/admin/dish', { params: { ids: String(row.id) } })
  ElMessage.success('删除成功'); fetchPage()
}

onMounted(() => { fetchCategories(); fetchPage() })
</script>
