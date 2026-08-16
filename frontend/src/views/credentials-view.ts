import { LitElement, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import { ApiError, api, type Credential, type Tier, type VaultStatus } from "../api";
import { base, tokens } from "../styles";

@customElement("psm-credentials-view")
export class CredentialsView extends LitElement {
  static styles = [tokens, base];

  @property({ attribute: false }) status!: VaultStatus;

  @state() private items: Credential[] = [];
  @state() private busy = false;
  @state() private error = "";
  @state() private notice = "";
  @state() private adding = false;
  @state() private kind: "ssh" | "token" = "ssh";
  @state() private importing = false;
  @state() private copied = "";

  connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  async load() {
    try {
      this.items = await api.credentials.list();
    } catch (err) {
      this.error = err instanceof ApiError ? err.message : String(err);
    }
  }

  render() {
    return html`
      ${this.error ? html`<div class="banner bad">${this.error}</div>` : nothing}
      ${this.notice ? html`<div class="banner ok">${this.notice}</div>` : nothing}

      <div class="card">
        <div class="row">
          <div class="grow">
            <h2>Credentials</h2>
            <p class="hint" style="margin:0">
              One credential per repository keeps the blast radius of a leak to a single repository.
            </p>
          </div>
          <button class="primary" @click=${() => (this.adding = !this.adding)}>
            ${this.adding ? "Cancel" : "Add credential"}
          </button>
        </div>
      </div>

      ${this.adding ? this.renderForm() : nothing}
      ${this.items.length === 0 && !this.adding
        ? html`<div class="card"><div class="empty">No credentials yet.</div></div>`
        : this.items.map((item) => this.renderCredential(item))}
    `;
  }

  private renderForm() {
    return html`
      <div class="card">
        <h3>New credential</h3>
        <div class="actions" style="margin:12px 0">
          <button class=${this.kind === "ssh" ? "primary" : ""} @click=${() => (this.kind = "ssh")}>
            SSH deploy key
          </button>
          <button
            class=${this.kind === "token" ? "primary" : ""}
            @click=${() => (this.kind = "token")}
          >
            Access token
          </button>
        </div>

        <form @submit=${this.onCreate}>
          <div class="grid2">
            <label>
              <span>Label</span>
              <input name="label" required placeholder="my-private-card" />
            </label>
            <label>
              <span>Tier</span>
              <select name="tier">
                <option value="unattended">unattended, updates without you</option>
                <option value="protected" ?disabled=${!this.status.passphrase_set}>
                  protected, needs the passphrase
                </option>
              </select>
            </label>
          </div>

          ${this.kind === "ssh" ? this.renderSshFields() : this.renderTokenFields()}

          <div class="actions">
            <button class="primary" ?disabled=${this.busy} type="submit">
              ${this.busy ? "Working…" : this.kind === "ssh" && !this.importing ? "Generate key" : "Save"}
            </button>
          </div>
        </form>
      </div>
    `;
  }

  private renderSshFields() {
    return html`
      <label class="inline" style="margin-bottom:12px">
        <input
          type="checkbox"
          .checked=${this.importing}
          @change=${(e: Event) => (this.importing = (e.target as HTMLInputElement).checked)}
        />
        Paste an existing private key instead of generating one
      </label>
      ${this.importing
        ? html`<label>
            <span>Private key, unencrypted OpenSSH or PEM</span>
            <textarea name="private_key" required placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"></textarea>
          </label>`
        : html`<p class="hint">
            A fresh Ed25519 key is generated. Copy the public half into the repository's deploy keys.
          </p>`}
    `;
  }

  private renderTokenFields() {
    return html`
      <div class="grid2">
        <label>
          <span>Token</span>
          <input name="token" type="password" required placeholder="github_pat_… or glpat-…" />
        </label>
        <label>
          <span>Username, optional</span>
          <input name="username" placeholder="x-access-token" />
        </label>
      </div>
    `;
  }

  private renderCredential(item: Credential) {
    const locked = item.tier === "protected" && !this.status.unlocked;
    return html`
      <div class="card">
        <div class="row">
          <h3 class="grow">${item.label}</h3>
          <span class="pill plain">${item.kind}</span>
          <span class="pill ${item.tier === "protected" ? "warn" : "plain"}">${item.tier}</span>
          ${locked ? html`<span class="pill bad">locked</span>` : nothing}
        </div>

        <dl style="margin-top:10px">
          ${item.fingerprint
            ? html`<dt>Fingerprint</dt>
                <dd class="mono">${item.fingerprint}</dd>`
            : nothing}
          ${item.username ? html`<dt>Username</dt><dd>${item.username}</dd>` : nothing}
          <dt>Used by</dt>
          <dd>${item.repo_count} ${item.repo_count === 1 ? "repository" : "repositories"}</dd>
        </dl>

        ${item.public_key
          ? html`
              <label style="margin-top:12px">
                <span>Public key, paste this into the deploy keys of the repository</span>
                <textarea readonly style="min-height:72px">${item.public_key}</textarea>
              </label>
              <button @click=${() => this.copy(item)}>
                ${this.copied === item.id ? "Copied" : "Copy public key"}
              </button>
            `
          : nothing}

        <div class="actions">
          ${item.kind === "ssh"
            ? html`<button ?disabled=${this.busy || locked} @click=${() => this.rotate(item)}>
                Rotate key
              </button>`
            : nothing}
          <button
            ?disabled=${this.busy || !this.status.passphrase_set || !this.status.unlocked}
            @click=${() => this.move(item)}
            title=${!this.status.passphrase_set ? "Set a passphrase first" : ""}
          >
            Move to ${item.tier === "protected" ? "unattended" : "protected"}
          </button>
          <button class="danger" ?disabled=${this.busy || item.repo_count > 0} @click=${() => this.deleteCredential(item)}>
            Delete
          </button>
        </div>
      </div>
    `;
  }

  private async copy(item: Credential) {
    try {
      await navigator.clipboard.writeText(item.public_key ?? "");
      this.copied = item.id;
      setTimeout(() => (this.copied = ""), 2000);
    } catch {
      this.error = "Clipboard access was refused, select the text manually";
    }
  }

  private async act(action: () => Promise<unknown>, notice: string) {
    this.busy = true;
    this.error = "";
    this.notice = "";
    try {
      await action();
      this.notice = notice;
      await this.load();
      this.dispatchEvent(new CustomEvent("credentials-changed", { bubbles: true, composed: true }));
    } catch (err) {
      this.error = err instanceof ApiError ? err.message : String(err);
    } finally {
      this.busy = false;
    }
  }

  private onCreate(event: SubmitEvent) {
    event.preventDefault();
    const data = new FormData(event.target as HTMLFormElement);
    const payload: Record<string, unknown> = {
      kind: this.kind,
      label: String(data.get("label") ?? ""),
      tier: String(data.get("tier") ?? "unattended"),
    };
    if (this.kind === "ssh" && this.importing) {
      payload.private_key = String(data.get("private_key") ?? "");
    }
    if (this.kind === "token") {
      payload.token = String(data.get("token") ?? "");
      const username = String(data.get("username") ?? "").trim();
      if (username) payload.username = username;
    }
    void this.act(async () => {
      await api.credentials.create(payload);
      this.adding = false;
    }, "Credential created");
  }

  private rotate(item: Credential) {
    void this.act(() => api.credentials.rotate(item.id), "New key generated, update the deploy key");
  }

  private move(item: Credential) {
    const tier: Tier = item.tier === "protected" ? "unattended" : "protected";
    void this.act(() => api.credentials.setTier(item.id, tier), `Moved to the ${tier} tier`);
  }

  private deleteCredential(item: Credential) {
    void this.act(() => api.credentials.remove(item.id), "Credential deleted");
  }
}
