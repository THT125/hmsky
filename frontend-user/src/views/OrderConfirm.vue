<template>
  <div>
    <van-nav-bar title="确认订单" left-text="返回" @click-left="$router.back()" />
    <div style="padding:12px">
      <!-- 选择地址 -->
      <van-cell-group style="margin-bottom:12px;border-radius:8px;overflow:hidden">
        <van-cell title="收货地址" is-link :value="addrText" @click="$router.push('/address')" />
      </van-cell-group>
      <van-cell-group style="margin-bottom:12px;border-radius:8px;overflow:hidden">
        <van-cell title="餐具数量"><van-stepper v-model="form.tablewareNumber" :min="0" /></van-cell>
        <van-cell title="配送方式"><van-radio-group v-model="form.deliveryStatus" direction="horizontal"><van-radio :name="1">立即送出</van-radio></van-radio-group></van-cell>
        <van-field v-model="form.remark" label="备注" placeholder="选填" />
      </van-cell-group>
      <!-- 费用 -->
      <van-cell-group style="margin-bottom:12px;border-radius:8px;overflow:hidden">
        <van-cell title="商品小计" :value="'¥'+subtotal" />
        <van-cell title="打包费"><van-stepper v-model="form.packAmount" :min="0" :step="1" /></van-cell>
        <van-cell title="配送费" value="¥6.00" />
      </van-cell-group>
      <div style="position:fixed;bottom:0;left:0;right:0;display:flex;align-items:center;justify-content:space-between;background:#fff;padding:12px 16px;border-top:1px solid #ebedf0">
        <span>应付: <span style="color:#ee0a24;font-size:20px;font-weight:bold">¥{{ total }}</span></span>
        <van-button type="danger" round :loading="submitting" @click="submit">提交订单</van-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '@/utils/request'

const router = useRouter()
const cartItems = ref([])
const defaultAddr = ref(null)
const submitting = ref(false)
const form = reactive({
  addressBookId: null,
  amount: 0,
  deliveryStatus: 1,
  packAmount: 0,
  payMethod: 1,
  remark: '',
  tablewareNumber: 0,
  tablewareStatus: 1,
})

const subtotal = computed(() => cartItems.value.reduce((s,i)=>s+Number(i.amount)*i.number,0).toFixed(2))
const total = computed(() => (Number(subtotal.value) + Number(form.packAmount) + 6).toFixed(2))
const addrText = computed(() => defaultAddr.value ? `${defaultAddr.value.detail} ${defaultAddr.value.consignee} ${defaultAddr.value.phone}` : '请选择地址')

async function fetchData() {
  cartItems.value = (await request.get('/user/shoppingCart/list')) || []
  try { defaultAddr.value = await request.get('/user/addressBook/default') } catch {}
  if (defaultAddr.value) form.addressBookId = defaultAddr.value.id
}

async function submit() {
  if (!form.addressBookId) { showToast('请选择收货地址'); return }
  if (!cartItems.value.length) { showToast('购物车为空，无法下单'); return }
  form.amount = total.value
  submitting.value = true
  try {
    const data = await request.post('/user/order/submit', form)
    // 模拟支付(后端提交时已在同一事务中清空购物车)
    await request.put('/user/order/payment', { orderNumber: data.orderNumber, payMethod: 1 })
    showToast('下单成功')
    router.push('/orders')
  } finally { submitting.value = false }
}

onMounted(fetchData)
</script>
