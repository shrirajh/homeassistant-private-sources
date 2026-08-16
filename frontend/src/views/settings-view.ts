import { LitElement, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import { ApiError, api, type HostKey, type Info } from "../api";
import { base, tokens } from "../styles";

@customElement("psm-settings-view")
export class SettingsView extends LitElement {
  static styles = [tokens, base];

  @property({ attribute: false }) info?: Info;

  @state() private busy = false;
  @state() private error = "";
  @state() private notice = "";
  @state() private scanned: HostKey[] = [];
  @state() private scannedHost = "";

  render() {
    return html`
      ${this.error ? html`<div class="banner bad">${this.error}</div>` : nothing}
      ${this.notice ? html`<div class="banner ok">${this.notice}</div>` : nothing}

      <div class="card">
        <h2>Trust a git host</h2>
        <p class="hint">
          GitHub and GitLab are trusted out of the box. Any other ssh host has to be confirmed
          once. Check the fingerprint against what the server operator publishes before accepting.
        </p>
        <form @submit=${this.onScan}>
          <div class="grid2">
            <label><span>Host</span><input name="host" required placeholder="gitea.lan" /></label>
            <label><span>Port</span><input name="port" type="number" value="22" /></label>
          </div>
          <div class="actions">
            <button class="primary" ?disabled=${this.busy} type="submit">Scan</button>
          </div>
        </form>

        ${this.scanned.length
          ? html`
              <div style="margin-top:16px">
                <h3>${this.scannedHost} offered these keys</h3>
                <dl style="margin-top:10px">
                  ${this.scanned.map(
                    (key) => html`<dt>${key.type}</dt>
                      <dd class="mono">${key.fingerprint}</dd>`,
                  )}
                </dl>
                <div class="actions">
                  <button class="primary" ?disabled=${this.busy} @click=${this.onTrust}>
                    Trust these keys
                  </button>
                  <button @click=${() => (this.scanned = [])}>Discard</button>
                </div>
              </div>
            `
          : nothing}
      </div>

      <div class="card">
        <h2>Home Assistant</h2>
        <p class="hint">
          Newly installed integrations only load after a restart. Lovelace cards and themes do not
          need one.
        </p>
        <div class="actions">
          <button
            class="danger"
            ?disabled=${this.busy || !this.info?.supervisor}
            @click=${this.onRestart}
          >
            Restart Home Assistant
          </button>
        </div>
        ${!this.info?.supervisor
          ? html`<div class="banner warn" style="margin-top:12px">
              No Supervisor connection, so Core actions are unavailable. This is expected when
              running outside Home Assistant.
            </div>`
          : nothing}
      </div>

      <div class="card">
        <h2>About</h2>
        <dl style="margin-top:10px">
          <dt>Version</dt>
          <dd>${this.info?.version ?? "unknown"}</dd>
          <dt>Supervisor</dt>
          <dd>${this.info?.supervisor ? "connected" : "not available"}</dd>
          ${this.info?.dev_mode ? html`<dt>Mode</dt><dd>development</dd>` : nothing}
        </dl>
      </div>
    `;
  }

  private async run(action: () => Promise<void>) {
    this.busy = true;
    this.error = "";
    this.notice = "";
    try {
      await action();
    } catch (err) {
      this.error = err instanceof ApiError ? err.message : String(err);
    } finally {
      this.busy = false;
    }
  }

  private onScan(event: SubmitEvent) {
    event.preventDefault();
    const data = new FormData(event.target as HTMLFormElement);
    const host = String(data.get("host") ?? "").trim();
    const port = Number(data.get("port") ?? 22);
    void this.run(async () => {
      const result = await api.hosts.scan(host, port);
      this.scanned = result.keys;
      this.scannedHost = `${result.host}:${result.port}`;
    });
  }

  private onTrust() {
    void this.run(async () => {
      const result = await api.hosts.trust(this.scanned.map((k) => k.line));
      this.notice = `Added ${result.added} host ${result.added === 1 ? "key" : "keys"}`;
      this.scanned = [];
    });
  }

  private onRestart() {
    void this.run(async () => {
      await api.core.restart();
      this.notice = "Restart requested. Home Assistant will be unreachable for a moment.";
    });
  }
}
