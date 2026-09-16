import { describe, expect, it } from 'vitest'
import { coarse, degrees, isOutdoor } from './format'

describe('weather helpers', () => {
  it('only outdoor places get a forecast', () => {
    expect(isOutdoor('outdoor_gym')).toBe(true)
    expect(isOutdoor('outdoor_bare')).toBe(true)
    expect(isOutdoor('home')).toBe(false)
    expect(isOutdoor('travel')).toBe(false)
  })

  it('never sends a position finer than about a kilometre', () => {
    expect(coarse(55.751244)).toBe(55.75)
    expect(coarse(37.618423)).toBe(37.62)
    expect(coarse(-0.004)).toBe(-0)
  })

  it('shows temperatures with a sign and a proper minus', () => {
    expect(degrees(14.6)).toBe('+15°')
    expect(degrees(-7.2)).toBe('−7°')
    expect(degrees(0.3)).toBe('0°')
  })
})
