import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "오늘의 투자 인사이트",
  description:
    "공식 RSS 전문을 수집하고 LangGraph 분석을 거쳐 Policy 기반 투자 후보를 생성합니다.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
