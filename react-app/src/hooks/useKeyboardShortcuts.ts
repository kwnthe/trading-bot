import { useEffect } from 'react'

interface KeyboardShortcut {
  key: string
  action: () => void
  preventDefault?: boolean
}

interface UseKeyboardShortcutsConfig {
  shortcuts: KeyboardShortcut[]
  ignoreInputs?: boolean
}

export function useKeyboardShortcuts({ shortcuts, ignoreInputs = true }: UseKeyboardShortcutsConfig) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input, textarea, or select (when ignoreInputs is true)
      if (ignoreInputs) {
        const target = e.target as HTMLElement
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') {
          return
        }
      }
      
      // Ignore if modifier keys are pressed
      if (e.ctrlKey || e.metaKey || e.altKey) {
        return
      }

      // Find matching shortcut
      const shortcut = shortcuts.find(s => 
        s.key.toLowerCase() === e.key.toLowerCase() || 
        s.key === e.key
      )

      if (shortcut) {
        if (shortcut.preventDefault !== false) {
          e.preventDefault()
        }
        shortcut.action()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [shortcuts, ignoreInputs])
}
