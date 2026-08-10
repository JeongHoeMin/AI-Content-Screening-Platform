export interface CatalogOption {
  value: string;
  label: string;
}

export const THEMES: CatalogOption[] = [
  { value: "semiconductor", label: "반도체" },
  { value: "artificial_intelligence", label: "AI" },
  { value: "renewable_energy", label: "대체에너지" },
];

export const TOPICS: CatalogOption[] = [
  { value: "earnings", label: "실적" },
  { value: "policy", label: "정책" },
  { value: "supply_chain", label: "공급망" },
  { value: "technology", label: "기술" },
];

export function toggle(values: string[], value: string): string[] {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}
