import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/',
    component: () => import('../layout/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '工作台' } },
      { path: 'employee', name: 'Employee', component: () => import('../views/Employee.vue'), meta: { title: '员工管理' } },
      { path: 'category', name: 'Category', component: () => import('../views/Category.vue'), meta: { title: '分类管理' } },
      { path: 'dish', name: 'Dish', component: () => import('../views/Dish.vue'), meta: { title: '菜品管理' } },
      { path: 'setmeal', name: 'Setmeal', component: () => import('../views/Setmeal.vue'), meta: { title: '套餐管理' } },
      { path: 'order', name: 'Order', component: () => import('../views/Order.vue'), meta: { title: '订单管理' } },
      { path: 'chat', name: 'Chat', component: () => import('../views/Chat.vue'), meta: { title: '客服消息' } },
      { path: 'coupon', name: 'Coupon', component: () => import('../views/Coupon.vue'), meta: { title: '优惠券管理' } },
      { path: 'report', name: 'Report', component: () => import('../views/Report.vue'), meta: { title: '数据统计' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from) => {
  const token = localStorage.getItem('adminToken')
  // 未登录访问受保护页面 → 跳登录页
  if (to.name !== 'Login' && !token) {
    return '/login'
  }
  // 已登录访问登录页 → 跳回首页
  if (to.name === 'Login' && token) {
    return '/'
  }
})

export default router
