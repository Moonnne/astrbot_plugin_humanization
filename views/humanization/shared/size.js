// Display bytes with a consistent 1024-based scale; stored values stay in bytes.
export function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.max(0, Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1));
  return `${(bytes / 1024 ** index).toLocaleString('zh-CN', {maximumFractionDigits:index ? 2 : 0})} ${units[index]}`;
}
