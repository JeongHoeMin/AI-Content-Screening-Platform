"use client";

import { useCallback, useState } from "react";

import { SiteNav } from "@/components/SiteNav";
import { THEMES, TOPICS, toggle } from "@/lib/catalog";

const LIMITS = [25, 50, 100] as const;

interface ScheduleSettings {
  active: boolean;
  cron_expression: string;
  timezone: string;
  themes: string[];
  topics: string[];
  limit: number;
  telegram_enabled: boolean;
  version: number;
  next_run_at: string;
}

function nextRunText(nextRunAt: string): string {
  return `저장됨 · 다음 실행 ${new Date(nextRunAt).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
  })} KST`;
}

export default function SettingsPage() {
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [authenticated, setAuthenticated] = useState(false);

  const [active, setActive] = useState(true);
  const [cron, setCron] = useState("0 8 * * *");
  const [limit, setLimit] = useState<number>(25);
  const [themes, setThemes] = useState<string[]>([]);
  const [topics, setTopics] = useState<string[]>([]);
  const [telegram, setTelegram] = useState(false);
  const [version, setVersion] = useState<number | null>(null);
  const [saveStatus, setSaveStatus] = useState("");
  const [saving, setSaving] = useState(false);

  const applySettings = useCallback((value: ScheduleSettings) => {
    setVersion(value.version);
    setActive(value.active);
    setCron(value.cron_expression);
    setLimit(value.limit);
    setThemes([...value.themes]);
    setTopics([...value.topics]);
    setTelegram(value.telegram_enabled);
    setSaveStatus(nextRunText(value.next_run_at));
  }, []);

  const login = useCallback(async () => {
    setLoginError("");
    let response: Response;
    try {
      response = await fetch("/api/settings/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password }),
      });
    } catch {
      setPassword("");
      setLoginError("서버에 연결하지 못했습니다.");
      return;
    }
    // The password only ever travels with this request; it is never stored.
    setPassword("");
    if (!response.ok) {
      setLoginError("비밀번호가 일치하지 않거나 서버 설정이 완료되지 않았습니다.");
      return;
    }
    setAuthenticated(true);

    try {
      const scheduleResponse = await fetch("/api/settings/schedule");
      if (scheduleResponse.status === 404) {
        // No schedule configured yet: show the form with its defaults.
        setSaveStatus("아직 저장된 정기 실행 설정이 없습니다. 새로 만들 수 있습니다.");
        return;
      }
      if (!scheduleResponse.ok) throw new Error("schedule_load_failed");
      applySettings(await scheduleResponse.json());
    } catch {
      setLoginError("설정 정보를 불러오지 못했습니다.");
    }
  }, [applySettings, password]);

  const save = useCallback(async () => {
    setSaving(true);
    try {
      const response = await fetch("/api/settings/schedule", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          active,
          cron_expression: cron,
          themes,
          topics,
          limit,
          telegram_enabled: telegram,
          version,
        }),
      });
      if (response.status === 409) {
        setSaveStatus(
          "다른 화면에서 설정이 변경되었습니다. 새로고침 후 다시 저장해 주세요.",
        );
        return;
      }
      if (!response.ok) {
        setSaveStatus("저장에 실패했습니다. cron 및 서버 연결을 확인해 주세요.");
        return;
      }
      applySettings(await response.json());
    } catch {
      setSaveStatus("저장에 실패했습니다. 서버 연결을 확인해 주세요.");
    } finally {
      setSaving(false);
    }
  }, [active, applySettings, cron, limit, telegram, themes, topics, version]);

  return (
    <main>
      <h1>정기 실행 설정</h1>
      <p className="empty">
        RSS 기반 추천 작업의 cron은 한국시간 기준입니다. 비밀번호는 로그인 요청에만 사용하며
        브라우저에 저장하지 않습니다.
      </p>
      <SiteNav current="/settings" />

      {!authenticated && (
        <section className="panel">
          <h2>접근 확인</h2>
          <label>
            설정 비밀번호
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void login();
              }}
            />
          </label>
          <button type="button" onClick={() => void login()}>
            설정 페이지 열기
          </button>
          {loginError && <p className="negative">{loginError}</p>}
        </section>
      )}

      {authenticated && (
        <section className="panel">
          <h2>실행 조건</h2>

          <label>
            <input
              type="checkbox"
              checked={active}
              onChange={(event) => setActive(event.target.checked)}
            />{" "}
            정기 실행 활성화
          </label>

          <label>
            cron 표현식
            <input
              value={cron}
              maxLength={128}
              required
              onChange={(event) => setCron(event.target.value)}
            />
          </label>

          <label>
            분석 건수
            <select
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
            >
              {LIMITS.map((value) => (
                <option key={value} value={value}>
                  {value}건
                </option>
              ))}
            </select>
          </label>

          <fieldset>
            <legend>투자 테마</legend>
            {THEMES.map((theme) => (
              <label key={theme.value}>
                <input
                  type="checkbox"
                  checked={themes.includes(theme.value)}
                  onChange={() => setThemes(toggle(themes, theme.value))}
                />{" "}
                {theme.label}
              </label>
            ))}
          </fieldset>

          <fieldset>
            <legend>뉴스 주제</legend>
            {TOPICS.map((topic) => (
              <label key={topic.value}>
                <input
                  type="checkbox"
                  checked={topics.includes(topic.value)}
                  onChange={() => setTopics(toggle(topics, topic.value))}
                />{" "}
                {topic.label}
              </label>
            ))}
          </fieldset>

          <label>
            <input
              type="checkbox"
              checked={telegram}
              onChange={(event) => setTelegram(event.target.checked)}
            />{" "}
            Telegram 요약 전송
          </label>
          <p className="empty">
            Telegram 자격 증명은 서버 `.env`의 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`로만
            설정합니다.
          </p>

          <button type="button" onClick={() => void save()} disabled={saving}>
            {saving ? "저장 중…" : "저장"}
          </button>
          {saveStatus && <p className="empty">{saveStatus}</p>}
        </section>
      )}
    </main>
  );
}
