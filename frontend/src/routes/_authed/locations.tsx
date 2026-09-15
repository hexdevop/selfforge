import { createFileRoute } from '@tanstack/react-router'
import { equipmentQuery } from '@/api/catalog'
import { locationsQuery } from '@/api/locations'
import { LocationsManager } from '@/features/inventory/locations-manager'

export const Route = createFileRoute('/_authed/locations')({
  loader: ({ context: { queryClient } }) =>
    Promise.all([
      queryClient.ensureQueryData(locationsQuery),
      queryClient.ensureQueryData(equipmentQuery),
    ]),
  component: LocationsPage,
})

function LocationsPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Места и инвентарь</h1>
      <LocationsManager withTools />
    </div>
  )
}
