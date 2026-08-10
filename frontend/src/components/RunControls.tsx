"use client";

const COLLECTION_SIZES = [
  { value: 10, label: "적게 · 10건" },
  { value: 25, label: "중간 · 25건" },
  { value: 50, label: "많이 · 50건" },
  { value: 100, label: "최대 · 100건" },
];

const THEMES = [
  { value: "semiconductor", label: "반도체" },
  { value: "artificial_intelligence", label: "AI" },
  { value: "renewable_energy", label: "대체에너지" },
];

const TOPICS = [
  { value: "earnings", label: "실적" },
  { value: "policy", label: "정책" },
  { value: "supply_chain", label: "공급망" },
  { value: "technology", label: "기술" },
];

interface RunControlsProps {
  limit: number;
  themes: string[];
  topics: string[];
  disabled: boolean;
  isRunning: boolean;
  onLimitChange: (limit: number) => void;
  onThemesChange: (themes: string[]) => void;
  onTopicsChange: (topics: string[]) => void;
  onRun: () => void;
}

function toggle(values: string[], value: string): string[] {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

export function RunControls({
  limit,
  themes,
  topics,
  disabled,
  isRunning,
  onLimitChange,
  onThemesChange,
  onTopicsChange,
  onRun,
}: RunControlsProps) {
  return (
    <div className="run-controls">
      <button onClick={onRun} disabled={disabled}>
        {isRunning ? "추천 분석 중…" : "오늘의 뉴스를 기준으로 추천받기"}
      </button>

      <fieldset className="option-group">
        <legend className="empty">분석 건수</legend>
        {COLLECTION_SIZES.map((size) => (
          <span key={size.value}>
            <input
              type="radio"
              id={`size-${size.value}`}
              name="collection-size"
              value={size.value}
              checked={limit === size.value}
              disabled={disabled}
              onChange={() => onLimitChange(size.value)}
            />
            <label htmlFor={`size-${size.value}`}>{size.label}</label>
          </span>
        ))}
      </fieldset>

      <fieldset className="option-group">
        <legend className="empty">투자 테마</legend>
        {THEMES.map((theme) => (
          <span key={theme.value}>
            <input
              type="checkbox"
              id={`theme-${theme.value}`}
              value={theme.value}
              checked={themes.includes(theme.value)}
              disabled={disabled}
              onChange={() => onThemesChange(toggle(themes, theme.value))}
            />
            <label htmlFor={`theme-${theme.value}`}>{theme.label}</label>
          </span>
        ))}
      </fieldset>

      <fieldset className="option-group">
        <legend className="empty">뉴스 주제</legend>
        {TOPICS.map((topic) => (
          <span key={topic.value}>
            <input
              type="checkbox"
              id={`topic-${topic.value}`}
              value={topic.value}
              checked={topics.includes(topic.value)}
              disabled={disabled}
              onChange={() => onTopicsChange(toggle(topics, topic.value))}
            />
            <label htmlFor={`topic-${topic.value}`}>{topic.label}</label>
          </span>
        ))}
      </fieldset>
    </div>
  );
}
