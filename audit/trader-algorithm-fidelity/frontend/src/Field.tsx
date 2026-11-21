import type { ReactNode } from 'react';

type Props = {
  label: string;
  hint: string;
  htmlFor?: string;
  wide?: boolean;
  children: ReactNode;
};

/** A labeled form field with a visible "?" affordance carrying the explanatory
 * tooltip, so the hint is discoverable instead of a silent `title` attribute. */
export function Field({ label, hint, htmlFor, wide, children }: Props) {
  return <label className={`field${wide ? ' field-wide' : ''}`} htmlFor={htmlFor}>
    <span className="field-label">
      {label}
      <span className="field-hint" tabIndex={0} title={hint} aria-label={hint} role="note">?</span>
    </span>
    {children}
  </label>;
}
