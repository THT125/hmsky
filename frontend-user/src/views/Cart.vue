<template>
  <div style="padding-bottom:60px">
    <van-nav-bar title="购物车" />
    <div v-if="!visibleItems.length" style="text-align:center;padding:100px 0;color:#999">购物车是空的</div>
    <div v-for="item in visibleItems" :key="item.id" style="display:flex;align-items:center;background:#fff;padding:12px;margin-bottom:8px">
      <van-image :src="item.image" width="60" height="60" fit="cover" radius="6" />
      <div style="flex:1;margin-left:10px">
        <div style="font-size:14px">{{ item.name }}</div>
        <div v-if="item.dishFlavor" style="color:#999;font-size:12px">{{ item.dishFlavor }}</div>
        <span style="color:#ee0a24;font-size:16px">¥{{ item.amount }}</span>
      </div>
      <van-stepper v-model="item.number" :min="0" @change="(v) => onChange(item, v)" />
    </div>
    <!-- 底部结算 -->
    <div v-if="visibleItems.length" style="position:fixed;bottom:50px;left:0;right:0;display:flex;align-items:center;justify-content:space-between;background:#fff;padding:12px 16px;border-top:1px solid #ebedf0">
      <span>合计: <span style="color:#ee0a24;font-size:18px;font-weight:bold">¥{{ total }}</span></span>
      <van-button type="danger" round @click="checkout">结算</van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onActivated, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()
const items = ref([])

// 只显示数量 > 0 的商品(v-if 与 v-for 同元素无法访问 item,用 computed 过滤)
const visibleItems = computed(() => items.value.filter(i => i.number > 0))

const total = computed(() => {
  return visibleItems.value.reduce((sum, i) => sum + Number(i.amount) * i.number, 0).toFixed(2)
})

async function fetchCart() {
  items.value = (await request.get('/user/shoppingCart/list')) || []
  // 初始化每个商品的基准数量:保证加载后的第一次增减也能正确同步后端
  items.value.forEach(i => { prevNumbers[i.id] = i.number })
}

// 记录每个商品上一次数量,用于判断增减方向同步后端
const prevNumbers = {}

function cartPayload(item) {
  return {
    dishId: item.dishId || null,
    setmealId: item.setmealId || null,
    dishFlavor: item.dishFlavor || null,
  }
}

async function onChange(item, val) {
  const prev = prevNumbers[item.id] ?? val
  prevNumbers[item.id] = val

  if (val > prev) {
    // 数量增加:同步 add
    await request.post('/user/shoppingCart/add', cartPayload(item))
  } else if (val < prev) {
    if (val <= 0) {
      // 减到 0:立即从列表移除并删除后端记录
      items.value = items.value.filter(i => i.id !== item.id)
      try {
        await request.post('/user/shoppingCart/sub', cartPayload(item))
      } catch {
        fetchCart() // 后端删除失败,重新拉取恢复
      }
    } else {
      // 数量减少(未到 0):同步 sub
      await request.post('/user/shoppingCart/sub', cartPayload(item))
    }
  }
}

function checkout() {
  router.push('/order/confirm')
}

onMounted(fetchCart)
onActivated(fetchCart)  // 每次回到购物车页刷新数据(配合 TabBar 布局的 keep-alive 场景)
</script>
