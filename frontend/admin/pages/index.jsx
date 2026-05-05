import dynamic from "next/dynamic";

// SSR 비활성화 — localStorage 사용으로 서버에서 렌더링 불가
const AdminApp = dynamic(() => import("../src/App"), { ssr: false });

export default function Home() {
  return <AdminApp />;
}
