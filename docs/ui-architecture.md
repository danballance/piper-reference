# UI Architecture Guide

## Overview

The frontend is a **Vite** single-page application using **React 19**, **TypeScript**, and **TanStack Router** for file-based routing. Code is organized into feature modules that mirror the backend's bounded contexts. The API contract is enforced by generating TypeScript types and SDK functions directly from the backend's OpenAPI schema.

## Module Structure

```
ui/src/
├── main.tsx                         # Composition root (router + QueryClient)
├── routeTree.gen.ts                 # AUTO-GENERATED route tree
├── index.css                        # Tailwind + design tokens
├── routes/                          # File-based routes (thin wrappers)
│   ├── __root.tsx                   # Root layout
│   └── index.tsx                    # Page: wires components to data
├── features/                        # One directory per bounded context
│   └── <feature>/
│       ├── queries.ts               # TanStack Query options + mutations
│       ├── store.ts                 # Zustand client state
│       └── components/
│           └── <component>.tsx      # Presentational components
├── api/
│   ├── client.ts                    # Base URL configuration
│   └── generated/                   # AUTO-GENERATED (never edit)
├── components/
│   └── ui/                          # shadcn/ui components (owned source)
└── lib/
    └── utils.ts                     # cn() class merging helper
```

Each feature (e.g. `todo/`) is self-contained. Add new features by copying this structure.

## Data Flow

```
schema/openapi.json
  │
  │  pnpm codegen (Hey API)
  ▼
src/api/generated/         types, SDK functions, TanStack Query hooks
  │
  │  thin re-export
  ▼
features/todo/queries.ts   domain-named query/mutation options
  │
  │  ensureQueryData in route loader
  ▼
routes/index.tsx           wires queries + mutations to components
  │
  │  props down, events up
  ▼
features/todo/components/  presentational React components
```

The OpenAPI schema is the single source of truth. Frontend types are never hand-written for API data.

## Routing

Routes live in `src/routes/` and are auto-discovered by the TanStack Router Vite plugin. The plugin generates `routeTree.gen.ts` at build time.

Route files are **thin wrappers** that import from `features/`. Business logic lives in feature modules, not route files.

```typescript
// routes/index.tsx
export const Route = createFileRoute("/")({
  loader: ({ context }) =>
    context.queryClient.ensureQueryData(todoListOptions()),
  component: IndexPage,
})
```

The `loader` prefetches data before the route renders, eliminating waterfalls. The `queryClient` is passed through router context from `main.tsx`.

Add a new route by creating a file in `src/routes/`. The plugin picks it up automatically.

## State Management

| Concern | Tool | Location | Example |
|---|---|---|---|
| **Server state** | TanStack Query | `features/*/queries.ts` | Todo list, mutations |
| **Client state** | Zustand | `features/*/store.ts` | Filter selection |
| **Component state** | `useState` | Inline | Form input focus |

TanStack Query owns all server-derived data. Zustand owns UI-only state that doesn't belong in the URL or the server cache. Use `useState` for ephemeral component state.

## API Integration

### Codegen Pipeline

Hey API reads the OpenAPI schema and generates TypeScript types, SDK functions, and TanStack Query hooks:

```typescript
// openapi-ts.config.ts
export default defineConfig({
  input: "../schema/openapi.json",
  output: "src/api/generated",
  plugins: [
    "@hey-api/typescript",
    "@hey-api/sdk",
    "@hey-api/client-fetch",
    "@tanstack/react-query",
  ],
})
```

Run `pnpm codegen` after any backend schema change. The `src/api/generated/` directory is gitignored and regenerated on demand.

### Re-export Layer

Feature modules re-export generated hooks with domain-friendly names. This decouples feature code from codegen output:

```typescript
// features/todo/queries.ts
export {
  getListOptions as todoListOptions,
  getListQueryKey as todoListQueryKey,
  addItemMutation,
  itemTitleUpdateItemMutation,
} from "@/api/generated/@tanstack/react-query.gen"
```

### Dev Proxy

In development, Vite proxies `/api/*` requests to the Litestar backend on port 8000, stripping the `/api` prefix:

```typescript
// vite.config.ts (partial)
server: {
  proxy: {
    "/api": {
      target: "http://localhost:8000",
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ""),
    },
  },
}
```

The API client sets its base URL to `/api`:

```typescript
// api/client.ts
client.setConfig({ baseUrl: "/api" })
```

## Components

Components follow the **props-in, events-out** pattern. They receive data and callbacks as props and never fetch data or manage global state directly.

```typescript
// features/todo/components/todo-item.tsx
interface TodoItemProps {
  title: string
  done: boolean
  onToggle: () => void
}

export function TodoItem({ title, done, onToggle }: TodoItemProps) {
  return (
    <div className="flex items-center gap-3 rounded-md border p-3">
      <Checkbox checked={done} onCheckedChange={onToggle} />
      <span className={cn("text-sm", done && "line-through text-muted-foreground")}>
        {title}
      </span>
    </div>
  )
}
```

Use shadcn/ui components (`Button`, `Input`, `Checkbox`, `Card`) from `@/components/ui/` as building blocks. These are owned source files, not an npm dependency.

## Forms

Forms use React Hook Form for state management and Zod for schema validation:

```typescript
// features/todo/components/todo-form.tsx
const todoFormSchema = z.object({
  title: z.string().min(1, "Title is required"),
})

export function TodoForm({ onSubmit }: TodoFormProps) {
  const {
    register, handleSubmit, reset,
    formState: { errors },
  } = useForm<TodoFormValues>({
    resolver: zodResolver(todoFormSchema),
    defaultValues: { title: "" },
  })

  const onFormSubmit = (values: TodoFormValues) => {
    onSubmit(values.title)
    reset()
  }
  // ...
}
```

The component receives a simple `onSubmit: (title: string) => void` callback. Form internals (validation, reset, error display) are encapsulated.

## Styling

- **Tailwind CSS v4** with CSS-based configuration (no `tailwind.config.js`).
- **shadcn/ui** provides accessible, composable components using Radix UI primitives.
- **`cn()`** from `@/lib/utils` merges Tailwind classes safely using `clsx` + `tailwind-merge`.
- Design tokens (colors, radii) are defined as CSS custom properties in `src/index.css`.

## Testing Conventions

Test structure mirrors source structure:

```
tests/
├── components/
│   └── todo/
│       ├── store.test.ts              # Zustand store logic
│       ├── todo-item.test.tsx         # Component rendering + interaction
│       ├── todo-form.test.tsx         # Form validation + submission
│       └── todo-list.test.tsx         # Filtering + composition
└── e2e/
    └── todo.spec.ts                   # Full-stack happy path
```

| Layer | Tool | Runs in | Tests |
|---|---|---|---|
| **Store tests** | Vitest | Browser (Playwright) | State transitions via `getState()`/`setState()` |
| **Component tests** | Vitest + vitest-browser-react | Real browser | Rendering, interaction, callbacks |
| **E2E tests** | Playwright | Real browser + real servers | Full user journeys |

Rules:
- **Function-style tests** only (no `describe` blocks for component tests, one assertion focus per test).
- **Real browser rendering** via Vitest Browser Mode with Playwright — not jsdom.
- **Props-based isolation** — component tests pass props directly, no API mocking needed.
- **E2E tests auto-start both servers** (Litestar on :8000, Vite on :5173) via Playwright config.

Example component test:

```typescript
// tests/components/todo/todo-item.test.tsx
test("calls onToggle when checkbox is clicked", async () => {
  const onToggle = vi.fn()
  const screen = await render(
    <TodoItem title="Buy groceries" done={false} onToggle={onToggle} />,
  )
  await screen.getByRole("checkbox").click()
  expect(onToggle).toHaveBeenCalledOnce()
})
```

## Development

| Command | Purpose |
|---|---|
| `pnpm dev` | Start Vite dev server (port 5173) |
| `pnpm build` | Production build to `dist/` |
| `pnpm codegen` | Regenerate API types from OpenAPI schema |
| `pnpm test` | Run component + store tests (Vitest Browser Mode) |
| `pnpm test:e2e` | Run E2E tests (starts both servers automatically) |

The backend must be running on port 8000 for `pnpm dev` to proxy API calls. Start it with:

```bash
uv run litestar --app api.main:create_app run --port 8000
```
