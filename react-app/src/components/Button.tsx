import type { ButtonHTMLAttributes } from 'react'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'primary' | 'danger'
}

export default function Button({ variant = 'default', className, ...rest }: Props) {
  const v = variant === 'primary' ? 'btnPrimary' : variant === 'danger' ? 'btnDanger' : ''
  return <button {...rest} className={['btn', v, className].filter(Boolean).join(' ')} />
}
