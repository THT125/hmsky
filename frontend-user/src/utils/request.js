import axios from 'axios'
import { showToast } from 'vant'

const request = axios.create({ baseURL: '', timeout: 15000 })

// 请求拦截:用户端 token 加在 header.authentication
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('userToken')
  if (token) config.headers.authentication = token
  return config
})

// 响应拦截:统一处理 Result{code, msg, data}
request.interceptors.response.use(
  async (res) => {
    const body = res.data
    if (body && body.code !== 1) {
      const msg = body.msg || '请求失败'
      // token 过期/失效:清除登录态并跳转登录页(纯账号制)
      if (msg.includes('token')) {
        localStorage.removeItem('userToken')
        localStorage.removeItem('userId')
        localStorage.removeItem('username')
        showToast('登录已失效，请重新登录')
        // 延迟跳转,避免与当前页面的错误提示冲突
        setTimeout(() => {
          if (!location.pathname.startsWith('/login')) location.href = '/login'
        }, 500)
        return Promise.reject(msg)
      }
      showToast(msg)
      return Promise.reject(msg)
    }
    return body.data
  },
  () => { showToast('网络错误'); return Promise.reject('网络错误') },
)

export default request
