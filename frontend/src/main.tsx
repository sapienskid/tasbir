import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { SWRConfig } from "swr"
import { apiFetcher } from "@/lib/api"
import App from "@/App"
import "@/index.css"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SWRConfig
      value={{
        fetcher: apiFetcher,
        dedupingInterval: 2000,
        shouldRetryOnError: false,
      }}
    >
      <App />
    </SWRConfig>
  </StrictMode>
)
