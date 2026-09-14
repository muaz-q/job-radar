import { useEffect, useState } from "react";
import { ErrorBox, Loading } from "../components/Status";
import { api, HOSTED } from "../services/api";

function Switch({ id, checked, onChange }) {
  return (
    <span className="switch">
      <input id={id} type="checkbox" role="switch" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="switch-track" aria-hidden="true" />
    </span>
  );
}

function OptionGroup({ name, label, options, selected, onChange }) {
  const toggle = (option, on) => onChange(on ? [...selected, option] : selected.filter((o) => o !== option));
  return (
    <>
      <h2 className="section-label">{label}</h2>
      <div className="group">
        {options.map((option) => {
          const id = `${name}-${option.replace(/\W+/g, "-").toLowerCase()}`;
          return (
            <label key={option} className="row plain setting" htmlFor={id}>
              <span>{option}</span>
              <Switch id={id} checked={selected.includes(option)} onChange={(on) => toggle(option, on)} />
            </label>
          );
        })}
      </div>
      {selected.length === 0 && <p className="footnote">None selected, so this filter is off and everything passes.</p>}
    </>
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

  const head = (
    <div className="page-head">
      <div>
        <h1 className="large-title">Settings</h1>
        <p className="page-sub">Choose which newly found jobs alert you</p>
      </div>
    </div>
  );

  if (!form || !options) {
    return <section>{head}<ErrorBox error={status.error} />{!status.error && <Loading />}</section>;
  }

  const { permission, requestPermission, sendTest } = notifier;

  return (
    <section>
      {head}
      <form onSubmit={save}>
        <OptionGroup name="location" label="Locations" options={options.locations} selected={form.locations} onChange={update("locations")} />
        <OptionGroup name="type" label="Job types" options={options.job_types} selected={form.job_types} onChange={update("job_types")} />
        <OptionGroup name="category" label="Categories" options={options.categories} selected={form.categories} onChange={update("categories")} />

        <h2 className="section-label">Keywords</h2>
        <div className="group">
          <input id="keywords" className="field wide-field" type="text" value={keywordText} placeholder="python, backend, machine learning"
                 aria-label="Keywords" onChange={(e) => { setKeywordText(e.target.value); setStatus((s) => ({ ...s, saved: false })); }} />
        </div>
        <p className="footnote">Separate with commas. A job matches if it contains any of them. Leave empty to skip this filter.</p>

        <h2 className="section-label">Freshness</h2>
        <div className="group">
          <label className="row plain setting" htmlFor="max-age">
            <span>Posted within (days)</span>
            <input id="max-age" className="field inline-field" type="number" min="1" max="365" placeholder="Any"
                   value={form.max_age_days ?? ""}
                   onChange={(e) => update("max_age_days")(e.target.value === "" ? null : Number(e.target.value))} />
          </label>
        </div>
        <p className="footnote">Leave empty for no limit. Jobs without a posting date are always shown.</p>

        <h2 className="section-label">Notifications</h2>
        <div className="group">
          <label className="row plain setting" htmlFor="browser-popups">
            <span>{HOSTED ? "Browser alerts while this page is open" : "Browser notifications"}</span>
            <Switch id="browser-popups" checked={form.browser_notifications} onChange={update("browser_notifications")} />
          </label>
          <div className="row plain setting" style={{ cursor: "default" }}>
            <span className="muted">
              {permission === "granted" && "Allowed in this browser"}
              {permission === "default" && "Not allowed yet"}
              {permission === "denied" && "Blocked. Allow notifications for this site from the address bar."}
              {permission === "unsupported" && "This browser doesn't support notifications"}
            </span>
            {permission === "granted" && <button type="button" className="btn btn-sm" onClick={sendTest}>Send Test</button>}
            {permission === "default" && <button type="button" className="btn btn-tinted btn-sm" onClick={requestPermission}>Allow</button>}
          </div>
        </div>
        <p className="footnote">
          {HOSTED
            ? "Telegram alerts come from the hourly scan, whether or not this page is open."
            : "Alerts show while a Job Radar tab is open. Missed ones appear when you come back."}
        </p>

        <div style={{ marginTop: 24 }}><ErrorBox error={status.error} /></div>
        <div className="save-bar">
          <button className="btn btn-primary btn-lg" type="submit" disabled={status.saving}>
            {status.saving ? "Saving…" : "Save"}
          </button>
          {status.saved && <span className="saved">{status.saved}</span>}
        </div>
        <p className="footnote" style={{ paddingInline: 0, marginTop: 14 }}>
          Filters only decide which newly found jobs alert you; a job is never announced twice.
          {HOSTED && " Saving asks for your admin password once per tab."}
        </p>
      </form>
    </section>
  );
}
