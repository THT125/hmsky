import { createRouter, createWebHistory } from 'vue-router'
import { isLoggedIn } from '../utils/auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { title: '登录', public: true } },
  { path: '/register', name: 'Register', component: () => import('../views/Register.vue'), meta: { title: '注册', public: true } },
  {
    path: '/',
    component: () => import('../views/HomeLayout.vue'),
    redirect: '/home',
    children: [
      { path: 'home', name: 'Home', component: () => import('../views/Home.vue'), meta: { title: '首页' } },
      { path: 'cart', name: 'Cart', component: () => import('../views/Cart.vue'), meta: { title: '购物车' } },
      { path: 'orders', name: 'Orders', component: () => import('../views/OrderList.vue'), meta: { title: '订单' } },
      { path: 'mine', name: 'Mine', component: () => import('../views/Mine.vue'), meta: { title: '我的' } },
    ],
  },
  { path: '/profile', name: 'Profile', component: () => import('../views/Profile.vue') },
  { path: '/change-password', name: 'ChangePassword', component: () => import('../views/ChangePassword.vue') },
  { path: '/chat', name: 'Chat', component: () => import('../views/Chat.vue') },
  { path: '/coupon', name: 'Coupon', component: () => import('../views/Coupon.vue') },
  { path: '/my-coupon', name: 'MyCoupon', component: () => import('../views/MyCoupon.vue') },
  { path: '/order/confirm', name: 'OrderConfirm', component: () => import('../views/OrderConfirm.vue') },
  { path: '/order/detail/:id', name: 'OrderDetail', component: () => import('../views/OrderDetail.vue') },
  { path: '/address', name: 'AddressList', component: () => import('../views/AddressList.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

// 全局路由守卫:未登录一律跳登录页(纯账号制,无游客态)
router.beforeEach((to) => {
  if (to.meta.public) return true // 登录/注册页放行
  if (!isLoggedIn()) return { path: '/login', query: { redirect: to.fullPath } }
  return true
})

export default router
