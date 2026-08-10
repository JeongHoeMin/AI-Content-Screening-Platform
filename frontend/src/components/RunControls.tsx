"use client";

import { THEMES, TOPICS, toggle } from "@/lib/catalog";
import { Button, Card, ChipOption, Fieldset } from "@/components/ui";

const COLLECTION_SIZES = [
  { value: 10, label: "적게 · 10건" },
  { value: 25, label: "중간 · 25건" },
  { value: 50, label: "많이 · 50건" },
  { value: 100, label: "최대 · 100건" },
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
  const selectedFilterCount = themes.length + topics.length;

  return (
    <Card
      title="추천 실행"
      description="수집 범위와 필터를 고른 뒤 실행하면 결과가 아래에 실시간으로 쌓입니다."
      actions={
        <Button size="lg" onClick={onRun} disabled={disabled}>
          {isRunning ? "추천 분석 중…" : "오늘의 뉴스로 추천받기"}
        </Button>
      }
    >
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-[minmax(0,auto)_minmax(0,1fr)_minmax(0,1fr)]">
        <Fieldset legend="분석 건수">
          {COLLECTION_SIZES.map((size) => (
            <ChipOption
              key={size.value}
              id={`size-${size.value}`}
              name="collection-size"
              type="radio"
              checked={limit === size.value}
              disabled={disabled}
              label={size.label}
              onChange={() => onLimitChange(size.value)}
            />
          ))}
        </Fieldset>

        <Fieldset legend="투자 테마">
          {THEMES.map((theme) => (
            <ChipOption
              key={theme.value}
              id={`theme-${theme.value}`}
              type="checkbox"
              checked={themes.includes(theme.value)}
              disabled={disabled}
              label={theme.label}
              onChange={() => onThemesChange(toggle(themes, theme.value))}
            />
          ))}
        </Fieldset>

        <Fieldset legend="뉴스 주제">
          {TOPICS.map((topic) => (
            <ChipOption
              key={topic.value}
              id={`topic-${topic.value}`}
              type="checkbox"
              checked={topics.includes(topic.value)}
              disabled={disabled}
              label={topic.label}
              onChange={() => onTopicsChange(toggle(topics, topic.value))}
            />
          ))}
        </Fieldset>
      </div>

      <p className="mt-5 border-t border-line pt-4 text-xs text-ink-subtle">
        {selectedFilterCount === 0
          ? "필터를 고르지 않으면 수집된 뉴스 전체를 분석합니다."
          : `테마·주제 필터 ${selectedFilterCount}개가 적용됩니다.`}
        {" 실행이 끝나면 결과 요약이 Telegram으로도 전송됩니다."}
      </p>
    </Card>
  );
}
