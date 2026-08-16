import { css } from "lit";

// Home Assistant's custom properties, which the app applies to the root element at
// startup because nothing cascades into the ingress iframe on its own. The fallbacks
// are Home Assistant's own default light and dark values, so an unthemed install still
// matches rather than merely looking similar.
export const tokens = css`
  :host {
    --psm-bg: var(--primary-background-color, #fafafa);
    --psm-card: var(--card-background-color, #ffffff);
    --psm-fg: var(--primary-text-color, #212121);
    --psm-muted: var(--secondary-text-color, #727272);
    --psm-line: var(--divider-color, rgba(0, 0, 0, 0.12));
    --psm-accent: var(--primary-color, #03a9f4);
    --psm-ok: var(--success-color, #43a047);
    --psm-warn: var(--warning-color, #ffa600);
    --psm-bad: var(--error-color, #db4437);
    --psm-radius: 12px;
  }

  @media (prefers-color-scheme: dark) {
    :host {
      --psm-bg: var(--primary-background-color, #111111);
      --psm-card: var(--card-background-color, #1c1c1c);
      --psm-fg: var(--primary-text-color, #e1e1e1);
      --psm-muted: var(--secondary-text-color, #9b9b9b);
      --psm-line: var(--divider-color, rgba(225, 225, 225, 0.12));
    }
  }
`;

export const base = css`
  * {
    box-sizing: border-box;
  }

  .card {
    background: var(--psm-card);
    border: 1px solid var(--psm-line);
    border-radius: var(--psm-radius);
    padding: 16px 20px;
    margin-bottom: 12px;
  }

  h2 {
    margin: 0 0 4px;
    font-size: 18px;
    font-weight: 600;
  }

  h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }

  p.hint {
    margin: 0 0 16px;
    color: var(--psm-muted);
    font-size: 13px;
  }

  button {
    font: inherit;
    font-size: 13px;
    padding: 7px 14px;
    border-radius: 8px;
    border: 1px solid var(--psm-line);
    background: transparent;
    color: var(--psm-fg);
    cursor: pointer;
    transition: background 120ms ease, border-color 120ms ease;
  }
  button:hover:not(:disabled) {
    border-color: var(--psm-accent);
  }
  button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  button.primary {
    background: var(--psm-accent);
    border-color: var(--psm-accent);
    color: #fff;
  }
  button.danger {
    color: var(--psm-bad);
    border-color: color-mix(in srgb, var(--psm-bad) 40%, transparent);
  }
  button.danger:hover:not(:disabled) {
    border-color: var(--psm-bad);
  }

  input,
  select,
  textarea {
    font: inherit;
    font-size: 13px;
    width: 100%;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--psm-line);
    background: var(--psm-bg);
    color: var(--psm-fg);
  }
  input:focus,
  select:focus,
  textarea:focus {
    outline: 2px solid color-mix(in srgb, var(--psm-accent) 45%, transparent);
    outline-offset: -1px;
  }
  textarea {
    min-height: 110px;
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
    resize: vertical;
  }

  label {
    display: block;
    margin-bottom: 12px;
    font-size: 12px;
    color: var(--psm-muted);
  }
  label > span {
    display: block;
    margin-bottom: 5px;
  }
  label.inline {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--psm-fg);
  }
  label.inline input {
    width: auto;
  }

  .row {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  .grow {
    flex: 1;
    min-width: 0;
  }
  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 12px;
  }
  .grid2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0 16px;
  }

  .pill {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }
  .pill.ok {
    background: color-mix(in srgb, var(--psm-ok) 18%, transparent);
    color: var(--psm-ok);
  }
  .pill.warn {
    background: color-mix(in srgb, var(--psm-warn) 20%, transparent);
    color: var(--psm-warn);
  }
  .pill.bad {
    background: color-mix(in srgb, var(--psm-bad) 18%, transparent);
    color: var(--psm-bad);
  }
  .pill.plain {
    background: color-mix(in srgb, var(--psm-muted) 16%, transparent);
    color: var(--psm-muted);
  }

  code,
  .mono {
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
    font-size: 12px;
    word-break: break-all;
  }

  .banner {
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 13px;
    margin-bottom: 12px;
  }
  .banner.bad {
    background: color-mix(in srgb, var(--psm-bad) 12%, transparent);
    color: var(--psm-bad);
  }
  .banner.ok {
    background: color-mix(in srgb, var(--psm-ok) 12%, transparent);
    color: var(--psm-ok);
  }
  .banner.warn {
    background: color-mix(in srgb, var(--psm-warn) 14%, transparent);
    color: var(--psm-warn);
  }

  .empty {
    text-align: center;
    color: var(--psm-muted);
    padding: 36px 12px;
    font-size: 14px;
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 4px 14px;
    margin: 0;
    font-size: 13px;
  }
  dt {
    color: var(--psm-muted);
  }
  dd {
    margin: 0;
  }
`;
