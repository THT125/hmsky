<template>
  <div>
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px">
          <div style="display:flex;gap:12px;flex-wrap:wrap">
            <el-input v-model="searchName" placeholder="搜索套餐" clearable style="width:180px" @keyup.enter="fetchPage" />
            <el-select v-model="searchCategory" placeholder="分类" clearable style="width:150px" @change="fetchPage">
              <el-option v-for="c in categoryList" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-select v-model="searchStatus" placeholder="状态" clearable style="width:100px" @change="fetchPage">
              <el-option label="起售" :value="1" /><el-option label="停售" :value="0" />
            </el-select>
          </div>
          <el-button type="primary" @click="openDialog()">新增套餐</el-button>
        </div>
      </template>
      <el-table :data="tableData" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="categoryName" label="分类" width="100" />
        <el-table-column prop="price" label="价格" width="80"><template #default="{row}">¥{{ row.price }}</template></el-table-column>
        <el-table-column label="菜品组成" min-width="200">
          <template #default="{row}">{{ (row.setmealDishes||[]).map(d=>d.name+'×'+d.copies).join('、') }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="70">
          <template #default="{row}"><el-tag :type="row.status===1?'success':'danger'">{{ row.status===1?'起售':'停售' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="stock" label="库存" width="90">
          <template #default="{row}">
            <span v-if="row.stock === null || row.stock === undefined">不限量</span>
            <el-tag v-else-if="row.stock === 0" type="danger">已售罄</el-tag>
            <span v-else>{{ row.stock }} 份</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{row}">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" :type="row.status===1?'danger':'success'" @click="toggleStatus(row)">{{ row.status===1?'停售':'起售' }}</el-button>
            <el-button size="small" type="danger" @click="delSetmeal(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:16px;justify-content:flex-end" v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total,prev,pager,next" @change="fetchPage" />
    </el-card>

    <el-dialog :title="isEdit?'编辑套餐':'新增套餐'" v-model="dialogVisible" width="640px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="分类" prop="categoryId">
          <el-select v-model="form.categoryId" style="width:100%">
            <el-option v-for="c in categoryList.filter(x=>x.type===2)" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="价格" prop="price"><el-input-number v-model="form.price" :precision="2" :min="0" /></el-form-item>
        <el-form-item label="库存(份)">
          <el-input-number v-model="form.stock" :min="0" :controls="false" placeholder="留空为不限量" style="width:200px" />
          <span style="color:#999;font-size:12px;margin-left:8px">留空 = 不限量;售罄后用户端不可下单</span>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
        <el-form-item label="图片">
          <el-input v-model="form.image" placeholder="图片URL" />
          <el-upload :action="uploadUrl" :headers="uploadHeaders" :show-file-list="false" :on-success="(res)=>form.image=res&&res.data" accept="image/*" style="display:inline-block;margin-left:8px">
            <el-button>上传</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="套餐菜品">
          <div v-for="(d, i) in form.setmealDishes" :key="i" style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
            <el-select v-model="d.dishId" placeholder="菜品" filterable style="flex:1" @change="onDishSelected(d)">
              <el-option v-for="dish in allDishes" :key="dish.id" :label="dish.name+' ¥'+dish.price" :value="dish.id" />
            </el-select>
            <span>份数:</span>
            <el-input-number v-model="d.copies" :min="1" size="small" style="width:70px" />
            <el-button size="small" @click="form.setmealDishes.splice(i,1)">删除</el-button>
          </div>
          <el-button size="small" @click="form.setmealDishes.push({dishId:null,name:'',price:0,copies:1})">+ 添加菜品</el-button>
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
const categoryList = ref([]), allDishes = ref([])
const dialogVisible = ref(false), isEdit = ref(false), submitting = ref(false)
const formRef = ref(null)
const form = reactive({ id: null, name: '', categoryId: null, price: 0, image: '', description: '', stock: null, setmealDishes: [] })
const rules = { name: [{ required: true }], categoryId: [{ required: true }], price: [{ required: true }] }
const uploadUrl = '/admin/common/upload'
const uploadHeaders = { token: localStorage.getItem('adminToken') || '' }

function onDishSelected(item) {
  const d = allDishes.value.find(x => x.id === item.dishId)
  if (d) { item.name = d.name; item.price = Number(d.price) }
}

async function fetchCategories() { categoryList.value = await request.get('/admin/category/list') || [] }
async function fetchDishes() { const res = await request.get('/admin/dish/list') || []; allDishes.value = res }

async function fetchPage() {
  loading.value = true
  const res = await request.get('/admin/setmeal/page', { params: { name: searchName.value, categoryId: searchCategory.value, status: searchStatus.value, page: page.value, pageSize: pageSize.value } })
  tableData.value = res.records || []; total.value = res.total || 0; loading.value = false
}

function openDialog(row) {
  isEdit.value = !!row
  if (row) Object.assign(form, { id: row.id, name: row.name, categoryId: row.categoryId, price: Number(row.price), image: row.image || '', description: row.description || '', stock: row.stock ?? null, setmealDishes: (row.setmealDishes||[]).map(d=>({dishId:d.dishId,name:d.name,price:Number(d.price||0),copies:d.copies})) })
  uploadHeaders.token = localStorage.getItem('adminToken') || ''
  dialogVisible.value = true
}

function resetForm() { Object.assign(form, { id: null, name: '', categoryId: null, price: 0, image: '', description: '', stock: null, setmealDishes: [] }) }

async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) await request.put('/admin/setmeal', form)
    else await request.post('/admin/setmeal', form)
    ElMessage.success('操作成功'); dialogVisible.value = false; fetchPage()
  } finally { submitting.value = false }
}

async function toggleStatus(row) {
  const s = row.status === 1 ? 0 : 1
  await request.post(`/admin/setmeal/status/${s}`, null, { params: { id: row.id } })
  row.status = s; ElMessage.success('操作成功')
}

async function delSetmeal(row) {
  await ElMessageBox.confirm('确认删除?', '提示', { type: 'warning' })
  await request.delete('/admin/setmeal', { params: { ids: String(row.id) } })
  ElMessage.success('删除成功'); fetchPage()
}

onMounted(() => { fetchCategories(); fetchDishes(); fetchPage() })
</script>
