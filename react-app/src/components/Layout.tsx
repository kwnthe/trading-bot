import type { ReactNode } from 'react'

export default function Layout(props: { title: string; subtitle?: string; right?: ReactNode; children: ReactNode }) {
  return (
    <div className="container">
      <div className="appHeader">
        <div>
          <div className="title">{props.title}</div>
          {props.subtitle ? <div className="subtitle">{props.subtitle}</div> : null}
        </div>
        {props.right ? <div className="row">{props.right}</div> : null}
      </div>
      {props.children}
    </div>
  )
}
