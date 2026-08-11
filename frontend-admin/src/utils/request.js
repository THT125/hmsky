import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '',
  timeout: 30000,
})

// 请求拦截:管理端 token 加在 header.token
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('adminToken')
  if (token) {
    config.headers.token = token
  }
  return config
})

// 响应拦截:统一处理 Result{code, msg, data}
request.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && body.code !== 1) {
      // token 过期/不合法:清除登录态并跳转登录页
      const msg = body.msg || ''
      if (msg.includes('token')) {
        localStorage.removeItem('adminToken')
        localStorage.removeItem('adminName')
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login'
        }
      }
      ElMessage.error(msg || '请求失败')
      return Promise.reject(msg)
    }
    return body.data
  },
  (err) => {
    ElMessage.error('网络错误')
    return Promise.reject(err)
  },
)

export default request
