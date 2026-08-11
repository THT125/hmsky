<template>
  <div>
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between">
          <el-input v-model="searchName" placeholder="搜索姓名" clearable style="width:200px" @keyup.enter="fetchPage" />
          <el-button type="primary" @click="openDialog()">新增员工</el-button>
        </div>
      </template>
      <el-table :data="tableData" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="phone" label="手机号" />
        <el-table-column prop="sex" label="性别" width="60">
          <template #default="{row}">{{ row.sex === '1' ? '男' : '女' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{row}"><el-tag :type="row.status===1?'success':'danger'">{{ row.status===1?'启用':'禁用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="320">
          <template #default="{row}">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" :type="row.status===1?'danger':'success'" :disabled="row.id===myId || row.username==='admin'" @click="toggleStatus(row)">{{ row.status===1?'禁用':'启用' }}</el-button>
            <el-button size="small" @click="openPwdDialog(row)">改密</el-button>
            <el-button size="small" type="danger" :disabled="row.id===myId || row.username==='admin'" @click="removeEmp(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top:16px;justify-content:flex-end"
        v-model:current-page="page" v-model:page-size="pageSize"
        :total="total" layout="total,prev,pager,next" @change="fetchPage"
      />
    </el-card>

    <!-- 新增/编辑 Dialog -->
    <el-dialog :title="isEdit?'编辑员工':'新增员工'" v-model="dialogVisible" width="500px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="姓名" prop="name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" :disabled="isEdit" /></el-form-item>
        <el-form-item v-if="!isEdit" label="初始密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少8位,需同时包含字母和数字" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="性别"><el-radio-group v-model="form.sex"><el-radio value="1">男</el-radio><el-radio value="0">女</el-radio></el-radio-group></el-form-item>
        <el-form-item label="身份证号" prop="idNumber"><el-input v-model="form.idNumber" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="submit" :loading="submitting">确定</el-button></template>
    </el-dialog>

    <!-- 改密 Dialog -->
    <el-dialog title="修改密码" v-model="pwdVisible" width="400px">
      <el-form :model="pwdForm" :rules="pwdRules" ref="pwdRef" label-width="100px">
        <el-form-item label="旧密码" prop="oldPassword"><el-input v-model="pwdForm.oldPassword" type="password" show-password /></el-form-item>
        <el-form-item label="新密码" prop="newPassword"><el-input v-model="pwdForm.newPassword" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer><el-button @click="pwdVisible=false">取消</el-button><el-button type="primary" @click="changePwd" :loading="submitting">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const router = useRouter()
const myId = Number(localStorage.getItem('adminId') || 0)
const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const searchName = ref('')
const dialogVisible = ref(false)
const pwdVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const pwdRef = ref(null)
const form = reactive({ id: null, name: '', username: '', password: '', phone: '', sex: '1', idNumber: '' })
const pwdForm = reactive({ empId: null, oldPassword: '', newPassword: '' })
const rules = {
  name: [{ required: true, message: '必填', trigger: 'blur' }],
  username: [{ required: true, message: '必填', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入初始密码', trigger: 'blur' },
    { pattern: /^(?=.*[a-zA-Z])(?=.*\d).{8,}$/, message: '至少8位,需同时包含字母和数字', trigger: 'blur' },
  ],
  phone: [
    { required: true, message: '必填', trigger: 'blur' },
    { pattern: /^1\d{10}$/, message: '手机号格式不正确(11位数字)', trigger: 'blur' },
  ],
  idNumber: [{ required: true, message: '必填', trigger: 'blur' }],
}
const pwdRules = {
  oldPassword: [{ required: true, message: '必填', trigger: 'blur' }],
  newPassword: [{ required: true, message: '必填', trigger: 'blur' }],
}

async function fetchPage() {
  loading.value = true
  const res = await request.get('/admin/employee/page', { params: { name: searchName.value, page: page.value, pageSize: pageSize.value } })
  tableData.value = res.records || []
  total.value = res.total || 0
  loading.value = false
}

function openDialog(row) {
  isEdit.value = !!row
  if (row) Object.assign(form, { id: row.id, name: row.name, username: row.username, password: '', phone: row.phone, sex: row.sex, idNumber: row.idNumber })
  dialogVisible.value = true
}

function resetForm() {
  Object.assign(form, { id: null, name: '', username: '', password: '', phone: '', sex: '1', idNumber: '' })
}

async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) {
      await request.put('/admin/employee', form)
    } else {
      await request.post('/admin/employee', form)
    }
    ElMessage.success('操作成功')
    dialogVisible.value = false
    fetchPage()
  } finally { submitting.value = false }
}

async function toggleStatus(row) {
  const newStatus = row.status === 1 ? 0 : 1
  await request.post(`/admin/employee/status/${newStatus}`, null, { params: { id: row.id } })
  row.status = newStatus
  ElMessage.success('操作成功')
}

function openPwdDialog(row) {
  Object.assign(pwdForm, { empId: row.id, oldPassword: '', newPassword: '' })
  pwdVisible.value = true
}

async function removeEmp(row) {
  try {
    await ElMessageBox.confirm(`确定删除员工「${row.name}」吗?删除后不可恢复!`, '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }
  await request.delete(`/admin/employee/${row.id}`)
  ElMessage.success('删除成功')
  fetchPage()
}

async function changePwd() {
  const valid = await pwdRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const res = await request.put('/admin/employee/editPassword', pwdForm)
    ElMessage.success('密码修改成功')
    pwdVisible.value = false
    if (res.selfChanged) {
      // 改的是自己:本会话已被吊销,需重新登录
      localStorage.removeItem('adminToken')
      localStorage.removeItem('adminName')
      ElMessage.warning('密码已修改,请使用新密码重新登录')
      setTimeout(() => router.replace('/login'), 600)
    }
  } finally { submitting.value = false }
}

onMounted(fetchPage)
</script>
