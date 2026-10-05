import { useState, type ReactNode } from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"

interface ConfirmActionProps {
  /** The destructive control that opens the dialog. */
  trigger: ReactNode
  title: string
  /** Inline content only — it renders inside a paragraph. */
  description: ReactNode
  confirmLabel?: string
  onConfirm: () => void | Promise<void>
  disabled?: boolean
}

/** A destructive action behind an explicit confirmation.
 *
 *  Settings rows (platforms, fonts) used to delete on click, which is far too
 *  easy to do by accident — and deleting a platform silently changes the
 *  render size of every format in that family. */
export function ConfirmAction({
  trigger,
  title,
  description,
  confirmLabel = "Delete",
  onConfirm,
  disabled,
}: ConfirmActionProps) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild disabled={disabled}>
        {trigger}
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={busy}
            onClick={(e) => {
              // Keep the dialog open while the request runs so a failure stays
              // visible instead of silently dismissing.
              e.preventDefault()
              void (async () => {
                setBusy(true)
                try {
                  await onConfirm()
                  setOpen(false)
                } finally {
                  setBusy(false)
                }
              })()
            }}
          >
            {busy ? "Working…" : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
