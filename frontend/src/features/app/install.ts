/** iPhone or iPad Safari, where installing is a manual trip through the Share menu. */
export function isIosSafari(userAgent: string, maxTouchPoints: number): boolean {
  const iPhone = /iPhone|iPod/.test(userAgent)
  // iPadOS 13+ says it's a Mac; touch points give it away.
  const iPad = /iPad/.test(userAgent) || (/Macintosh/.test(userAgent) && maxTouchPoints > 1)
  const otherBrowser = /CriOS|FxiOS|EdgiOS|OPiOS|YaBrowser/.test(userAgent)
  return (iPhone || iPad) && !otherBrowser
}

export function isInstalled(): boolean {
  const standalone = (navigator as Navigator & { standalone?: boolean }).standalone
  return standalone === true || window.matchMedia('(display-mode: standalone)').matches
}

const DISMISSED = 'selfforge:install-hint-dismissed'

export function wasDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED) === '1'
  } catch {
    return false
  }
}

export function dismiss(): void {
  try {
    localStorage.setItem(DISMISSED, '1')
  } catch {
    // Private mode: the hint just comes back next time.
  }
}
