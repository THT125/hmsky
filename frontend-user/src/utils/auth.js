/**
 * 登录态管理:账号密码制(注册/登录后保存 token 与用户信息)
 */

/** 登录/注册成功后保存登录态 */
export function setAuth(data) {
  localStorage.setItem('userToken', data.token)
  localStorage.setItem('userId', String(data.id || ''))
  localStorage.setItem('username', data.username || '')
}

/** 是否已登录 */
export function isLoggedIn() {
  return !!localStorage.getItem('userToken')
}

/** 退出登录:清除登录态(服务端 token 黑名单由请求层处理) */
export function logoutLocal() {
  localStorage.removeItem('userToken')
  localStorage.removeItem('userId')
  localStorage.removeItem('username')
}
