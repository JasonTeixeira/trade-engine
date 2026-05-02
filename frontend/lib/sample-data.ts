export function generateSamplePrices(
  start = 5000,
  count = 200,
  seed = 42
): number[] {
  const prices: number[] = [start]
  let price = start
  let s = seed
  const rand = () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
  for (let i = 1; i < count; i++) {
    price += (rand() - 0.48) * price * 0.003 // slight upward bias
    prices.push(Math.round(price * 100) / 100)
  }
  return prices
}
