import type { ReactNode } from 'react'

export default function Card(props: { title?: ReactNode; right?: ReactNode; children?: ReactNode; className?: string }) {
  return (
    <div className={`panel ${props.className || ''}`.trim()}>
      {props.title || props.right ? (
        <div className="panelHeader">
          <div>{props.title || null}</div>
          <div className="row">{props.right || null}</div>
        </div>
      ) : null}
      <div className="panelBody">{props.children}</div>
    </div>
  )
}
