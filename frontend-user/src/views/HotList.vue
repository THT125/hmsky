<template>
  <div style="min-height:100vh;background:#f7f8fa">
    <van-nav-bar title="热销榜" left-text="返回" @click-left="$router.back()" />
    <van-tabs v-model:active="active" @change="load">
      <van-tab title="热销菜品"></van-tab>
      <van-tab title="热销套餐"></van-tab>
    </van-tabs>
    <div style="padding:12px">
      <div v-for="item in list" :key="item.id" style="display:flex;background:#fff;border-radius:8px;margin-bottom:10px;padding:8px;align-items:center">
        <!-- 排名 -->
        <div :style="{
          width:32,height:32,borderRadius:'50%',display:'flex',alignItems:'center',justifyContent:'center',
          fontWeight:'bold',color:'#fff',flexShrink:0,
          background:item.rank<=3 ? (item.rank===1?'#f5222d':(item.rank===2?'#fa8c16':'#fadb14')) : '#c0c4cc',
        }">{{ item.rank }}</div>
        <van-image :src="item.image" width="64" height="64" fit="cover" radius="6" style="margin:0 10px;flex-shrink:0" />
        <div style="flex:1;min-width:0">
          <div style="font-size:15px;font-weight:500">{{ item.name }}</div>
          <div style="color:#999;font-size:12px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ item.description }}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px">
            <span style="color:#ee0a24;font-size:15px">¥{{ item.price }}</span>
            <span style="color:#999;font-size:12px">已售 {{ item.sold }} 份</span>
          </div>
        </div>
        <van-icon name="add" size="22" color="#ee0a24" style="margin-left:8px" @click="addCart(item)" />
      </div>
      <div v-if="!list.length" style="text-align:center;padding:60px 0;color:#999">暂无销量数据,快去下单吧</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import request from '@/utils/request'

const active = ref(0)
const list = ref([])

async function load() {
  const type = active.value === 0 ? 1 : 2
  list.value = (await request.get('/user/hot/list', { params: { type, top: 10 } })) || []
}

async function addCart(item) {
  const body = active.value === 0 ? { dishId: item.id } : { setmealId: item.id }
  await request.post('/user/shoppingCart/add', body)
  showToast('已加入购物车')
}

onMounted(load)
</script>
