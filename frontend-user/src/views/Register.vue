<template>
  <div style="min-height:100vh;background:#f7f8fa;padding:60px 24px">
    <div style="text-align:center;margin-bottom:40px">
      <van-icon name="shop-o" size="56" color="#ee0a24" />
      <h2 style="margin:12px 0 4px">你饿了吗</h2>
      <div style="color:#999;font-size:13px">注册新账号</div>
    </div>
    <van-form @submit="register">
      <van-cell-group inset>
        <van-field v-model="form.username" name="username" label="用户名" placeholder="请输入用户名"
                   :rules="[{ required: true, message: '请输入用户名' }]" />
        <van-field v-model="form.phone" name="phone" label="手机号" type="tel" maxlength="11" placeholder="请输入手机号"
                   :rules="[{ required: true, message: '请输入手机号' }, { pattern: /^1\d{10}$/, message: '手机号格式不正确' }]" />
        <van-field v-model="form.password" type="password" name="password" label="密码" placeholder="至少8位，含字母和数字"
                   :rules="[{ required: true, message: '请输入密码' }]" />
        <van-field v-model="form.confirmPassword" type="password" name="confirmPassword" label="确认密码"
                   placeholder="请再次输入密码"
                   :rules="[{ required: true, message: '请再次输入密码' }, { validator: (v) => v === form.password, message: '两次密码不一致' }]" />
        <van-field v-model="form.captchaCode" name="captchaCode" label="验证码" placeholder="请输入验证码" maxlength="4"
                   :rules="[{ required: true, message: '请输入验证码' }]">
          <template #button>
            <img :src="captchaImage" alt="验证码" title="点击刷新" @click="fetchCaptcha"
                 style="width:100px;height:36px;border-radius:4px;cursor:pointer" />
          </template>
        </van-field>
      </van-cell-group>
      <div style="margin:24px 16px">
        <van-button round block type="danger" native-type="submit" :loading="loading">注 册</van-button>
        <div style="text-align:center;margin-top:16px;color:#1989fa;font-size:14px" @click="$router.push('/login')">
          已有账号？去登录
        </div>
      </div>
    </van-form>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '@/utils/request'
import { setAuth } from '@/utils/auth'

const router = useRouter()
const loading = ref(false)
const captchaImage = ref('')
const captchaUuid = ref('')
const form = reactive({ username: '', phone: '', password: '', confirmPassword: '', captchaCode: '' })

async function fetchCaptcha() {
  try {
    const data = await request.get('/user/captcha')
    captchaUuid.value = data.uuid
    captchaImage.value = 'data:image/png;base64,' + data.image
    if (data.code) form.captchaCode = data.code // 开发模式自动填充明文
  } catch {}
}

async function register() {
  loading.value = true
  try {
    const data = await request.post('/user/user/register', {
      username: form.username,
      phone: form.phone,
      password: form.password,
      captchaUuid: captchaUuid.value,
      captchaCode: form.captchaCode,
    })
    setAuth(data) // 注册成功自动登录
    showToast('注册成功，已自动登录')
    router.replace('/home')
  } catch {
    form.captchaCode = ''
    fetchCaptcha()
  } finally {
    loading.value = false
  }
}

onMounted(fetchCaptcha)
</script>
