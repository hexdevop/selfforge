import type { ReactNode } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipContentProps,
  XAxis,
  YAxis,
} from 'recharts'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'
import { formatKg } from '@/lib/format'
import { shortDate } from './format'

// One series per chart, drawn in ink; heat marks only progression (docs/05-frontend.md).
// Colors come from CSS so the dark theme swaps them in one place.
const AXIS = { fontSize: 13, fill: 'var(--muted-foreground)' }
const HEAT = 'var(--heat)'

type Frame = { title: string; hint?: string; table: ReactNode; children: ReactNode }

/** Every chart has its numbers as a table too: for screen readers and a quick exact look. */
export function ChartFrame({ title, hint, table, children }: Frame) {
  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="flex flex-col">
        <span className="font-medium">{title}</span>
        {hint && <span className="text-sm text-muted-foreground">{hint}</span>}
      </figcaption>
      <div className="h-48 w-full text-foreground" aria-hidden>
        {children}
      </div>
      <details className="text-sm">
        <summary className="flex min-h-11 cursor-pointer items-center text-muted-foreground">
          Показать таблицей
        </summary>
        {table}
      </details>
    </figure>
  )
}

export function DataTable({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full tabular-nums">
        <thead>
          <tr className="text-left text-muted-foreground">
            {head.map((h) => (
              <th key={h} className="py-1 pr-4 font-normal">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.join('|')} className="border-t">
              {row.map((cell, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: columns are positional
                <td key={i} className="py-1 pr-4">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Tip({ lines }: { lines: (string | null)[] }) {
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-sm">
      {lines.filter(Boolean).map((line, i) => (
        <p key={line} className={i === 0 ? 'text-muted-foreground' : 'tabular-nums'}>
          {line}
        </p>
      ))}
    </div>
  )
}

type Datum = Record<string, unknown> & { day: string }

function tooltip<T extends Datum>(render: (d: T) => (string | null)[]) {
  return ({ active, payload }: TooltipContentProps<ValueType, NameType>) => {
    const datum = payload?.[0]?.payload as T | undefined
    return active && datum ? <Tip lines={[shortDate(datum.day), ...render(datum)]} /> : null
  }
}

type Marked = { cx?: number; cy?: number; payload?: Record<string, unknown> }

/** Plain points stay small; a progression event gets a larger heat dot with a surface ring. */
function markedDot(flag: string) {
  return function Dot({ cx, cy, payload }: Marked) {
    if (cx === undefined || cy === undefined) return <g />
    const hot = Boolean(payload?.[flag])
    return (
      <circle
        cx={cx}
        cy={cy}
        r={hot ? 5 : 3}
        style={{ fill: hot ? HEAT : 'currentColor', stroke: 'var(--card)', strokeWidth: 2 }}
      />
    )
  }
}

const common = { margin: { top: 8, right: 8, bottom: 0, left: -12 } }

export function LevelChart({
  data,
  titleOf,
}: {
  data: { day: string; level: number; exercise: string; stepUp: boolean }[]
  titleOf: (slug: string) => string
}) {
  return (
    <ResponsiveContainer>
      <LineChart data={data} {...common}>
        <CartesianGrid vertical={false} stroke="var(--border)" />
        <XAxis
          dataKey="day"
          tickFormatter={shortDate}
          tick={AXIS}
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis
          allowDecimals={false}
          tick={AXIS}
          tickLine={false}
          axisLine={false}
          width={40}
          domain={['dataMin - 1', 'dataMax + 1']}
        />
        <Tooltip
          cursor={{ stroke: 'var(--steel-400)' }}
          content={tooltip<{ day: string; level: number; exercise: string; stepUp: boolean }>(
            (d) => [titleOf(d.exercise), `ступень ${d.level}`, d.stepUp ? 'Новая ступень' : null],
          )}
        />
        <Line
          type="stepAfter"
          dataKey="level"
          stroke="currentColor"
          strokeWidth={2}
          dot={markedDot('stepUp')}
          activeDot={{ r: 6, style: { fill: 'currentColor' } }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function ResultChart({
  data,
  format,
  titleOf,
}: {
  data: { day: string; value: number; exercise: string; record: boolean }[]
  format: (value: number) => string
  titleOf: (slug: string) => string
}) {
  return (
    <ResponsiveContainer>
      <LineChart data={data} {...common}>
        <CartesianGrid vertical={false} stroke="var(--border)" />
        <XAxis
          dataKey="day"
          tickFormatter={shortDate}
          tick={AXIS}
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis
          tick={AXIS}
          tickLine={false}
          axisLine={false}
          width={40}
          tickFormatter={(v: number) => formatKg(v)}
        />
        <Tooltip
          cursor={{ stroke: 'var(--steel-400)' }}
          content={tooltip<{ day: string; value: number; exercise: string; record: boolean }>(
            (d) => [titleOf(d.exercise), format(d.value), d.record ? 'Рекорд' : null],
          )}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="currentColor"
          strokeWidth={2}
          dot={markedDot('record')}
          activeDot={{ r: 6, style: { fill: 'currentColor' } }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function WeeklyBars({ data }: { data: { day: string; value: number }[] }) {
  return (
    <ResponsiveContainer>
      <BarChart data={data} {...common} barCategoryGap={2}>
        <CartesianGrid vertical={false} stroke="var(--border)" />
        <XAxis
          dataKey="day"
          tickFormatter={shortDate}
          tick={AXIS}
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis
          tick={AXIS}
          tickLine={false}
          axisLine={false}
          width={60}
          tickFormatter={(v: number) => formatKg(Math.round(v))}
        />
        <Tooltip
          cursor={{ fill: 'var(--muted)' }}
          content={tooltip<{ day: string; value: number }>((d) => [
            `${formatKg(d.value)} кг за неделю`,
          ])}
        />
        <Bar
          dataKey="value"
          fill="currentColor"
          radius={[4, 4, 0, 0]}
          maxBarSize={32}
          isAnimationActive={false}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function TrendLine({ data }: { data: { day: string; value: number }[] }) {
  return (
    <ResponsiveContainer>
      <LineChart data={data} {...common}>
        <CartesianGrid vertical={false} stroke="var(--border)" />
        <XAxis
          dataKey="day"
          tickFormatter={shortDate}
          tick={AXIS}
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis
          tick={AXIS}
          tickLine={false}
          axisLine={false}
          width={52}
          domain={['dataMin - 1', 'dataMax + 1']}
          tickFormatter={(v: number) => formatKg(v)}
        />
        <Tooltip
          cursor={{ stroke: 'var(--steel-400)' }}
          content={tooltip<{ day: string; value: number }>((d) => [
            `${formatKg(d.value)} кг в среднем за 7 дней`,
          ])}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="currentColor"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 5, style: { fill: 'currentColor' } }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
