import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Plus } from "lucide-react"
import { toast } from "sonner"
import { apiRequest, type GenerateResponse } from "@/lib/api"

const KNOWN_PLATFORMS = [
  "instagram-square",
  "instagram-portrait",
  "instagram-story",
  "linkedin-post",
  "twitter-card",
  "facebook-post",
  "pinterest-pin",
]

const CAMPAIGNS = ["default", "educational", "thought-leadership"]

export function NewTaskDialog() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")
  const [category, setCategory] = useState("")
  const [campaign, setCampaign] = useState("default")
  const [platforms, setPlatforms] = useState<string[]>(["instagram-square"])

  function togglePlatform(p: string, checked: boolean) {
    setPlatforms((prev) => (checked ? [...prev, p] : prev.filter((x) => x !== p)))
  }

  async function submit() {
    if (!content.trim()) {
      toast.error("Content is required")
      return
    }
    setSubmitting(true)
    try {
      const res = await apiRequest<GenerateResponse>("/generate", {
        method: "POST",
        body: JSON.stringify({
          content,
          title,
          category: category || undefined,
          campaign,
          platforms,
        }),
      })
      toast.success("Task queued")
      setOpen(false)
      navigate(`/tasks/${res.task_id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to queue task")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="size-4" />
          New Task
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New Generation Task</DialogTitle>
          <DialogDescription>Post content in, platform graphics out.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="nt-title">Title</Label>
            <Input
              id="nt-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Article title"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="nt-content">Content</Label>
            <Textarea
              id="nt-content"
              className="min-h-40"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Paste the full article / blog post..."
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="nt-category">Category</Label>
              <Input
                id="nt-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="WRITING (optional)"
              />
            </div>
            <div className="grid gap-2">
              <Label>Campaign</Label>
              <Select value={campaign} onValueChange={setCampaign}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CAMPAIGNS.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-2">
            <Label>Platforms</Label>
            <div className="grid grid-cols-2 gap-2">
              {KNOWN_PLATFORMS.map((p) => (
                <div key={p} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    id={`nt-${p}`}
                    checked={platforms.includes(p)}
                    onCheckedChange={(c) => togglePlatform(p, c === true)}
                  />
                  <Label htmlFor={`nt-${p}`} className="font-normal">
                    {p}
                  </Label>
                </div>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={submitting}>
            {submitting ? "Queuing..." : "Generate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
