Redis 最终数据验证

sign:43:202608
  type=string(位图)    ✓
  ttl=5183980秒(≈60天) ✓ EXPIRE 生效,且没有覆盖值
  本月签到日: [30]       ✓ 今天(8月30日)签到,位图正确
  bitcount=1            ✓
功能总览
层	实现
Redis(Bitmap)	sign:{userId}:{yyyyMM} 位图:第 day-1 位=当天是否签到;SETBIT 签到、GETBIT 判重、BITCOUNT 月天数、BITFIELD 一次取整月位图
连续签到	BITFIELD 取位图 → 位运算从今天往前数连续 1;今天=最低位(BITFIELD 位序实测修正)
奖励	连续 5 天 → 懒创建"签到奖励20元券"模板(20元/无门槛/30天有效)→ 发放 user_coupon(幂等:已持有不再发)
接口	POST /user/sign(签到)、GET /user/sign/status(状态+日历)
前端	Sign.vue:连续天数头部 + 本月签到日历 + 签到按钮;Mine.vue「每日签到」入口
过程中踩的坑(教学价值拉满)
坑	根因	修复
BITFIELD 位序反了	GET u{n} 0 返回的整数,offset 最远位在 LSB(实测 setbit 29 → 0b1)	第 i 天 = bits >> (n-1-i)
SETEX 销毁位图(最经典!)	想给位图设 TTL 用了 SETEX,整个 key 被覆盖成字符串 "1"	位图/计数结构设 TTL 必须用 EXPIRE(只改过期时间不动值)
redis-py bitfield API 差异	r.bitfield(key, ...) 签名不兼容	改用 execute_command 发原始命令
验证矩阵
验证	结果
pytest 新增 5 用例(签到/重复拒绝/5天发券/奖励幂等/状态日历)	✅ 145/145
smoke_test 新增 3 检查点(签到→重复拒→状态)	✅ 110/110
浏览器体验路径
用户端「我的 → 每日签到」:签到 → 连续天数 +1 → 日历今日点亮;连续 5 天后自动发放 20 元无门槛券(「我的券」可见)。

这就是 Bitmap 的全部核心用法:位操作 + 位统计 + 位序理解 + EXPIRE 陷阱——第 1 步完成,随时可以进入第 2 步(ZSet 热销排行榜)。