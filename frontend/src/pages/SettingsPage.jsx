import { useEffect, useState } from "react";
import { ErrorBox, Loading } from "../components/Status";
import { api, HOSTED } from "../services/api";

function CheckboxGroup({ legend, options, selected, onChange }) {
  const toggle = (option) =>
    onChange(selected.includes(option) ? selected.filter((o) => o !== option) : [...selected, option]);
  return (
    <fieldset>
      <legend>{legend}</legend>
      {options.map((option) => (
        <label key={option} className="check">
          <input type="checkbox" checked={selected.includes(option)} onChange={() => toggle(option)} />
          {option}
        </label>
      ))}
      {selected.length === 0 && <p className="hint">None selected: this filter is off (anything passes).</p>}
    </fieldset>
  );
}

const toKeywordList = (text) => text.split(",").map((k) => k.trim()).filter(Boolean);

export default function SettingsPage({ notifier }) {
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState(null);
  const [keywordText, setKeywordText] = useState("");
  const [status, setStatus] = useState({ saving: false, saved: false, error: null });

  useEffect(() => {
    Promise.all([api.getSettingsOptions(), api.getSettings()])
      .then(([opts, settings]) => {
        setOptions(opts);
        setForm(settings);
        setKeywordText(settings.keywords.join(", "));
      })
      .catch((error) => setStatus((s) => ({ ...s, error })));
  }, []);

  const update = (key) => (value) => {
    setForm((f) => ({ ...f, [key]: value }));
    setStatus((s) => ({ ...s, saved: false }));
  };

  async function save(event) {
    event.preventDefault();
    setStatus({ saving: true, saved: false, error: null });
    try {
      const { detail, ...saved } = await api.saveSettings({ ...form, keywords: toKeywordList(keywordText) });
      setForm(saved);
      setKeywordText(saved.keywords.join(", "));
      setStatus({ saving: false, saved: detail ?? "Saved", error: null });
    } catch (error) {
      setStatus({ saving: false, saved: false, error });
    }
  }

  if (!form || !options) {
    return <section><h2 className="page-title">Settings</h2><ErrorBox error={status.error} />{!status.error && <Loading />}</section>;
  }

  const { permission, requestPermission, sendTest } = notifier;

  return (
    <section>
      <h2 className="page-title">Settings</h2>
      <form className="settings" onSubmit={save}>
        <CheckboxGroup legend="Locations" options={options.locations} selected={form.locations}
                       onChange={update("locations")} />
        <CheckboxGroup legend="Job types" options={options.job_types} selected={form.job_types}
                       onChange={update("job_types")} />
        <CheckboxGroup legend="Categories" options={options.categories} selected={form.categories}
                       onChange={update("categories")} />

        <fieldset>
          <legend>Keywords</legend>
          <input type="text" value={keywordText} placeholder="python, backend, machine learning"
                 onChange={(e) => { setKeywordText(e.target.value); setStatus((s) => ({ ...s, saved: false })); }} />
          <p className="hint">Comma-separated. A job matches if it contains <b>any</b> keyword. Empty = no keyword filter.</p>
        </fieldset>

        <fieldset>
          <legend>Freshness</legend>
          <label className="inline">
            Only jobs posted in the last
            <input type="number" min="1" max="365" value={form.max_age_days ?? ""}
                   onChange={(e) => update("max_age_days")(e.target.value === "" ? null : Number(e.target.value))} />
            days
          </label>
          <p className="hint">Leave empty for no limit. Jobs with no posting date always pass.</p>
        </fieldset>

        <fieldset>
          <legend>Notifications</legend>
          <label className="check">
            <input type="checkbox" checked={form.browser_notifications}
                   onChange={(e) => update("browser_notifications")(e.target.checked)} />
            {HOSTED ? "Browser popups while the dashboard is open" : "Browser notifications"}
          </label>
          <div className="permission">
            {permission === "granted" && <>
              <span className="status ok">● Allowed in this browser</span>
              <button type="button" className="button small" onClick={sendTest}>Send test</button>
            </>}
            {permission === "default" && (
              <button type="button" className="button small" onClick={requestPermission}>Allow notifications</button>
            )}
            {permission === "denied" && (
              <span className="status error">Blocked by the browser. Allow notifications for this site in the address bar.</span>
            )}
            {permission === "unsupported" && <span className="status error">This browser does not support notifications.</span>}
          </div>
          <p className="hint">
            {HOSTED
              ? "Telegram alerts are sent by the hourly GitHub scan, whether or not this page is open. Browser popups are an extra while the dashboard is open."
              : "Alerts are shown while a Job Radar tab is open. Missed ones are shown when you return."}
          </p>
        </fieldset>

        <ErrorBox error={status.error} />
        <div className="form-actions">
          <button className="button primary" type="submit" disabled={status.saving}>
            {status.saving ? "Saving…" : "Save settings"}
          </button>
          {status.saved && <span className="status ok">{status.saved}</span>}
        </div>
        {HOSTED && <p className="hint">Saving asks for the admin password once per browser tab.</p>}
        <p className="hint">Filters decide which <b>newly discovered</b> jobs notify you. Jobs already seen are never announced again.</p>
      </form>
    </section>
  );
}
