import { describe, expect, it } from 'vitest'
import { isIosSafari } from './install'

const UA = {
  iphoneSafari:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
  iphoneChrome:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/129.0 Mobile/15E148 Safari/604.1',
  ipadAsMac:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
  android:
    'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36',
}

describe('who needs the manual install hint', () => {
  it('Safari on iPhone', () => expect(isIosSafari(UA.iphoneSafari, 5)).toBe(true))
  it('an iPad that says it is a Mac', () => expect(isIosSafari(UA.ipadAsMac, 5)).toBe(true))
  it('not a real Mac', () => expect(isIosSafari(UA.ipadAsMac, 0)).toBe(false))
  it('not Chrome on iPhone, which cannot install', () =>
    expect(isIosSafari(UA.iphoneChrome, 5)).toBe(false))
  it('not Android, which offers install itself', () =>
    expect(isIosSafari(UA.android, 5)).toBe(false))
})
