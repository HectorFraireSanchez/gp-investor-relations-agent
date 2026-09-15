// Radix Dialog handles focus, Escape, and dismissal for the source drawer.
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ComponentProps } from 'react'

export const Sheet = Dialog.Root
export const SheetTitle = Dialog.Title
export const SheetDescription = Dialog.Description

export function SheetContent({ children, ...props }: ComponentProps<typeof Dialog.Content>) {
  return <Dialog.Portal>
    <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/25 backdrop-blur-[2px]" />
    <Dialog.Content className="source-sheet fixed inset-y-0 right-0 z-50 w-full overflow-y-auto bg-white p-7 shadow-2xl sm:max-w-md sm:p-9" {...props}>
      {children}
      <Dialog.Close className="icon-button absolute right-5 top-5" aria-label="Close source details">
        <X size={20} aria-hidden="true" />
      </Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal>
}
