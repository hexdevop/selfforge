import { expect, it } from 'vitest'
import type { Location } from '@/api/locations'
import type { Program } from '@/api/programs'
import { initialPlaces } from './places'

const place = (id: string) => ({ id }) as Location
const program = (...ids: (string | null)[]) =>
  ({ weeks: [{ sessions: ids.map((location_id) => ({ location_id })) }] }) as Program

it('keeps the running program places', () => {
  expect(initialPlaces(program('a', 'b', 'a'), [place('a'), place('b')], 3)).toEqual([
    'a',
    'b',
    'a',
  ])
})

it.each([
  ['no program', null],
  ['a place was deleted', program('a', null, 'a')],
  ['days changed', program('b', 'b')],
])('falls back to the default place when %s', (_, active) => {
  expect(initialPlaces(active, [place('a'), place('b')], 3)).toEqual(['a', 'a', 'a'])
})

it('has nothing to offer without places', () => {
  expect(initialPlaces(null, [], 3)).toEqual([])
})
