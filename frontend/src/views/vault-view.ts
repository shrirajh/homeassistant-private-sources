import { LitElement, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import { ApiError, api, type VaultStatus } from "../api";
import { base, tokens } from "../styles";

@customElement("psm-vault-view")
export class VaultView extends LitElement {
  static styles = [tokens, base];

  @property({ attribute: false }) status!: VaultStatus;

  @state() private busy = false;
  @state() private error = "";
  @state() private notice = "";
  @state() private mode: "none" | "change" | "remove" = "none";

  render() {
    return html`
      ${this.error ? html`<div class="banner bad">${this.error}</div>` : nothing}
      ${this.notice ? html`<div class="banner ok">${this.notice}</div>` : nothing}
      ${this.status.passphrase_set ? this.renderConfigured() : this.renderSetup()}
      ${this.renderExplainer()}
    `;
  }

  private renderSetup() {
    return html`
      <div class="card">
        <h2>Set a passphrase</h2>
        <p class="hint">
          Optional. Credentials in the protected tier are encrypted with this passphrase, which is
          never written to disk. The vault locks on every add-on restart until you re-enter it.
        </p>
        <form @submit=${this.onCreate}>
          <label>
            <span>Passphrase, at least 10 characters</span>
            <input name="passphrase" type="password" autocomplete="new-password" required />
          </label>
          <label>
            <span>Confirm</span>
            <input name="confirm" type="password" autocomplete="new-password" required />
          </label>
          <div class="actions">
            <button class="primary" ?disabled=${this.busy} type="submit">
              ${this.busy ? "Calibrating…" : "Set passphrase"}
            </button>
          </div>
        </form>
      </div>
    `;
  }

  private renderConfigured() {
    const { unlocked, retry_after, failed_attempts, kdf_n } = this.status;
    return html`
      <div class="card">
        <div class="row">
          <h2 class="grow">Vault</h2>
          <span class="pill ${unlocked ? "ok" : "warn"}">${unlocked ? "unlocked" : "locked"}</span>
        </div>
        <p class="hint">
          ${unlocked
            ? "Protected credentials are available until the add-on restarts."
            : "Protected repositories cannot be reached until you unlock."}
        </p>

        ${unlocked ? this.renderUnlocked() : this.renderUnlock(retry_after, failed_attempts)}

        <dl style="margin-top:16px">
          <dt>Key derivation</dt>
          <dd>scrypt, cost ${kdf_n ?? "unknown"}</dd>
          <dt>Auto lock</dt>
          <dd>
            ${this.status.auto_lock_minutes > 0
              ? `after ${this.status.auto_lock_minutes} idle minutes`
              : "disabled"}
          </dd>
        </dl>
      </div>
      ${this.mode === "change" ? this.renderChange() : nothing}
      ${this.mode === "remove" ? this.renderRemove() : nothing}
    `;
  }

  private renderUnlock(retry: number, failed: number) {
    return html`
      <form @submit=${this.onUnlock}>
        <label>
          <span>Passphrase</span>
          <input name="passphrase" type="password" autocomplete="current-password" required />
        </label>
        ${retry > 0
          ? html`<div class="banner warn">
              ${failed} failed ${failed === 1 ? "attempt" : "attempts"}. Wait
              ${Math.ceil(retry)}s before trying again.
            </div>`
          : nothing}
        <div class="actions">
          <button class="primary" ?disabled=${this.busy || retry > 0} type="submit">Unlock</button>
        </div>
      </form>
    `;
  }

  private renderUnlocked() {
    return html`
      <div class="actions">
        <button @click=${this.onLock} ?disabled=${this.busy}>Lock now</button>
        <button @click=${() => (this.mode = this.mode === "change" ? "none" : "change")}>
          Change passphrase
        </button>
        <button class="danger" @click=${() => (this.mode = this.mode === "remove" ? "none" : "remove")}>
          Remove passphrase
        </button>
      </div>
    `;
  }

  private renderChange() {
    return html`
      <div class="card">
        <h3>Change passphrase</h3>
        <p class="hint">Secrets are re-wrapped, not re-encrypted, so this is quick.</p>
        <form @submit=${this.onChange}>
          <label><span>Current</span><input name="current" type="password" required /></label>
          <label><span>New</span><input name="next" type="password" required /></label>
          <div class="actions">
            <button class="primary" ?disabled=${this.busy} type="submit">Change</button>
            <button type="button" @click=${() => (this.mode = "none")}>Cancel</button>
          </div>
        </form>
      </div>
    `;
  }

  private renderRemove() {
    return html`
      <div class="card">
        <h3>Remove passphrase</h3>
        <div class="banner warn">
          Every protected credential moves down to the unattended tier, where it is protected only
          by a key file on disk. Background updates will keep working after a reboot.
        </div>
        <form @submit=${this.onRemove}>
          <label><span>Confirm with your passphrase</span><input name="passphrase" type="password" required /></label>
          <div class="actions">
            <button class="danger" ?disabled=${this.busy} type="submit">Remove passphrase</button>
            <button type="button" @click=${() => (this.mode = "none")}>Cancel</button>
          </div>
        </form>
      </div>
    `;
  }

  private renderExplainer() {
    return html`
      <div class="card">
        <h3>What the two tiers mean</h3>
        <dl style="margin-top:10px">
          <dt><span class="pill plain">unattended</span></dt>
          <dd>
            Encrypted with a key file on disk, excluded from Home Assistant backups. Survives
            reboots so updates run without you. Does not protect against someone with root access.
          </dd>
          <dt style="margin-top:8px"><span class="pill plain">protected</span></dt>
          <dd>
            Encrypted with your passphrase. Protects against a stolen device or backup. Unavailable
            until unlocked, so these repositories are skipped by background checks while locked.
          </dd>
        </dl>
      </div>
    `;
  }

  private async run(action: () => Promise<VaultStatus>, notice: string) {
    this.busy = true;
    this.error = "";
    this.notice = "";
    try {
      const status = await action();
      this.notice = notice;
      this.mode = "none";
      this.dispatchEvent(
        new CustomEvent("vault-changed", { detail: status, bubbles: true, composed: true }),
      );
    } catch (err) {
      this.error = err instanceof ApiError ? err.message : String(err);
      this.dispatchEvent(new CustomEvent("vault-refresh", { bubbles: true, composed: true }));
    } finally {
      this.busy = false;
    }
  }

  private onCreate(event: SubmitEvent) {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const data = new FormData(form);
    const passphrase = String(data.get("passphrase") ?? "");
    if (passphrase !== String(data.get("confirm") ?? "")) {
      this.error = "The two passphrases do not match";
      return;
    }
    void this.run(() => api.vault.setPassphrase(passphrase), "Passphrase set, vault unlocked");
  }

  private onUnlock(event: SubmitEvent) {
    event.preventDefault();
    const data = new FormData(event.target as HTMLFormElement);
    void this.run(() => api.vault.unlock(String(data.get("passphrase") ?? "")), "Vault unlocked");
  }

  private onLock() {
    void this.run(() => api.vault.lock(), "Vault locked");
  }

  private onChange(event: SubmitEvent) {
    event.preventDefault();
    const data = new FormData(event.target as HTMLFormElement);
    void this.run(
      () =>
        api.vault.change(String(data.get("current") ?? ""), String(data.get("next") ?? "")),
      "Passphrase changed",
    );
  }

  private onRemove(event: SubmitEvent) {
    event.preventDefault();
    const data = new FormData(event.target as HTMLFormElement);
    void this.run(
      () => api.vault.remove(String(data.get("passphrase") ?? "")),
      "Passphrase removed",
    );
  }
}
