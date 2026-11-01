// Shapes of the server's DTOs, as the tools return them in structuredContent.

export interface Coverage {
  data_status?: string
  warning: string | null
}

// ActiveFilterDTO: a set filter in Croatian; argument is the tool argument that sets it.
export interface ActiveFilter {
  argument: string
  label: string
}
