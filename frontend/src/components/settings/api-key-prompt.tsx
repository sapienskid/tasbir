import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { getApiKey, setApiKey } from "@/lib/api"

const SKIP_KEY = "tasbir:apikey-prompt-skipped:v1"

/**
 * First-run prompt: the API requires x-api-key (fail-closed). Show the key
 * dialog until one is provided or explicitly dismissed.
 */
export function ApiKeyPrompt() {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState("")

  useEffect(() => {
    if (getApiKey()) return
    try {
      if (localStorage.getItem(SKIP_KEY) === "1") return
    } catch {
      /* noop */
    }
    setOpen(true)
  }, [])

  function save() {
    const trimmed = value.trim()
    if (trimmed) {
      setApiKey(trimmed)
      setOpen(false)
    }
  }

  function skip() {
    setOpen(false)
    try {
      localStorage.setItem(SKIP_KEY, "1")
    } catch {
      /* noop */
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && skip()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Set your API key</DialogTitle>
          <DialogDescription>
            The Tasbir API requires an <code>x-api-key</code>. Paste the key from
            <code> .env</code> (the <code>API_KEYS</code> value). You can change it
            anytime via the "API Key" button in the header.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="apikey-prompt">API key</Label>
          <Input
            id="apikey-prompt"
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="paste your API key"
            autoComplete="off"
            autoFocus
          />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={skip}>
            Skip for now
          </Button>
          <Button onClick={save} disabled={!value.trim()}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
