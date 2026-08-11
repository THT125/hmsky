<template>
  <div>
    <van-nav-bar title="地址簿" left-text="返回" @click-left="$router.back()" />
    <div style="padding:12px">
      <div v-for="a in addrs" :key="a.id" style="background:#fff;padding:12px;margin-bottom:10px;border-radius:8px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <span style="font-weight:500;font-size:15px">{{ a.consignee }}</span>
            <span style="margin-left:8px;color:#666">{{ a.phone }}</span>
            <van-tag v-if="a.isDefault" type="danger" size="mini" style="margin-left:6px">默认</van-tag>
          </div>
          <div>
            <van-icon name="edit" size="18" style="margin-right:12px" @click="openDialog(a)" />
            <van-icon name="delete-o" size="18" color="#f56c6c" @click="del(a.id)" />
          </div>
        </div>
        <div style="color:#999;font-size:13px;margin-top:4px">{{ getName(a) }} {{ a.detail }}</div>
        <div style="margin-top:6px">
          <van-button v-if="!a.isDefault" size="small" plain @click="setDefault(a.id)">设为默认</van-button>
        </div>
      </div>
      <van-button type="primary" block @click="openDialog()">新增地址</van-button>
    </div>

    <!-- 新增/编辑 -->
    <van-popup v-model:show="showPopup" position="bottom" :style="{ height: '70%' }">
      <van-nav-bar :title="isEdit?'编辑地址':'新增地址'" right-text="保存" @click-right="save" @click-left="showPopup=false" />
      <div style="padding:12px">
        <van-field v-model="form.consignee" label="收货人" placeholder="必填" />
        <van-field v-model="form.phone" label="手机号" placeholder="必填" />
        <van-field v-model="form.provinceName" label="省" placeholder="如: 北京市" />
        <van-field v-model="form.cityName" label="市" placeholder="如: 北京市" />
        <van-field v-model="form.districtName" label="区" placeholder="如: 朝阳区" />
        <van-field v-model="form.detail" label="详细地址" placeholder="必填" />
        <van-field v-model="form.label" label="标签" placeholder="如: 家/公司" />
        <van-radio-group v-model="form.sex" direction="horizontal" style="padding:12px 16px">
          <van-radio name="1">男</van-radio>
          <van-radio name="0">女</van-radio>
        </van-radio-group>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import request from '@/utils/request'

const addrs = ref([])
const showPopup = ref(false)
const isEdit = ref(false)
const form = reactive({ id: null, consignee: '', phone: '', sex: '1', detail: '', provinceName: '', cityName: '', districtName: '', label: '', isDefault: 0 })

function getName(a) { return [a.provinceName, a.cityName, a.districtName].filter(Boolean).join('') }

async function fetch() { addrs.value = (await request.get('/user/addressBook/list')) || [] }

// 重置表单:显式重建所有字段(防止残留上一次编辑的额外字段)
function resetForm() {
  Object.assign(form, { id: null, consignee: '', phone: '', sex: '1', detail: '', provinceName: '', cityName: '', districtName: '', label: '', isDefault: 0 })
}

function openDialog(row) {
  isEdit.value = !!row
  resetForm()
  if (row) Object.assign(form, { ...row })
  showPopup.value = true
}

async function save() {
  if (!form.consignee || !form.phone || !form.detail) { showToast('请填写完整信息'); return }
  if (!/^1\d{10}$/.test(form.phone)) { showToast('手机号格式不正确(11位数字)'); return }
  if (isEdit.value) await request.put('/user/addressBook', form)
  else await request.post('/user/addressBook', form)
  showToast('保存成功'); showPopup.value = false; fetch()
}

async function setDefault(id) { await request.put('/user/addressBook/default', { id }); showToast('已设为默认'); fetch() }
async function del(id) {
  try {
    await showConfirmDialog({ title: '提示', message: '确认删除该地址？' })
  } catch {
    return // 用户取消
  }
  await request.delete('/user/addressBook', { params: { id } }); showToast('已删除'); fetch()
}

onMounted(fetch)
</script>
