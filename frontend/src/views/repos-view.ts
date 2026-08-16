import { LitElement, html, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import { ApiError, api, type Credential, type GitRef, type Repo, type VaultStatus } from "../api";
import { base, tokens } from "../styles";

const CATEGORIES = [
  ["", "detect automatically"],
  ["integration", "integration"],
  ["plugin", "Lovelace card"],
  ["theme", "theme"],
  ["python_script", "python script"],
  ["appdaemon", "AppDaemon app"],
  ["addon", "Home Assistant add-on"],
];

function describeTracking(repo: Repo): string {
  if (repo.ref_kind === "branch") {
    return `rolling, branch ${repo.pinned_ref ?? "default"}`;
  }
  return repo.pinned_ref ? `pinned to ${repo.pinned_ref}` : "newest tag";
}

@customElement("psm-repos-view")
export class ReposView extends LitElement {
  static styles = [tokens, base];

  @property({ attribute: false }) status!: VaultStatus;
  @property({ attribute: false }) credentials: Credential[] = [];

  @state() private items: Repo[] = [];
  @state() private busy = "";
  @state() private error = "";
  @state() private notice = "";
  @state() private adding = false;
  @state() private expanded = "";
  @state() private refs: Record<string, GitRef[]> = {};

  connectedCallback() {
    super.connectedCallback();
    void this.load();
  }

  async load() {
    try {
      this.items = await api.repos.list();
    } catch (err) {
      this.error = err instanceof ApiError ? err.message : String(err);
    }
  }

  render() {
    const updates = this.items.filter((r) => r.update_available).length;
    return html`
      ${this.error ? html`<div class="banner bad">${this.error}</div>` : nothing}
      ${this.notice ? html`<div class="banner ok">${this.notice}</div>` : nothing}

      <div class="card">
        <div class="row">
          <div class="grow">
            <h2>Repositories</h2>
            <p class="hint" style="margin:0">
              ${this.items.length} tracked${updates ? `, ${updates} with updates available` : ""}
            </p>
          </div>
          <button ?disabled=${this.busy !== ""} @click=${this.checkAll}>Check for updates</button>
          <button class="primary" @click=${() => (this.adding = !this.adding)}>
            ${this.adding ? "Cancel" : "Add repository"}
          </button>
        </div>
      </div>

      ${this.adding ? this.renderAdd() : nothing}
      ${this.items.length === 0 && !this.adding
        ? html`<div class="card"><div class="empty">Nothing tracked yet.</div></div>`
        : this.items.map((repo) => this.renderRepo(repo))}
    `;
  }

  private renderAdd() {
    return html`
      <div class="card">
        <h3>Add repository</h3>
        <p class="hint">
          Any git URL. Use an ssh URL with a deploy key, or an https URL with a token.
        </p>
        <form @submit=${this.onAdd}>
          <label>
            <span>Repository URL</span>
            <input name="url" required placeholder="git@github.com:me/my-private-card.git" />
          </label>
          <div class="grid2">
            <label>
              <span>Credential</span>
              <select name="credential_id">
                <option value="">none, public repository</option>
                ${this.credentials.map(
                  (c) => html`<option value=${c.id}>${c.label} (${c.kind}, ${c.tier})</option>`,
                )}
              </select>
            </label>
            <label>
              <span>Category</span>
              <select name="category">
                ${CATEGORIES.map(([value, text]) => html`<option value=${value}>${text}</option>`)}
              </select>
            </label>
            <label>
              <span>Release channel</span>
              <select name="ref_kind">
                <option value="tag">newest tag</option>
                <option value="branch">rolling, follow a branch</option>
              </select>
            </label>
            <label>
              <span>Branch or tag, optional</span>
              <input name="pinned_ref" placeholder="leave empty for newest tag or default branch" />
            </label>
          </div>
          <label class="inline" style="margin-bottom:12px">
            <input type="checkbox" name="auto_update" />
            Install updates automatically
          </label>
          <div class="actions">
            <button class="primary" ?disabled=${this.busy !== ""} type="submit">
              ${this.busy === "add" ? "Cloning…" : "Add"}
            </button>
          </div>
        </form>
      </div>
    `;
  }

  private renderRepo(repo: Repo) {
    const open = this.expanded === repo.id;
    const working = this.busy === repo.id;
    return html`
      <div class="card">
        <div class="row">
          <div class="grow">
            <h3>${repo.slug}</h3>
              <div class="hint" style="margin:2px 0 0">
              ${repo.host} · ${repo.category}
              ${repo.ref_kind === "branch" ? html`· <span class="pill plain">rolling</span>` : nothing}
            </div>
          </div>
          ${repo.update_available
            ? html`<span class="pill warn">update ${repo.available_version}</span>`
            : nothing}
          <span class="pill ${repo.installed ? "ok" : "plain"}">
            ${repo.installed ? (repo.installed_version ?? "installed") : "not installed"}
          </span>
        </div>

        ${repo.last_error ? html`<div class="banner bad" style="margin-top:10px">${repo.last_error}</div>` : nothing}

        <div class="actions">
          <button
            class=${repo.update_available || !repo.installed ? "primary" : ""}
            ?disabled=${working}
            @click=${() => this.install(repo)}
          >
            ${working ? "Working…" : repo.installed ? "Update" : "Install"}
          </button>
          <button ?disabled=${working} @click=${() => this.refresh(repo)}>Check</button>
          <button ?disabled=${working} @click=${() => this.toggle(repo)}>
            ${open ? "Hide" : "Details"}
          </button>
          ${repo.installed
            ? html`<button ?disabled=${working} @click=${() => this.uninstall(repo)}>Uninstall</button>`
            : nothing}
          <button class="danger" ?disabled=${working} @click=${() => this.deleteRepo(repo)}>Remove</button>
        </div>

        ${open ? this.renderDetails(repo) : nothing}
      </div>
    `;
  }

  private renderDetails(repo: Repo) {
    const refs = this.refs[repo.id] ?? [];
    const branches = refs.filter((r) => r.kind === "branch");
    const rolling = repo.ref_kind === "branch";

    return html`
      <div style="margin-top:16px; border-top:1px solid var(--psm-line); padding-top:14px">
        <dl>
          <dt>URL</dt><dd class="mono">${repo.url}</dd>
          <dt>Tracking</dt><dd>${describeTracking(repo)}</dd>
          <dt>Installed ref</dt><dd class="mono">${repo.installed_ref?.slice(0, 12) ?? "none"}</dd>
          <dt>Last checked</dt><dd>${repo.last_checked ?? "never"}</dd>
        </dl>

        <div class="grid2" style="margin-top:14px">
          <label>
            <span>Credential</span>
            <select @change=${(e: Event) => this.patch(repo, { credential_id: (e.target as HTMLSelectElement).value })}>
              <option value="" ?selected=${!repo.credential_id}>none</option>
              ${this.credentials.map(
                (c) => html`<option value=${c.id} ?selected=${c.id === repo.credential_id}>
                  ${c.label}
                </option>`,
              )}
            </select>
          </label>

          <label>
            <span>Release channel</span>
            <select
              @change=${(e: Event) =>
                this.patch(repo, {
                  ref_kind: (e.target as HTMLSelectElement).value,
                  clear_pin: true,
                })}
            >
              <option value="tag" ?selected=${!rolling}>newest tag</option>
              <option value="branch" ?selected=${rolling}>rolling, follow a branch</option>
            </select>
          </label>

          ${rolling
            ? html`<label>
                <span>Branch to follow</span>
                <select
                  @change=${(e: Event) =>
                    this.patch(repo, { pinned_ref: (e.target as HTMLSelectElement).value })}
                >
                  <option value="">default branch</option>
                  ${branches.map(
                    (r) => html`<option value=${r.name} ?selected=${r.name === repo.pinned_ref}>
                      ${r.name}
                    </option>`,
                  )}
                </select>
              </label>`
            : html`<label>
                <span>Pin to a tag</span>
                <select
                  @change=${(e: Event) => {
                    const value = (e.target as HTMLSelectElement).value;
                    this.patch(repo, value ? { pinned_ref: value } : { clear_pin: true });
                  }}
                >
                  <option value="" ?selected=${!repo.pinned_ref}>track the newest</option>
                  ${refs
                    .filter((r) => r.kind === "tag")
                    .map(
                      (r) => html`<option value=${r.name} ?selected=${r.name === repo.pinned_ref}>
                        ${r.name}
                      </option>`,
                    )}
                </select>
              </label>`}

          <label>
            <span>Install a specific ref now</span>
            <select @change=${(e: Event) => this.install(repo, (e.target as HTMLSelectElement).value)}>
              <option value="">choose a ref…</option>
              ${refs.map((r) => html`<option value=${r.name}>${r.name} (${r.kind})</option>`)}
            </select>
          </label>
        </div>

        <label class="inline">
          <input
            type="checkbox"
            .checked=${repo.auto_update}
            @change=${(e: Event) =>
              this.patch(repo, { auto_update: (e.target as HTMLInputElement).checked })}
          />
          Install updates automatically
        </label>
        ${rolling
          ? html`<p class="hint" style="margin:4px 0 0">
              A rolling repository updates whenever the branch moves, so the version shown is
              the branch and its head commit.
            </p>`
          : nothing}
      </div>
    `;
  }

  private async act(id: string, action: () => Promise<unknown>, notice: string) {
    this.busy = id;
    this.error = "";
    this.notice = "";
    try {
      await action();
      this.notice = notice;
      await this.load();
    } catch (err) {
      this.error = err instanceof ApiError ? `${err.message}${err.detail ? ` — ${err.detail}` : ""}` : String(err);
    } finally {
      this.busy = "";
    }
  }

  private onAdd(event: SubmitEvent) {
    event.preventDefault();
    const data = new FormData(event.target as HTMLFormElement);
    const payload: Record<string, unknown> = {
      url: String(data.get("url") ?? "").trim(),
      credential_id: String(data.get("credential_id") ?? "") || null,
      category: String(data.get("category") ?? "") || null,
      ref_kind: String(data.get("ref_kind") ?? "tag"),
      pinned_ref: String(data.get("pinned_ref") ?? "").trim() || null,
      auto_update: data.get("auto_update") === "on",
    };
    void this.act("add", async () => {
      await api.repos.add(payload);
      this.adding = false;
    }, "Repository added");
  }

  private install(repo: Repo, ref?: string) {
    if (ref === "") return;
    void this.act(repo.id, () => api.repos.install(repo.id, ref), `Installed ${repo.slug}`);
  }

  private refresh(repo: Repo) {
    void this.act(repo.id, () => api.repos.refresh(repo.id), `Checked ${repo.slug}`);
  }

  private uninstall(repo: Repo) {
    void this.act(repo.id, async () => {
      const result = await api.repos.uninstall(repo.id);
      if (result.modified.length) {
        throw new ApiError(409, "Modified", `Locally modified files were left alone: ${result.modified.join(", ")}`);
      }
    }, `Uninstalled ${repo.slug}`);
  }

  private deleteRepo(repo: Repo) {
    void this.act(repo.id, () => api.repos.remove(repo.id), `Removed ${repo.slug}`);
  }

  private patch(repo: Repo, payload: Record<string, unknown>) {
    void this.act(repo.id, () => api.repos.patch(repo.id, payload), "Saved");
  }

  private async toggle(repo: Repo) {
    if (this.expanded === repo.id) {
      this.expanded = "";
      return;
    }
    this.expanded = repo.id;
    if (!this.refs[repo.id]) {
      try {
        this.refs = { ...this.refs, [repo.id]: await api.repos.refs(repo.id) };
      } catch {
        this.refs = { ...this.refs, [repo.id]: [] };
      }
    }
  }

  private checkAll() {
    void this.act("all", async () => {
      const summary = await api.updates.check();
      this.notice = `Checked ${summary.checked}, ${summary.updates.length} with updates${
        summary.skipped_locked ? `, ${summary.skipped_locked} skipped while locked` : ""
      }`;
    }, "");
  }
}
