// Same character weights as AstrBot EstimateTokenCounter; this is not billing usage.
export function statistics(text) {
  const chars = Array.from(text), chinese = chars.filter(c => /[\u4e00-\u9fff]/u.test(c)).length;
  const emoji = chars.filter(c => /[\u200d\u2600-\u27bf\ufe00-\ufe0f\u{1f000}-\u{1faff}]/u.test(c)).length;
  return `${chars.length} 字 · 估计 ${Math.trunc(chinese * 0.6 + emoji * 2 + (chars.length - chinese - emoji) * 0.3)} Tokens`;
}
