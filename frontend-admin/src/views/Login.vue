<template>
  <div style="display:flex;justify-content:center;align-items:center;height:100vh;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%)">
    <el-card style="width:400px;padding:20px">
      <h2 style="text-align:center;margin-bottom:30px">苍穹外卖管理端</h2>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="0">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" size="large" show-password @keyup.enter="login" />
        </el-form-item>
        <el-form-item prop="captchaCode">
          <div style="display:flex;gap:10px;width:100%">
            <el-input v-model="form.captchaCode" placeholder="验证码" prefix-icon="Key" size="large" maxlength="4" @keyup.enter="login" />
            <img :src="captchaImage" alt="验证码" title="点击刷新" @click="fetchCaptcha"
                 style="width:120px;height:40px;border-radius:4px;cursor:pointer;flex-shrink:0" />
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="login">登录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const router = useRouter()
const loading = ref(false)
const formRef = ref(null)
const captchaImage = ref('')
const captchaUuid = ref('')
const form = reactive({ username: 'admin', password: '123456', captchaCode: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  captchaCode: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
}

// 获取验证码(CAPTCHA_ENABLED=0 时响应带 code 明文,测试模式自动填充)
async function fetchCaptcha() {
  try {
    const data = await request.get('/admin/captcha')
    captchaUuid.value = data.uuid
    captchaImage.value = 'data:image/png;base64,' + data.image
    if (data.code) form.captchaCode = data.code
  } catch {}
}

async function login() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const data = await request.post('/admin/employee/login', {
      ...form,
      captchaUuid: captchaUuid.value,
    })
    localStorage.setItem('adminToken', data.token)
    localStorage.setItem('adminName', data.name || data.userName)
    localStorage.setItem('adminId', data.id)
    if (data.forceChangePassword) {
      // 首次登录(默认密码):强制改密
      ElMessageBox.confirm('检测到您正在使用初始密码登录，为保证账号安全，请立即修改密码。', '安全提醒', {
        confirmButtonText: '去修改密码',
        cancelButtonText: '稍后再说',
        type: 'warning',
      }).then(() => router.push('/employee')).catch(() => router.push('/'))
    } else {
      router.push('/')
    }
  } catch {
    // 错误已在拦截器中提示;刷新验证码
    form.captchaCode = ''
    fetchCaptcha()
  } finally {
    loading.value = false
  }
}

onMounted(fetchCaptcha)
</script>
