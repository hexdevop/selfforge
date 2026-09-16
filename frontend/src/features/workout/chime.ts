type AudioCtor = typeof AudioContext

let context: AudioContext | null = null

function audio(): AudioContext | null {
  const Ctor: AudioCtor | undefined =
    window.AudioContext ?? (window as { webkitAudioContext?: AudioCtor }).webkitAudioContext
  if (!Ctor) return null
  context ??= new Ctor()
  return context
}

/**
 * The end-of-rest signal, through Web Audio.
 *
 * Not vibration: `navigator.vibrate` does nothing in Safari on iOS, so a phone left face
 * down would give no sign at all.
 */
export function chime(): void {
  const ctx = audio()
  if (!ctx) return
  void ctx.resume().catch(() => {})

  const at = ctx.currentTime
  const gain = ctx.createGain()
  gain.connect(ctx.destination)
  // Short, quiet, and faded out: a click at full volume next to the ear is unpleasant.
  gain.gain.setValueAtTime(0.0001, at)
  gain.gain.exponentialRampToValueAtTime(0.25, at + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.45)

  const tone = ctx.createOscillator()
  tone.type = 'sine'
  tone.frequency.setValueAtTime(880, at)
  tone.frequency.setValueAtTime(1175, at + 0.18)
  tone.connect(gain)
  tone.start(at)
  tone.stop(at + 0.5)
}

/** iOS only lets audio start from a gesture: warm the context up on the first tap. */
export function primeChime(): void {
  void audio()
    ?.resume()
    .catch(() => {})
}
