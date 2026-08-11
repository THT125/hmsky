<template>
  <div style="min-height:100vh;background:#f7f8fa;padding-bottom:80px">
    <van-nav-bar title="编辑资料" left-text="返回" @click-left="$router.back()" />
    <!-- 头像 -->
    <div style="background:#fff;padding:20px 16px;display:flex;align-items:center;gap:16px">
      <van-uploader :after-read="onAvatarRead" max-count="1">
        <van-image v-if="form.avatar" :src="form.avatar" width="64" height="64" round fit="cover" />
        <div v-else style="width:64px;height:64px;border-radius:50%;background:#f2f3f5;display:flex;align-items:center;justify-content:center;color:#999;font-size:12px">
          上传头像
        </div>
      </van-uploader>
      <div>
        <div style="font-size:16px;font-weight:bold">{{ form.username }}</div>
        <div style="color:#999;font-size:13px;margin-top:4px">{{ form.phone }}</div>
      </div>
    </div>
    <van-form @submit="save" style="margin-top:12px">
      <van-cell-group inset>
        <van-field name="sex" label="性别">
          <template #input>
            <van-radio-group v-model="form.sex" direction="horizontal">
              <van-radio name="1">男</van-radio>
              <van-radio name="0">女</van-radio>
            </van-radio-group>
          </template>
        </van-field>
      </van-cell-group>
      <div style="margin:24px 16px">
        <van-button round block type="danger" native-type="submit" :loading="loading">保 存</van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { showToast } from 'vant'
import request from '@/utils/request'

const loading = ref(false)
const form = reactive({ username: '', phone: '', sex: '1', avatar: '' })

async function fetchProfile() {
  try {
    Object.assign(form, await request.get('/user/user/profile'))
    if (form.sex === null || form.sex === undefined) form.sex = '1'
  } catch {}
}

// 头像上传
async function onAvatarRead(file) {
  const fd = new FormData()
  fd.append('file', file.file)
  try {
    const path = await request.post('/user/common/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    form.avatar = path
    showToast('头像已上传，保存后生效')
  } catch {}
}

async function save() {
  loading.value = true
  try {
    await request.put('/user/user/profile', {
      sex: form.sex,
      avatar: form.avatar,
    })
    showToast('保存成功')
    setTimeout(() => history.back(), 600)
  } finally {
    loading.value = false
  }
}

onMounted(fetchProfile)
</script>
