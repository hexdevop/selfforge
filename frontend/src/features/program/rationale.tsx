/** The engine's «why it looks like this», paragraphs separated by blank lines. */
export function Rationale({ text }: { text: string }) {
  return (
    <div className="flex max-w-[70ch] flex-col gap-3">
      {text.split('\n\n').map((paragraph) => (
        <p key={paragraph}>{paragraph}</p>
      ))}
    </div>
  )
}
