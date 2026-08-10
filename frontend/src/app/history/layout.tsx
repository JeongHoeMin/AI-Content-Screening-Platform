import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "추천 이력",
  description:
    "과거 추천 실행별로 매수·매도 종목의 진입가 대비 현재가 손익률을 확인합니다.",
};

export default function HistoryLayout({ children }: LayoutProps<"/history">) {
  return children;
}
