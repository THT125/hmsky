<template>
  <div>
    <!-- 店铺状态条 -->
    <van-notice-bar v-if="!shopOpen" mode="closeable" color="#f56c6c" background="#fef0f0">
      店铺已打烊，暂无法下单
    </van-notice-bar>

    <div style="display:flex;height:calc(100vh - 50px)">
      <!-- 左侧分类(禁用的分类仍显示,置灰标记) -->
      <div style="width:90px;background:#fff;overflow-y:auto">
        <div v-for="c in categories" :key="c.id"
          @click="selectCategory(c)"
          :style="{padding:'12px 8px',textAlign:'center',fontSize:'14px',background:selectedId===c.id?'#fff':'#f7f8fa',color:c.status===0?'#999':(selectedId===c.id?'#ee0a24':'#323233'),borderLeft:selectedId===c.id?'3px solid #ee0a24':'3px solid transparent'}"
        >
          <div>{{ c.name }}</div>
          <div v-if="c.status===0" style="font-size:10px;color:#c45656">已禁用</div>
        </div>
      </div>

      <!-- 右侧内容 -->
      <div style="flex:1;overflow-y:auto;padding:12px">
        <!-- 菜品列表 -->
        <div v-for="d in dishes" :key="'d'+d.id" style="display:flex;background:#fff;margin-bottom:10px;border-radius:8px;padding:8px">
          <van-image :src="d.image" width="80" height="80" fit="cover" radius="6" style="flex-shrink:0" />
          <div style="flex:1;margin-left:10px">
            <div style="font-size:15px;font-weight:500">{{ d.name }}</div>
            <div style="color:#999;font-size:12px;margin:4px 0">{{ d.description }}</div>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span style="color:#ee0a24;font-size:16px">¥{{ d.price }}</span>
              <van-icon name="add" size="22" :color="catDisabled ? '#ccc' : '#ee0a24'" @click="addDish(d)" />
            </div>
            <!-- 口味选择(若有) -->
            <div v-if="d.flavors&&d.flavors.length" style="margin-top:6px">
              <template v-for="f in d.flavors" :key="f.name">
                <div style="font-size:12px;color:#666;margin-bottom:2px">{{ f.name }}</div>
                <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:4px">
                  <span v-for="v in parseValues(f.value)" :key="v" @click="selectedFlavors[d.id]=v"
                    :style="{padding:'2px 8px',fontSize:'12px',borderRadius:'12px',border:selectedFlavors[d.id]===v?'1px solid #ee0a24':'1px solid #ddd',color:selectedFlavors[d.id]===v?'#ee0a24':'#666'}"
                  >{{ v }}</span>
                </div>
              </template>
            </div>
          </div>
        </div>
        <!-- 套餐列表 -->
        <div v-for="s in setmeals" :key="'s'+s.id" style="display:flex;background:#fff;margin-bottom:10px;border-radius:8px;padding:8px">
          <van-image :src="s.image" width="80" height="80" fit="cover" radius="6" style="flex-shrink:0" />
          <div style="flex:1;margin-left:10px">
            <div style="font-size:15px;font-weight:500;color:#323233">{{ s.name }}</div>
            <div style="color:#999;font-size:12px;margin:4px 0">{{ s.description }}</div>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span style="color:#ee0a24;font-size:16px">¥{{ s.price }}</span>
              <van-icon name="add" size="22" :color="catDisabled ? '#ccc' : '#ee0a24'" @click="addSetmeal(s)" />
            </div>
          </div>
        </div>
        <div v-if="!dishes.length&&!setmeals.length" style="text-align:center;padding:60px 0;color:#999">该分类下暂无商品</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { showToast } from 'vant'
import request from '@/utils/request'

const categories = ref([])
const dishes = ref([])
const setmeals = ref([])
const selectedId = ref(0)
const selectedCat = ref(null) // 当前选中分类(含 status)
const selectedFlavors = ref({})
const shopOpen = ref(true)

// 当前分类是否已禁用(禁用则不可加购)
const catDisabled = computed(() => selectedCat.value && selectedCat.value.status === 0)

function parseValues(val) {
  try { return JSON.parse(val) } catch { return [] }
}

async function init() {
  // 店铺状态
  try { shopOpen.value = await request.get('/user/shop/status') === 1 } catch {}
  // 分类
  await refreshCategories()
}

async function refreshCategories() {
  categories.value = (await request.get('/user/category/list')) || []
  if (!categories.value.some(c => c.id === selectedId.value)) {
    if (categories.value.length) selectCategory(categories.value[0])
  } else {
    refreshCurrent()
  }
}

async function refreshCurrent() {
  const cat = categories.value.find(c => c.id === selectedId.value)
  if (cat) selectCategory(cat)
}

// 收到 WebSocket 推送:店铺状态/菜单变更自动刷新
function handleShopStatusChange() {
  request.get('/user/shop/status').then(s => { shopOpen.value = s === 1 }).catch(() => {})
}

onMounted(() => {
  window.addEventListener('shop-status-change', handleShopStatusChange)
  window.addEventListener('menu-update', refreshCategories)
})
onBeforeUnmount(() => {
  window.removeEventListener('shop-status-change', handleShopStatusChange)
  window.removeEventListener('menu-update', refreshCategories)
})

async function selectCategory(cat) {
  selectedId.value = cat.id
  selectedCat.value = cat
  if (cat.type === 1) {
    dishes.value = (await request.get('/user/dish/list', { params: { categoryId: cat.id } })) || []
    setmeals.value = []
  } else {
    dishes.value = []
    setmeals.value = (await request.get('/user/setmeal/list', { params: { categoryId: cat.id } })) || []
  }
}

async function addDish(d) {
  if (catDisabled.value) { showToast('该分类已禁用，无法购买'); return }
  const flavor = selectedFlavors.value[d.id] || null
  await request.post('/user/shoppingCart/add', { dishId: d.id, dishFlavor: flavor })
  showToast('已加入购物车')
}

async function addSetmeal(s) {
  if (catDisabled.value) { showToast('该分类已禁用，无法购买'); return }
  await request.post('/user/shoppingCart/add', { setmealId: s.id })
  showToast('已加入购物车')
}

onMounted(init)
</script>
