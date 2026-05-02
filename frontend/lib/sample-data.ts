export function generateSamplePrices(
  start = 5000,
  count = 1000,
  seed = 42,
  drift = 0.0,
  volatility = 0.015
): number[] {
  const prices: number[] = [start]
  let price = start
  let s = seed
  const rand = () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
  for (let i = 1; i < count; i++) {
    const dailyReturn = drift + volatility * (rand() - 0.5) * 2
    price *= (1 + dailyReturn)
    prices.push(Math.round(price * 100) / 100)
  }
  return prices
}
