import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/utils'

export type Choice = { value: string; label: string; description?: string }

type ChoiceGroupProps = {
  legend: ReactNode
  hint?: string
  error?: string
  choices: Choice[]
  type?: 'radio' | 'checkbox'
  /** Stack full-width rows (with descriptions) instead of inline chips. */
  stacked?: boolean
  /** Controlled mode (without react-hook-form): the checked values and a toggle callback. */
  selected?: string[]
  onSelect?: (value: string) => void
} & Omit<ComponentProps<'input'>, 'type'>

/** Native radios/checkboxes styled as chips: keyboard and screen readers work for free. */
export function ChoiceGroup({
  legend,
  hint,
  error,
  choices,
  type = 'radio',
  stacked = false,
  selected,
  onSelect,
  ...inputProps
}: ChoiceGroupProps) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-2">
      <legend className="mb-2 text-base font-medium">{legend}</legend>
      {hint && <p className="-mt-1 mb-1 text-sm text-muted-foreground">{hint}</p>}
      <div className={cn('flex gap-2', stacked ? 'flex-col' : 'flex-wrap')}>
        {choices.map((choice) => (
          <label key={choice.value} className="relative">
            <input
              type={type}
              value={choice.value}
              className="peer sr-only"
              {...inputProps}
              {...(selected && {
                checked: selected.includes(choice.value),
                onChange: () => onSelect?.(choice.value),
              })}
            />
            <span
              className={cn(
                'flex min-h-11 cursor-pointer flex-col justify-center rounded-lg border bg-card px-3 py-2 text-base',
                'peer-checked:border-primary peer-checked:bg-primary peer-checked:text-primary-foreground',
                'peer-focus-visible:ring-3 peer-focus-visible:ring-ring/50',
                stacked && 'px-4',
              )}
            >
              <span className={cn(stacked && 'font-medium')}>{choice.label}</span>
              {choice.description && (
                <span className="text-sm opacity-80">{choice.description}</span>
              )}
            </span>
          </label>
        ))}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </fieldset>
  )
}
