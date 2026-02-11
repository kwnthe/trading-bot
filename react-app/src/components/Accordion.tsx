import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'

export default function Accordion(props: { title: ReactNode; defaultOpen?: boolean; right?: ReactNode; children: ReactNode }) {
  const [open, setOpen] = useState(Boolean(props.defaultOpen))
  const icon = useMemo(() => (open ? '–' : '+'), [open])

  return (
    <div className="panel">
      <button type="button" className="accordionBtn" onClick={() => setOpen((v) => !v)}>
        <span>{props.title}</span>
        <span className="row">
          {props.right ? <span className="pill">{props.right}</span> : null}
          <span className="kbd">{icon}</span>
        </span>
      </button>
      {open ? <div className="divider" /> : null}
      {open ? <div className="panelBody">{props.children}</div> : null}
    </div>
  )
}
