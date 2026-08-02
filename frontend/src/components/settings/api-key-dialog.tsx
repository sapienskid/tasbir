import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { KeyRound } from "lucide-react"
import { getApiKey, setApiKey, clearApiKey } from "@/lib/api"

export function ApiKeyDialog() {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState(() => getApiKey())
  const hasKey = Boolean(getApiKey())

  function save() {
    const trimmed = value.trim()
    if (trimmed) setApiKey(trimmed)
    else clearApiKey()
    setOpen(false)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={hasKey ? "outline" : "secondary"} size="sm">
          <KeyRound className="size-4" />
          API Key
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>API Key</DialogTitle>
          <DialogDescription>
            Stored locally in your browser and sent as <code>x-api-key</code> on every request.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          <Label htmlFor="api-key">Key</Label>
          <Input
            id="api-key"
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="paste your API key"
            autoComplete="off"
          />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={save}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
