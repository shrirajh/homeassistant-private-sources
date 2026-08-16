import { LitElement, css, html, nothing } from "lit";
import { customElement, state } from "lit/decorators.js";
import { ApiError, api, type Credential, type Info, type VaultStatus } from "./api";
import { base, tokens } from "./styles";
import "./views/credentials-view";
import "./views/repos-view";
import "./views/settings-view";
import "./views/vault-view";

type Tab = "repos" | "credentials" | "vault" | "settings";

const TABS: [Tab, string][] = [
  ["repos", "Repositories"],
  ["credentials", "Credentials"],
  ["vault", "Vault"],
  ["settings", "Settings"],
];

const shell = css`
  :host {
    display: block;
    min-height: 100vh;
    background: var(--psm-bg);
    color: var(--psm-fg);
    font: 14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  .page {
    max-width: 940px;
    margin: 0 auto;
    padding: 20px 16px 48px;
  }
  h1 {
    margin: 0 0 14px;
    font-size: 22px;
    font-weight: 600;
  }
  nav {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--psm-line);
    margin-bottom: 16px;
  }
  button.tab {
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 9px 14px;
    color: var(--psm-muted);
    display: inline-flex;
    align-items: center;
    gap: 7px;
  }
  button.tab:hover {
    color: var(--psm-fg);
  }
  button.tab.active {
    color: var(--psm-accent);
    border-bottom-color: var(--psm-accent);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    display: inline-block;
  }
  .dot.ok {
    background: var(--psm-ok);
  }
  .dot.warn {
    background: var(--psm-warn);
  }
`;

@customElement("psm-app")
export class App extends LitElement {
  static styles = [tokens, base, shell];

  @state() private tab: Tab = "repos";
  @state() private status?: VaultStatus;
  @state() private info?: Info;
  @state() private credentials: Credential[] = [];
  @state() private fatal = "";

  connectedCallback() {
    super.connectedCallback();
    void this.bootstrap();
    this.addEventListener("vault-changed", (event) => {
      this.status = (event as CustomEvent<VaultStatus>).detail;
      void this.loadCredentials();
    });
    this.addEventListener("vault-refresh", () => void this.loadStatus());
    this.addEventListener("credentials-changed", () => void this.loadCredentials());
  }

  render() {
    if (this.fatal) {
      return html`<div class="page"><div class="banner bad">${this.fatal}</div></div>`;
    }
    if (!this.status) {
      return html`<div class="page"><div class="empty">Loading…</div></div>`;
    }

    const locked = this.status.passphrase_set && !this.status.unlocked;
    return html`
      <div class="page">
        <h1>Private Sources</h1>
        <nav>
          ${TABS.map(
            ([id, label]) => html`
              <button class="tab ${this.tab === id ? "active" : ""}" @click=${() => (this.tab = id)}>
                ${label}
                ${id === "vault" && this.status?.passphrase_set
                  ? html`<span class="dot ${this.status.unlocked ? "ok" : "warn"}"></span>`
                  : nothing}
              </button>
            `,
          )}
        </nav>

        ${locked && this.tab !== "vault"
          ? html`<div class="banner warn">
              The vault is locked. Protected repositories cannot be reached until you unlock it on
              the Vault tab.
            </div>`
          : nothing}

        <main>${this.renderTab()}</main>
      </div>
    `;
  }

  private renderTab() {
    const status = this.status!;
    switch (this.tab) {
      case "vault":
        return html`<psm-vault-view .status=${status}></psm-vault-view>`;
      case "credentials":
        return html`<psm-credentials-view .status=${status}></psm-credentials-view>`;
      case "settings":
        return html`<psm-settings-view .info=${this.info}></psm-settings-view>`;
      default:
        return html`<psm-repos-view
          .status=${status}
          .credentials=${this.credentials}
        ></psm-repos-view>`;
    }
  }

  private async bootstrap() {
    try {
      const [info, status] = await Promise.all([api.info(), api.vault.status()]);
      this.info = info;
      this.status = status;
      await this.loadCredentials();
    } catch (err) {
      this.fatal = err instanceof ApiError ? err.message : String(err);
    }
  }

  private async loadStatus() {
    try {
      this.status = await api.vault.status();
    } catch {
      /* the active view surfaces its own failure */
    }
  }

  private async loadCredentials() {
    try {
      this.credentials = await api.credentials.list();
    } catch {
      this.credentials = [];
    }
  }
}
