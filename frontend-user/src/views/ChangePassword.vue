<template>
  <div style="min-height:100vh;background:#f7f8fa">
    <van-nav-bar title="修改密码" left-text="返回" @click-left="$router.back()" />
    <van-form @submit="save" style="margin-top:12px">
      <van-cell-group inset>
        <van-field v-model="form.oldPassword" label="旧密码" type="password" placeholder="请输入旧密码"
                   :rules="[{ required: true, message: '请输入旧密码' }]" />
        <van-field v-model="form.newPassword" label="新密码" type="password" placeholder="至少8位,需同时包含字母和数字"
                   :rules="[{ required: true, message: '请输入新密码' },
                            { pattern: /^(?=.*[a-zA-Z])(?=.*\d).{8,}$/, message: '至少8位,需同时包含字母和数字' }]" />
        <van-field v-model="form.confirm" label="确认密码" type="password" placeholder="再次输入新密码"
                   :rules="[{ required: true, message: '请再次输入新密码' },
                            { validator: (v) => v === form.newPassword, message: '两次密码不一致' }]" />
      </van-cell-group>
      <div style="margin:24px 16px">
        <van-button round block type="danger" native-type="submit" :loading="loading">确认修改</van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast } from 'vant'
import request from '@/utils/request'
import { logoutLocal } from '@/utils/auth'

const router = useRouter()
const loading = ref(false)
const form = reactive({ oldPassword: '', newPassword: '', confirm: '' })

async function save() {
  loading.value = true
  try {
    await request.put('/user/user/password', { oldPassword: form.oldPassword, newPassword: form.newPassword })
    logoutLocal() // 旧 token 已被吊销,清除本地登录态
    showSuccessToast('密码修改成功,请重新登录')
    setTimeout(() => router.replace('/login'), 600)
  } finally {
    loading.value = false
  }
}
</script>
