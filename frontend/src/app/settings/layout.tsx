import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "정기 실행 설정",
  description: "RSS 기반 추천 작업의 KST cron 정기 실행 조건을 설정합니다.",
};

export default function SettingsLayout({ children }: LayoutProps<"/settings">) {
  return children;
}
