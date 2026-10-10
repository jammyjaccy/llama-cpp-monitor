// 后端以 UTC 存储时间，格式 `YYYY-MM-DD HH:MM:SS`（无时区标记）。
// 显示时补 'Z' 标记按 UTC 解析，再格式化为浏览器本地时区的 `YYYY-MM-DD HH:mm:ss`。
export function formatLocalTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value.replace(' ', 'T') + 'Z')
  if (Number.isNaN(d.getTime())) return value // 解析失败原样显示，不抛异常
  const p = (n: number) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ` +
    `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
  )
}
